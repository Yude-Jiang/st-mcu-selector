# 阿里云 SAE + 微信小程序

中国区终端入口：网页与微信小程序共用同一套 FastAPI（recommend / compare / inspect）。

生产域名（已 ICP、阿里云）：**`https://mp.microelectronics.com`**  
微信 request 合法域名只填 host：`mp.microelectronics.com`。

**把域名整站指到 SAE：** 按 [sae-bind-domain.md](./sae-bind-domain.md) 做（ACR → 推镜像 → 建应用 → CLB/证书 → 改 `mp` 解析）。

器件库缓存用 **OSS**（`ST_MCU_OSS_BUCKET`）可第二步再加，不要设 `ST_MCU_GCS_BUCKET`。

Cloud Run / GCS 说明见 [`../cloud-run/README.md`](../cloud-run/README.md)。

## 微信开发者工具

1. 导入仓库根目录，`project.config.json` 已指向 `miniprogram/`
2. 详情 → 本地设置：勾选不校验合法域名、web-view、TLS
3. `miniprogram/config.js` 开发环境默认 `http://127.0.0.1:8080`
4. 真机预览把 `apiBase` 改成电脑局域网 IP，例如 `http://192.168.1.8:8080`
5. 把 `appid` 换成你们的小程序 AppID 后再上传体验版

## OSS 缓存桶（冷启动）

```bash
# 按控制台或 aliyun oss 建专用桶，region 与 SAE 一致（默认 cn-hangzhou）
# 对象由应用写入：cube-finder-db/current.json 与 objects/<sha256>/cube-finder-db.db
```

ETag 与 ST zip 一致则从 OSS 拷贝；变化则拉新包、写新对象、再改 pointer。ST 不可达时用上一份，`/api/health` 里 `cache.stale=true`。

## 部署（SAE + ACR）

```powershell
# 一次性：aliyun configure；docker login registry.cn-hangzhou.aliyuncs.com
$env:ACR_NAMESPACE = "st-mcu-selector"
$env:ALIYUN_REGION = "cn-hangzhou"
$env:ST_MCU_OSS_BUCKET = "<oss-bucket>"
# 第二次起：
# $env:SAE_APP_ID = "<sae-app-id>"
python -m unittest tests.test_api tests.test_db_cache
.\scripts\aliyun-deploy.ps1 production
```

```bash
export ACR_NAMESPACE=st-mcu-selector
export ALIYUN_REGION=cn-hangzhou
export ST_MCU_OSS_BUCKET=<oss-bucket>
# export SAE_APP_ID=<sae-app-id>
python -m unittest tests.test_api tests.test_db_cache
bash scripts/aliyun-deploy.sh production
```

首次未设 `SAE_APP_ID` 时，脚本会打印 `CreateApplication`。创建后：

1. SAE / SLB / 网关把 `mp.microelectronics.com` 指到本服务（若域名上已有站点，只反代 `/api/*` 与 `/healthz`）
2. 微信公众平台 request 合法域名：`mp.microelectronics.com`
3. 体验版把 `miniprogram/config.js` 的 `ENV` 改为 `production`（已指向 `https://mp.microelectronics.com`）
4. 上传小程序代码

Health: `/healthz`（器件库未就绪时 503）。Smoke 与回滚见 [deploy-runbook.md](./deploy-runbook.md)。
