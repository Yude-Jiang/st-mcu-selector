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
  --set-env-vars FORWARDED_ALLOW_IPS=*,ST_MCU_GCS_BUCKET=st-china-ai-force-mcu-db \
  --set-secrets VITE_DEEPSEEK_API_KEY=VITE_DEEPSEEK_API_KEY:latest
```

现网不设 `ST_MCU_SERIES_DIVERSIFY`，短名单仍按 RPN 去重，与改版前候选一致。页面（页头、tab、页脚）会更新。

## 预览（新 URL）

服务名必须是 **`st-mcu-selector-preview`**，不是 `st-mcu-selector`。当前 URL：https://st-mcu-selector-preview-460989091461.asia-east1.run.app/

设 `ST_MCU_SERIES_DIVERSIFY=true`，短名单按系列散开。两个服务共用同一 GCS 桶，前端同一套，结果规则不同。

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
  --set-env-vars FORWARDED_ALLOW_IPS=*,ST_MCU_GCS_BUCKET=st-china-ai-force-mcu-db,ST_MCU_SERIES_DIVERSIFY=true \
  --set-secrets VITE_DEEPSEEK_API_KEY=VITE_DEEPSEEK_API_KEY:latest
```

Health: `/healthz`（器件库未就绪时 503）。`/api/health` 含 `cache.source`（`gcs` | `st` | `local`）和 `llm.configured`。Smoke 与回滚见 [deploy-runbook.md](./deploy-runbook.md)。

## 限流

服务是 `--allow-unauthenticated`，页面上的 @st.com 门禁只在浏览器里生效，`curl` 直接打 API 绕得过去。所以 `/api/turn`、`/api/parse-requirements`、`/api/parse-datasheet` 这三个会花 DeepSeek 额度和 CPU 的端点走**单客户端 + 全局**两层滑动窗口；`X-Forwarded-For` 是调用方可伪造的，真正给 API key 兜底的是全局那层。

`/healthz`、`/api/health`、`/api/database` 和静态页永不限流，否则 Cloud Run 会把 revision 判成不健康。

默认值（每分钟），全部可用环境变量覆盖，不改代码：

| 变量 | 默认 | 作用 |
|------|------|------|
| `ST_MCU_RATE_COSTLY_PER_MIN` | 15 | 单客户端，LLM / OCR 端点 |
| `ST_MCU_RATE_CHEAP_PER_MIN` | 90 | 单客户端，纯查库端点 |
| `ST_MCU_RATE_GLOBAL_COSTLY_PER_MIN` | 60 | 全服务，LLM / OCR 端点 |
| `ST_MCU_RATE_GLOBAL_CHEAP_PER_MIN` | 600 | 全服务，纯查库端点 |

超限返回 429，带 `Retry-After`，中英文按 `Accept-Language` 给。

计数在进程内存里。`--max-instances 1` 时全局值是准的；**以后调大 max-instances，实际全局上限会变成「设定值 × 实例数」**，要按比例调低这几个变量，或改用共享存储。

## DeepSeek（Secret Manager）

Secret 名沿用 `VITE_DEEPSEEK_API_KEY`（历史 Vite 命名）。这是 **Cloud Run 运行时环境变量**，不会打进网页；不要用 `--set-env-vars` 明文写 key。

`--set-env-vars` 与 `--set-secrets` 每次都会整组覆盖，deploy 必须把现网/预览需要的环境变量和 secret **全部写全**。现网不要带 `ST_MCU_SERIES_DIVERSIFY`。

第一次把 secret 绑到 Cloud Run 默认计算账号：

```bash
PROJECT_NUMBER=$(gcloud projects describe st-china-ai-force --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding VITE_DEEPSEEK_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role=roles/secretmanager.secretAccessor \
  --project=st-china-ai-force
```

服务读环境变量顺序：`VITE_DEEPSEEK_API_KEY` → `DEEPSEEK_API_KEY` → `ST_MCU_LLM_KEY`。模型默认 `deepseek-chat`。未绑 secret 或 DeepSeek 不可达时，「填入下方表单」回退关键词抽取。短名单仍走 `/api/recommend`，模型不报料号。
