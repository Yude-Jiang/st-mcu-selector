const FACT_LABELS = {
  core: "内核",
  frequency_mhz: "主频",
  flash_kb: "Flash",
  ram_kb: "RAM",
  package: "封装",
  package_type: "封装类型",
  pin_count: "引脚",
  temperature_min_c: "最低工作温度",
  temperature_max_c: "最高工作温度",
  voltage_min_v: "最低电压",
  voltage_max_v: "最高电压",
  adc_channels: "ADC 通道",
  adc_units: "ADC 单元",
  opamps: "运放",
  comparators: "比较器",
  dac_channels: "DAC 通道",
  can: "CAN",
  fdcan: "FDCAN",
  usb: "USB",
  usb_types: "USB 类型",
  ethernet: "Ethernet",
  ethernet_speed_mbps: "Ethernet 速率",
  motor_timers: "电机定时器",
  hrtim: "HRTIM",
  timers: "定时器",
  timers_16bit: "16 位定时器",
  timers_32bit: "32 位定时器",
  timers_8bit: "8 位定时器",
  fpu: "FPU",
  firmware_package: "固件包",
};

const IDENTITY_KEYS = ["core", "frequency_mhz", "flash_kb", "ram_kb", "package", "pin_count"];
const SHORTLIST_KEYS = [
  "core", "frequency_mhz", "flash_kb", "ram_kb", "package", "pin_count",
  "temperature_max_c", "fdcan", "usb", "motor_timers", "hrtim",
];

const SPEC_GROUPS = [
  { title: "工作条件", keys: ["temperature_min_c", "temperature_max_c", "voltage_min_v", "voltage_max_v"] },
  { title: "通信接口", keys: ["fdcan", "can", "usb", "usb_types", "ethernet", "ethernet_speed_mbps"] },
  { title: "模拟与定时", keys: ["adc_channels", "adc_units", "opamps", "comparators", "dac_channels", "motor_timers", "hrtim", "timers", "timers_16bit", "timers_32bit"] },
];

const LIST_KEYS = [
  { key: "security", title: "安全能力" },
  { key: "other_timer_functions", title: "其他定时功能" },
];

const INSPECT_DISCLAIMER =
  "这是库内身份核对，不是设计签核。封装引脚、外设并发、认证、价格和供货须以 st.com 与最新 datasheet 为准。";

function hasFactValue(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") {
    const text = value.trim().toLowerCase();
    return text !== "" && text !== "null" && text !== "none";
  }
  return true;
}

function formatFactValue(key, value) {
  if (!hasFactValue(value)) return "";
  if (key === "frequency_mhz") return `${value} MHz`;
  if (key === "flash_kb" || key === "ram_kb") return `${value} KB`;
  if (key === "temperature_min_c" || key === "temperature_max_c") return `${value} °C`;
  if (key === "voltage_min_v" || key === "voltage_max_v") return `${value} V`;
  if (key === "ethernet_speed_mbps") return `${value} Mbps`;
  return String(value);
}

function factEntries(facts, keys) {
  const source = facts || {};
  const selected = keys || Object.keys(source);
  return selected
    .filter((key) => hasFactValue(source[key]))
    .map((key) => ({
      key,
      label: FACT_LABELS[key] || key,
      value: formatFactValue(key, source[key]),
    }));
}

function splitFactList(value) {
  return String(value)
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);
}

function lifecycleStatus(raw) {
  const status = String(raw || "").trim();
  const lower = status.toLowerCase();
  if (!status) return { kind: "unknown", text: "库内状态未标注" };
  if (lower.includes("coming soon")) {
    return { kind: "soon", text: "即将供货（库内状态，不是可下单承诺）" };
  }
  if (lower.includes("obsolete")) return { kind: "obsolete", text: "停产（库内状态）" };
  if (lower.includes("nrnd") || lower.includes("not recommended")) {
    return { kind: "nrnd", text: "不建议用于新设计（库内状态）" };
  }
  if (lower.includes("active")) return { kind: "active", text: "量产（库内状态）" };
  return { kind: "other", text: `库内状态：${status}` };
}

function stComSearchUrl(partNumber) {
  const query = encodeURIComponent(String(partNumber || "").trim());
  return `https://www.st.com/content/st_com/en/search.html#q=${query}&t=products`;
}

function inspectModel(payload) {
  const facts = payload.normalized || {};
  const rpn = payload.rpn || {};
  const partNumber = payload.part_number || "";
  const groups = SPEC_GROUPS.map((group) => ({
    title: group.title,
    items: factEntries(facts, group.keys),
  })).filter((group) => group.items.length > 0);
  const lists = LIST_KEYS.map((entry) => ({
    title: entry.title,
    items: hasFactValue(facts[entry.key]) ? splitFactList(facts[entry.key]) : [],
  })).filter((entry) => entry.items.length > 0);
  return {
    partNumber,
    stUrl: stComSearchUrl(partNumber),
    status: lifecycleStatus(rpn.marketingStatus),
    description: rpn.description || payload.reference || "",
    identity: factEntries(facts, IDENTITY_KEYS),
    groups,
    lists,
    disclaimer: INSPECT_DISCLAIMER,
  };
}

function shortlistModel(item, index, mode) {
  return {
    rank: index + 1,
    partNumber: item.part_number,
    score: item.score,
    status: lifecycleStatus(item.status),
    facts: factEntries(item.facts, SHORTLIST_KEYS),
    evidenceTitle: mode === "competitor" ? "与竞品对照" : "依据",
    evidence: item.matches || item.comparisons || [],
    penalties: item.penalties || [],
    otherPackages: item.other_packages || [],
    risks: item.risks || [],
  };
}

module.exports = { factEntries, inspectModel, shortlistModel };
