# Deploy Smoke and Rollback — 阿里云 SAE

Service: SAE `st-mcu-selector`，默认 region `cn-hangzhou`，port 8080。镜像在 ACR。器件库缓存：OSS。

网页 + 微信小程序共用此后端。Cloud Run 回滚见 [`../cloud-run/deploy-runbook.md`](../cloud-run/deploy-runbook.md)。

## 1) Post-deploy smoke

```bash
npm run smoke -- --url=https://<your-icp-domain>
```

Expected:

- Homepage `200`，含 `id="root"` 与 ST MCU Selector
- `/healthz` 器件库就绪为 `200`，首次加载可为 `503`
- `/api/health` 含 `cache.source`（`oss` | `st` | `local`）与 `cache.stale`

## 2) Rollback

### Option A: 控制台

SAE 应用 → 变更单 / 版本 → 回滚到上一稳定版本。

### Option B: 上一镜像 tag

```bash
aliyun sae DeployApplication \
  --region cn-hangzhou \
  --AppId <sae-app-id> \
  --PackageType Image \
  --ImageUrl registry.cn-hangzhou.aliyuncs.com/<namespace>/st-mcu-selector:<previous-tag> \
  --Deploy true
```

## 3) Post-rollback

1. 再跑 smoke
2. 网页三种表单仍能出短名单
3. 微信开发者工具对同一域名 `wx.request` 成功（生产需已配合法域名）
