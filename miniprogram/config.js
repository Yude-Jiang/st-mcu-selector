/**
 * 小程序有两条独立的域名配置，别混：
 *
 * 1. apiBase —— wx.request 调 API 用，对应公众平台「服务器域名 → request 合法域名」
 * 2. webBase —— web-view 内嵌网页用，对应公众平台「业务域名」
 *    业务域名要单独配，还要把校验文件放到域名根目录；只填 host，不带 https:// 和路径
 *
 * develop:    开发者工具里验证。勾上「不校验合法域名、web-view（业务域名）、TLS」
 *             才能内嵌 Cloud Run；真机预览不行，run.app 没有 ICP 备案
 * production: 体验版/正式版。必须是已备案域名，且已配成业务域名
 */
const ENV = "develop";

const HOSTS = {
  develop: {
    // 本机 FastAPI 供 wx.request 用；web-view 不能内嵌 http，所以指向 Cloud Run
    api: "http://127.0.0.1:8080",
    web: "https://st-mcu-selector-460989091461.asia-east1.run.app",
  },
  production: {
    api: "https://mp.microelectronics.com",
    web: "https://mp.microelectronics.com",
  },
};

module.exports = {
  env: ENV,
  apiBase: HOSTS[ENV].api,
  webBase: HOSTS[ENV].web,
};
