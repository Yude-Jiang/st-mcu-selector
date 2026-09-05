const api = require("../../utils/api");
const form = require("../../utils/form");

const APPLICATIONS = [
  { id: "", label: "不指定" },
  { id: "motor_control", label: "电机控制" },
  { id: "power_conversion", label: "电源变换" },
  { id: "bms", label: "电池管理" },
  { id: "industrial_control", label: "工业控制" },
  { id: "iot", label: "物联网" },
];

const PACKAGES = [
  { id: "", label: "不限制" },
  { id: "LQFP", label: "LQFP" },
  { id: "QFN", label: "QFN" },
  { id: "BGA", label: "BGA" },
  { id: "WLCSP", label: "WLCSP" },
];

const MODE_HINTS = {
  requirements: "填必须规格，最多三颗候选",
  competitor: "填已核实规格，对照 STM32",
  inspect: "输入订货号，核对其在库里是什么",
};

const POLICIES = [
  { id: "allow_risk", label: "保留并标出风险" },
  { id: "exclude", label: "库中无证据则排除" },
];

Page({
  data: {
    mode: "requirements",
    modeHint: MODE_HINTS.requirements,
    dbStatus: "器件库加载中",
    banner: "",
    bannerError: false,
    loading: false,
    cards: [],
    inspectCard: null,
    emptyText: "",
    meta: "",
    applications: APPLICATIONS,
    packages: PACKAGES,
    policies: POLICIES,
    applicationIndex: 0,
    packageIndex: 0,
    policyIndex: 0,
    comparePackageIndex: 0,
    rec: {
      frequency_mhz: "",
      flash_kb: "",
      ram_kb: "",
      pin_count: "",
      temperature_max_c: "",
      fdcan: "",
      usb: "",
      motor_timers: "",
      hrtim: "",
    },
    cmp: {
      manufacturer: "",
      part_number: "",
      source_note: "",
      frequency_mhz: "",
      flash_kb: "",
      ram_kb: "",
      pin_count: "",
      fdcan: "",
      usb: "",
      motor_timers: "",
      hrtim: "",
    },
    inspectPart: "",
  },

  onShow() {
    this.refreshHealth();
  },

  switchMode(event) {
    const mode = event.currentTarget.dataset.mode;
    this.setData({
      mode,
      modeHint: MODE_HINTS[mode],
      cards: [],
      inspectCard: null,
      emptyText: "",
      meta: "",
      banner: "",
      bannerError: false,
    });
  },

  onRecInput(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({ [`rec.${field}`]: event.detail.value });
  },

  onCmpInput(event) {
    const field = event.currentTarget.dataset.field;
    this.setData({ [`cmp.${field}`]: event.detail.value });
  },

  onInspectInput(event) {
    this.setData({ inspectPart: event.detail.value });
  },

  onApplicationChange(event) {
    this.setData({ applicationIndex: Number(event.detail.value) });
  },

  onPackageChange(event) {
    this.setData({ packageIndex: Number(event.detail.value) });
  },

  onPolicyChange(event) {
    this.setData({ policyIndex: Number(event.detail.value) });
  },

  onComparePackageChange(event) {
    this.setData({ comparePackageIndex: Number(event.detail.value) });
  },

  setBanner(message, isError) {
    this.setData({ banner: message || "", bannerError: Boolean(isError) });
  },

  async refreshHealth() {
    try {
      const payload = await api.health();
      const count = payload.counts && payload.counts.cpn ? payload.counts.cpn : "";
      this.setData({ dbStatus: count ? `器件库就绪 · ${count} 个订货号` : "器件库就绪" });
    } catch (error) {
      this.setData({ dbStatus: error.message || "器件库未就绪" });
    }
  },

  async onRecommendSubmit() {
    const rec = { ...this.data.rec, package_type: PACKAGES[this.data.packageIndex].id };
    this.setBanner("正在查询公开 MCU 数据库…", false);
    this.setData({ loading: true, cards: [], inspectCard: null, emptyText: "", meta: "" });
    try {
      const payload = await api.recommend({
        must: form.collectMust(rec),
        application: APPLICATIONS[this.data.applicationIndex].id || null,
        unknown_policy: POLICIES[this.data.policyIndex].id,
        limit: 3,
      });
      this.renderCards(payload);
    } catch (error) {
      this.setBanner(error.message, true);
    } finally {
      this.setData({ loading: false });
    }
  },

  async onCompareSubmit() {
    const cmp = { ...this.data.cmp, package_type: PACKAGES[this.data.comparePackageIndex].id };
    if (!cmp.manufacturer || !cmp.part_number || String(cmp.source_note).length < 5) {
      this.setBanner("厂商、订货号和规格来源（至少 5 字）都要填。", true);
      return;
    }
    const specs = form.collectSpecs(cmp);
    if (Object.keys(specs).length === 0) {
      this.setBanner("请至少填写一项已核实的竞品规格。", true);
      return;
    }
    this.setBanner("正在查询公开 MCU 数据库…", false);
    this.setData({ loading: true, cards: [], inspectCard: null, emptyText: "", meta: "" });
    try {
      const payload = await api.compare({
        manufacturer: cmp.manufacturer,
        part_number: cmp.part_number,
        source_note: cmp.source_note,
        specs,
        essential: Object.keys(specs),
        limit: 3,
      });
      this.renderCards(payload);
    } catch (error) {
      this.setBanner(error.message, true);
    } finally {
      this.setData({ loading: false });
    }
  },

  async onInspectSubmit() {
    const partNumber = String(this.data.inspectPart || "").trim();
    if (partNumber.length < 3) {
      this.setBanner("请填写至少 3 个字符的 STM32 订货号。", true);
      return;
    }
    this.setBanner("正在查询公开 MCU 数据库…", false);
    this.setData({ loading: true, cards: [], inspectCard: null, emptyText: "", meta: "" });
    try {
      const payload = await api.inspect(partNumber);
      this.renderInspect(payload);
    } catch (error) {
      this.setBanner(error.message, true);
    } finally {
      this.setData({ loading: false });
    }
  },

  renderCards(payload) {
    const cards = form.toCards(payload);
    const rejected = payload.rejected_by_hard_constraints;
    const extra = rejected === undefined ? "" : `硬约束剔除 ${rejected} 颗。`;
    this.setData({
      cards,
      inspectCard: null,
      emptyText: cards.length ? "" : "没有满足硬约束的候选。放宽 must 条件后再试。",
      meta: `${payload.disclaimer || ""} ${extra}`.trim(),
      banner: "",
      bannerError: false,
    });
  },

  renderInspect(payload) {
    if (!payload.found) {
      const suggestions = (payload.suggestions || []).join("、");
      this.setData({
        cards: [],
        inspectCard: null,
        emptyText: `未找到 ${payload.part_number}。${suggestions ? "相近订货号：" + suggestions : ""}`,
        meta: "",
        banner: "",
        bannerError: false,
      });
      return;
    }
    this.setData({
      cards: [],
      inspectCard: form.toInspectCard(payload),
      emptyText: "",
      meta: "",
      banner: "",
      bannerError: false,
    });
  },

  openStLink(event) {
    const url = event.currentTarget.dataset.url;
    if (!url) return;
    wx.setClipboardData({
      data: url,
      success: () => {
        wx.showToast({ title: "已复制 st.com 链接", icon: "none" });
      },
    });
  },
});
