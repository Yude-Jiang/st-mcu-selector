/**
 * 小程序只调本服务 HTTP API（recommend / compare / inspect），
 * 不能在微信里直接跑 Claude skill。
 *
 * develop: 本机 `python run.py`，开发者工具勾选「不校验合法域名、不校验 TLS」
 * production: 换成已 ICP 备案的阿里云 HTTPS 域名，并写入微信公众平台 request 合法域名
 */
const ENV = "develop";

const HOSTS = {
  develop: "http://127.0.0.1:8080",
  production: "https://REPLACE-WITH-ICP-DOMAIN",
};

module.exports = {
  env: ENV,
  apiBase: HOSTS[ENV],
};
