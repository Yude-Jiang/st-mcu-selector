# Cloud Run + GCS

Google Cloud 网页入口：Cloud Shell clone 后 `gcloud run deploy`。器件库缓存用 **GCS**（`ST_MCU_GCS_BUCKET`），不要设 `ST_MCU_OSS_BUCKET`。

微信小程序不能用 `*.run.app`（需 ICP 备案域名）。小程序与阿里云见 [`../aliyun/README.md`](../aliyun/README.md)。

仓库：https://github.com/Yude-Jiang/st-mcu-selector

## Cloud Shell

```bash
git clone https://github.com/Yude-Jiang/st-mcu-selector.git
cd st-mcu-selector
gcloud config set project st-china-ai-force
```

`gcloud run deploy --source .` 必须在仓库根目录（有 `Dockerfile` 的那层）。

## GCS 缓存桶（冷启动）

```bash
gcloud storage buckets create gs://st-china-ai-force-mcu-db \
  --project st-china-ai-force \
  --location asia-east1 \
  --uniform-bucket-level-access

PROJECT_NUMBER=$(gcloud projects describe st-china-ai-force --format='value(projectNumber)')
gcloud storage buckets add-iam-policy-binding gs://st-china-ai-force-mcu-db \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role=roles/storage.objectAdmin
```

桶保持空即可。应用会写入 `cube-finder-db/current.json` 和 `objects/<sha256>/cube-finder-db.db`。ETag 变了写新对象，不覆盖上一份；ST 不可达则用上一份，`cache.stale=true`。

未设 `ST_MCU_GCS_BUCKET` 时，启动仍直接从 `sw-center.st.com` 拉 zip。

## 现网

服务名 `st-mcu-selector`。当前 URL：https://st-mcu-selector-460989091461.asia-east1.run.app/

```bash
gcloud run deploy st-mcu-selector \
  --source . \
  --project st-china-ai-force \
  --region asia-east1 \
  --port 8080 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 300 \
  --max-instances 1 \
  --set-env-vars ST_MCU_TRUST_PROXY=true,FORWARDED_ALLOW_IPS=*,ST_MCU_GCS_BUCKET=st-china-ai-force-mcu-db
```

不要用这条命令发还未验收的改版，否则会换掉上面这个 URL 的内容。

## 预览（新 URL）

服务名必须是 **`st-mcu-selector-preview`**，不是 `st-mcu-selector`。Cloud Run 会另给一条 `https://st-mcu-selector-preview-….asia-east1.run.app/`。现网地址不变。两个服务可共用同一 GCS 桶。

```bash
cd st-mcu-selector
git pull

gcloud run deploy st-mcu-selector-preview \
  --source . \
  --project st-china-ai-force \
  --region asia-east1 \
  --port 8080 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 300 \
  --max-instances 1 \
  --set-env-vars ST_MCU_TRUST_PROXY=true,FORWARDED_ALLOW_IPS=*,ST_MCU_GCS_BUCKET=st-china-ai-force-mcu-db
```

Health: `/healthz`（器件库未就绪时 503）。`/api/health` 含 `cache.source`（`gcs` | `st` | `local`）。Smoke 与回滚见 [deploy-runbook.md](./deploy-runbook.md)。
