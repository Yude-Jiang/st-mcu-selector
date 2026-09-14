const { webBase, env } = require("../../config");

// Tells the page it is running inside this shell so it skips the @st.com gate. The
// mini program is already internal-only, and its web-view would otherwise ask for the
// address on every launch because sessionStorage does not survive a new web-view.
const EMBED_QUERY = "embed=miniprogram";

// web-view fills the page and cannot be mixed with other components, so the error
// state replaces it entirely rather than overlaying it.
Page({
  data: {
    url: "",
    failed: false,
    hint: "",
  },

  onLoad() {
    this.load();
  },

  load() {
    const base = String(webBase || "").replace(/\/$/, "");
    if (!/^https:\/\//.test(base)) {
      // web-view refuses http even in the devtools; catch it here so the page says
      // why instead of rendering blank.
      this.setData({
        failed: true,
        hint: `web-view 只能内嵌 https，当前 webBase 是 ${base || "(空)"}。请改 miniprogram/config.js。`,
      });
      return;
    }
    const separator = base.indexOf("?") === -1 ? "?" : "&";
    this.setData({ url: `${base}${separator}${EMBED_QUERY}`, failed: false, hint: "" });
  },

  onWebViewLoad() {
    this.setData({ failed: false, hint: "" });
  },

  onWebViewError(event) {
    const detail = (event && event.detail && event.detail.errMsg) || "";
    this.setData({
      failed: true,
      hint: env === "develop"
        ? `网页加载失败${detail ? "：" + detail : ""}。开发者工具需勾选「不校验合法域名、web-view（业务域名）、TLS」；真机预览无法内嵌未备案域名。`
        : `网页加载失败${detail ? "：" + detail : ""}。请确认该域名已在公众平台配成业务域名，且校验文件已放到域名根目录。`,
    });
  },

  onRetry() {
    this.load();
  },

  onCopyUrl() {
    wx.setClipboardData({
      data: this.data.url || webBase,
      success() {
        wx.showToast({ title: "已复制网址", icon: "none" });
      },
    });
  },
});
