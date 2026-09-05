const { apiBase } = require("../config");

function formatDetail(detail) {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join("；");
  }
  return JSON.stringify(detail);
}

function request({ url, method = "GET", data }) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${String(apiBase).replace(/\/$/, "")}${url}`,
      method,
      data,
      header: { "content-type": "application/json" },
      timeout: 120000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        const payload = res.data || {};
        const detail =
          formatDetail(payload.detail || payload.error) || `请求失败 (${res.statusCode})`;
        reject(new Error(detail));
      },
      fail(err) {
        reject(new Error(err.errMsg || "无法连接选型服务"));
      },
    });
  });
}

module.exports = { request, formatDetail };
