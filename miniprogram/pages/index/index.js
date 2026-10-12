const config = require("../../config");

// web-view fills its page and cannot be mixed with other components, so a load
// failure swaps the whole page for a native view rather than overlaying one.
Page({
  data: {
    src: "",
    failed: false,
    hint: "",
  },

  onLoad() {
    this.load();
  },

  load() {
    const url = String(config.webViewUrl || "");
    if (!/^https:\/\//.test(url)) {
      // web-view refuses http. Caught here so the page says why instead of
      // rendering blank, which is what develop pointing at 127.0.0.1 produces.
      this.setData({
        failed: true,
        hint: `web-view 只能加载 https，当前是 ${url || "(空)"}。` +
          `开发时请把 miniprogram/config.js 的 develop 指向一个 https 地址。`,
      });
      return;
    }
    this.setData({ src: url, failed: false, hint: "" });
  },

  onWebViewLoad() {
    this.setData({ failed: false, hint: "" });
  },

  onWebViewError(event) {
    const detail = (event && event.detail && event.detail.errMsg) || "";
    this.setData({
      failed: true,
      hint: config.env === "develop"
        ? `网页加载失败${detail ? "：" + detail : ""}。开发者工具需勾选「不校验合法域名、web-view（业务域名）、TLS」；真机预览无法加载未备案域名。`
        : `网页加载失败${detail ? "：" + detail : ""}。请确认该域名已配成业务域名，且校验文件可从域名根目录访问。`,
    });
  },

  onRetry() {
    this.load();
  },

  onCopyUrl() {
    wx.setClipboardData({
      data: this.data.src || config.webViewUrl,
      success() {
        wx.showToast({ title: "已复制网址", icon: "none" });
      },
    });
  },
});
