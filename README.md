# ST MCU Selector

终端用户（硬件/软件工程师、产品主管工程师）完成 MCU 短名单：按需求推荐、竞品对照、查看订货号。计算逻辑与 MCP/skill 相同，使用 ST 公开 `cube-finder-db`。

两种云端部署**分开文档、互不覆盖**：

| 目标 | 入口 | 缓存 | 文档 |
|------|------|------|------|
| Google Cloud Run | 网页 | GCS | [docs/cloud-run/README.md](docs/cloud-run/README.md) |
| 阿里云 SAE | 网页 + 微信小程序 | OSS | [docs/aliyun/README.md](docs/aliyun/README.md) |

小程序不能执行 Claude skill，也不能用未备案的 `*.run.app`。只设一个 bucket 环境变量：`ST_MCU_GCS_BUCKET` 或 `ST_MCU_OSS_BUCKET`，不要同时设。

仓库：https://github.com/Yude-Jiang/st-mcu-selector

## 本地开发

```bash
pip install -r server/requirements.txt
python run.py
# http://127.0.0.1:8080
```

```bash
python -m unittest tests.test_api tests.test_db_cache
```

未设缓存 bucket 时，首次启动从 `sw-center.st.com` 下载器件库到本地（可用 `ST_MCU_DATA_DIR`）。
