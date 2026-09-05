# Deploy Smoke and Rollback Runbook

Service: 阿里云 SAE `st-mcu-selector`，默认 region `cn-hangzhou`，port 8080。镜像在 ACR。

## 1) Post-deploy smoke checklist

Run after each staging or production deploy:

```bash
npm run smoke -- --url=https://<your-icp-domain>
```

Expected:
- Homepage returns `200` and includes `id="root"` plus ST MCU Selector.
- `/healthz` returns `200` when the MCU database is ready (`503` only during first-load).

If smoke fails:
1. Stop promotion to next environment.
2. Capture failing output in release notes.
3. Execute rollback procedure below.

## 2) Rollback procedure (SAE)

### Option A: Roll back in console

SAE 应用 → 变更单 / 版本 → 回滚到上一稳定版本。

### Option B: Redeploy previous image tag

```bash
aliyun sae DeployApplication \
  --region cn-hangzhou \
  --AppId <sae-app-id> \
  --PackageType Image \
  --ImageUrl registry.cn-hangzhou.aliyuncs.com/<namespace>/st-mcu-selector:<previous-tag> \
  --Deploy true
```

## 3) Post-rollback validation

1. Re-run smoke checks:

```bash
npm run smoke -- --url=https://<your-icp-domain>
```

2. Verify critical user flow:
- 网页三种表单仍能出短名单
- 微信开发者工具对同一域名 `wx.request` 成功（生产需已配合法域名）

3. Log incident summary in weekly status report (`npm run kpi:report` output file).
