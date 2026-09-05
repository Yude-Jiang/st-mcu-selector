# 项目进度: ST MCU Selector

### Intent

终端用户在网页或微信小程序上直接做推荐 / 竞品对照 / 订货号查询；后端复用同一套公开库引擎，托管在阿里云 SAE，器件库缓存走 OSS。

### TODO

- [x] 网页表单对接 recommend / compare / inspect
- [x] Dockerfile（8080，启动后拉库）
- [x] 微信小程序表单对接同一套 API
- [x] 部署目标改为阿里云 SAE + ACR（不再用 Cloud Run）
- [x] 器件库缓存从 GCS 改为 OSS
- [ ] 在已登录 aliyun / ACR 的环境 push 镜像并创建 SAE 应用
- [ ] 绑定已备案 HTTPS 域名，写入小程序 production 与微信合法域名
