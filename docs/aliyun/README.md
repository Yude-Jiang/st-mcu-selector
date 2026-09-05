# 阿里云 SAE + 微信小程序

中国区终端入口：网页与微信小程序共用同一套 FastAPI（recommend / compare / inspect）。生产必须挂**已 ICP 备案**的 HTTPS 域名（微信不接受 `*.run.app`）。

器件库缓存用 **OSS**（`ST_MCU_OSS_BUCKET`），不要设 `ST_MCU_GCS_BUCKET`。

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
$env:ACR_NAMESPACE = "<your-acr-namespace>"
$env:ALIYUN_REGION = "cn-hangzhou"
$env:ST_MCU_OSS_BUCKET = "<oss-bucket>"
# 第二次起：
# $env:SAE_APP_ID = "<sae-app-id>"
python -m unittest tests.test_api tests.test_db_cache
.\scripts\aliyun-deploy.ps1 production
```

```bash
export ACR_NAMESPACE=<your-acr-namespace>
export ALIYUN_REGION=cn-hangzhou
export ST_MCU_OSS_BUCKET=<oss-bucket>
# export SAE_APP_ID=<sae-app-id>
python -m unittest tests.test_api tests.test_db_cache
bash scripts/aliyun-deploy.sh production
```

首次未设 `SAE_APP_ID` 时，脚本会打印 `CreateApplication`。创建后：

1. SAE 绑定已 ICP 备案的 HTTPS 自定义域名
2. 微信公众平台 → 开发 → 开发管理 → 服务器域名：填入 **request 合法域名**
3. `miniprogram/config.js` 把 `ENV` 改为 `production`，`HOSTS.production` 写成该 HTTPS 地址
4. 上传小程序代码

Health: `/healthz`（器件库未就绪时 503）。Smoke 与回滚见 [deploy-runbook.md](./deploy-runbook.md)。
