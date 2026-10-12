/**
 * 小程序用 web-view 打开本服务选型页，不在微信里跑 Claude skill。
 *
 * 微信公众平台「业务域名」（web-view）和「request 合法域名」都填 host：
 * mp.microelectronics.com（不要带 https:// 和路径）
 *
 * develop: 开发者工具里验证，勾选「不校验合法域名、web-view（业务域名）、TLS」。
 *          不能指向 http://127.0.0.1 —— web-view 不加载 http，会直接白屏。
 * production: 体验版/正式版，必须是已备案且已配成业务域名的 HTTPS 地址。
 */
const ENV = "develop";

const HOSTS = {
  // web-view cannot load http at all, so develop points at the Cloud Run deployment
  // rather than the local server. Tick 不校验合法域名 / 业务域名 in the devtools to
  // use it; a real-device preview still needs the filed domain below.
  develop: "https://st-mcu-selector-460989091461.asia-east1.run.app",
  production: "https://mp.microelectronics.com",
};

module.exports = {
  env: ENV,
  webViewUrl: `${HOSTS[ENV]}/?mp=1`,
};
