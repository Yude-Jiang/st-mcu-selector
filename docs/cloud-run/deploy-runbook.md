# Deploy Smoke and Rollback — Cloud Run

Service: Cloud Run `st-mcu-selector` in `st-china-ai-force` / `asia-east1`，port 8080。器件库缓存：GCS。

阿里云 SAE 回滚见 [`../aliyun/deploy-runbook.md`](../aliyun/deploy-runbook.md)。

## 1) Post-deploy smoke

```bash
npm run smoke -- --url=https://<your-cloud-run-url>
```

Expected:

- Homepage `200`，含 `id="root"` 与 ST MCU Selector
- `/healthz` 就绪为 `200`，加载中为 `503`
- `/api/health` 含 `cache.source`（`gcs` | `st` | `local`）与 `cache.stale`

## 2) Rollback

### Option A: 上一 revision

```bash
gcloud run revisions list --service=st-mcu-selector --region=asia-east1 --project=st-china-ai-force
gcloud run services update-traffic st-mcu-selector \
  --region=asia-east1 \
  --project=st-china-ai-force \
  --to-revisions=<stable-revision>=100
```

### Option B: 上一镜像 tag

```bash
gcloud run deploy st-mcu-selector \
  --region=asia-east1 \
  --project=st-china-ai-force \
  --image=<registry>/<project>/<image>:<previous-tag>
```

## 3) Post-rollback

1. 再跑 smoke
2. 网页三种表单仍能出短名单
