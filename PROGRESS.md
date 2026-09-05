# 项目进度: ST MCU Selector

### Intent

终端用户在网页或微信小程序上做推荐 / 竞品对照 / 订货号查询。同一套引擎；**Cloud Run + GCS** 与 **阿里云 SAE + OSS + 小程序** 文档分目录，互不覆盖。

### TODO

- [x] 网页表单对接 recommend / compare / inspect
- [x] Dockerfile（8080，启动后拉库）
- [x] 微信小程序表单对接同一套 API
- [x] 文档拆分：`docs/cloud-run/`（GCS）与 `docs/aliyun/`（OSS / 小程序）
- [x] 器件库对象缓存（ETag；GCS 或 OSS 二选一）
- [ ] Cloud Shell：建 GCS 桶并 `gcloud run deploy`（见 `docs/cloud-run/`）
- [ ] 阿里云：ACR push、SAE 应用、已备案 HTTPS、微信合法域名（见 `docs/aliyun/`）
