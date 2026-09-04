# Deploy Smoke and Rollback Runbook

Service: `st-mcu-selector` in `st-china-ai-force` / `asia-east1`, port 8080.

This runbook standardizes post-deploy verification and rollback actions for Cloud Run deployments.

## 1) Post-deploy smoke checklist

Run after each staging or production deploy:

```bash
npm run smoke -- --url=https://<your-cloud-run-url>
```

Expected:
- Homepage returns `200` and includes `id="root"` plus ST MCU Selector.
- `/healthz` either returns `200` (if implemented) or `404` (accepted for current version).

If smoke fails:
1. Stop promotion to next environment.
2. Capture failing output in release notes.
3. Execute rollback procedure below.

## 2) Rollback procedure (Cloud Run)

### Option A: Roll back to previous stable revision

```bash
gcloud run revisions list --service=st-mcu-selector --region=asia-east1
gcloud run services update-traffic st-mcu-selector --region=asia-east1 --to-revisions=<stable-revision>=100
```

### Option B: Roll back by image tag

```bash
gcloud run deploy <service-name> \
  --region=<region> \
  --image=<registry>/<project>/<image>:<previous-tag>
```

## 3) Post-rollback validation

1. Re-run smoke checks:

```bash
npm run smoke -- --url=https://<your-cloud-run-url>
```

2. Verify critical user flow manually:
- Dashboard loads
- AI Probe can open
- Data Operations page can read data

3. Log incident summary in weekly status report (`npm run kpi:report` output file).
