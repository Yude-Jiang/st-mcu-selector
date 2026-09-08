# 项目进度: ST MCU Selector

### Intent

终端用户在网页或微信小程序上做推荐 / 竞品对照 / 订货号查询。同一套引擎；**Cloud Run + GCS** 与 **阿里云 SAE + OSS + 小程序** 文档分目录，互不覆盖。

### TODO

- [x] 网页表单对接 recommend / compare / inspect
- [x] Dockerfile（8080，启动后拉库）
- [x] 微信小程序表单对接同一套 API
- [x] 文档拆分：`docs/cloud-run/`（GCS）与 `docs/aliyun/`（OSS / 小程序）
- [x] 器件库对象缓存（ETag；GCS 或 OSS 二选一）
- [x] 模型接地：结论里的料号与数字必须来自检索结果，校验不过回退确定性文本（`nl_ground.py`）
- [x] 竞品规格不再由模型回忆；只接受上传的 datasheet 或用户填写的参数
- [x] 公开端点限流：单客户端 + 全局两层滑动窗口（见 `docs/cloud-run/README.md#限流`）
- [x] 器件库新鲜度：后台按周重查上游 ETag，`/api/db-freshness` 可随时确认是否落后（`db_refresh.py`）
- [ ] Cloud Shell：建 GCS 桶并 `gcloud run deploy`（见 `docs/cloud-run/`）
- [x] 微信 request 合法域名定为 `mp.microelectronics.com`（已 ICP，阿里云）
- [ ] 按 `docs/aliyun/sae-bind-domain.md`：ACR 推镜像、建 SAE、`mp.microelectronics.com` 整站指到该应用
