# Deploy Smoke and Rollback

本仓库有两套互不覆盖的部署说明：

| 环境 | Smoke / rollback |
|------|------------------|
| Cloud Run + GCS | [cloud-run/deploy-runbook.md](./cloud-run/deploy-runbook.md) |
| 阿里云 SAE + 微信小程序 + OSS | [aliyun/deploy-runbook.md](./aliyun/deploy-runbook.md) |

不要把 Cloud Run 的 URL 配进微信 request 合法域名。
