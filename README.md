# ST MCU Selector

终端用户（硬件/软件工程师、产品主管工程师）在网页上完成 MCU 短名单：按需求推荐、竞品对照、查看订货号。计算逻辑与 MCP 相同，使用 ST 公开 `cube-finder-db`.

## Quick Start

```bash
pip install -r server/requirements.txt
cd server
python -m bootstrap
# http://127.0.0.1:8080
```

首次启动会从 `sw-center.st.com` 下载器件库到 `/data`（本地默认也可用 `ST_MCU_DATA_DIR`）。

## Cloud Run

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
  --set-env-vars ST_MCU_TRUST_PROXY=true,FORWARDED_ALLOW_IPS=*
```

Health: `/healthz`  （器件库未就绪时返回 503）
