/**
 * 小程序用 web-view 打开本服务选型页，不在微信里跑 Claude skill。
 *
 * 微信公众平台「业务域名」（web-view）和「request 合法域名」都填 host：
 * mp.microelectronics.com（不要带 https:// 和路径）
 *
 * develop: 本机 python run.py；开发者工具勾选不校验合法域名 / 业务域名
 * production: 体验版必须 HTTPS，并关掉「不校验」
 */
const ENV = "develop";

const HOSTS = {
  develop: "http://127.0.0.1:8080",
  production: "https://mp.microelectronics.com",
};

module.exports = {
  env: ENV,
  webViewUrl: `${HOSTS[ENV]}/?mp=1`,
};
