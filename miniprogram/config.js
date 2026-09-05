/**
 * 小程序只调本服务 HTTP API（recommend / compare / inspect），
 * 不能在微信里直接跑 Claude skill。
 *
 * 微信公众平台 request 合法域名只填 host：mp.microelectronics.com
 * （不要带 https:// 和路径）
 *
 * develop: 本机 python run.py；开发者工具可勾选「不校验合法域名」
 * production: 体验版/正式版必须用下面 HTTPS，并关掉「不校验合法域名」
 */
const ENV = "develop";

const HOSTS = {
  develop: "http://127.0.0.1:8080",
  production: "https://mp.microelectronics.com",
};

module.exports = {
  env: ENV,
  apiBase: HOSTS[ENV],
};
