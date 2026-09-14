# 阿里云 SAE + 微信小程序

中国区终端入口：网页与微信小程序共用同一套 FastAPI（recommend / compare / inspect）。

生产域名（已 ICP、阿里云）：**`https://mp.microelectronics.com`**  
微信 request 合法域名只填 host：`mp.microelectronics.com`。

**把域名整站指到 SAE：** 按 [sae-bind-domain.md](./sae-bind-domain.md) 做（ACR → 推镜像 → 建应用 → CLB/证书 → 改 `mp` 解析）。

器件库缓存用 **OSS**（`ST_MCU_OSS_BUCKET`）可第二步再加，不要设 `ST_MCU_GCS_BUCKET`。

Cloud Run / GCS 说明见 [`../cloud-run/README.md`](../cloud-run/README.md)。

## 小程序形态：web-view 内嵌同一个网页

首页 `pages/web/index` 是一个 `web-view`，直接内嵌 `webBase` 指向的网页，**和 Cloud Run / SAE 上跑的是同一套前端**。这样两端不会再各写一份 UI 然后慢慢跑偏。原生表单页 `pages/index/index` 仍保留在 `app.json` 里，把它挪回数组第一位就切回去，不用重写。

### 两条域名配置是独立的，别混

| 配置项 | 用途 | 公众平台位置 |
|--------|------|--------------|
| `apiBase` → request 合法域名 | `wx.request` 调 `/api/*` | 开发管理 → 开发设置 → 服务器域名 |
| `webBase` → **业务域名** | `web-view` 内嵌网页 | 开发管理 → 开发设置 → **业务域名** |

业务域名要单独配，而且**必须把校验文件下载下来放到域名根目录**（`https://mp.microelectronics.com/<校验文件名>.txt` 能直接访问才算通过）。只填 host，不带 `https://` 和路径。

SAE 侧要保证这个校验文件可访问：如果只反代了 `/api/*` 和 `/healthz`，校验文件会 404，业务域名就配不上。

## 微信开发者工具（本地验证）

1. 导入仓库根目录，`project.config.json` 已指向 `miniprogram/`
2. 详情 → 本地设置：勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」
3. `miniprogram/config.js` 的 `develop` 里 `web` 指向 Cloud Run，工具里能直接内嵌
4. **真机预览内嵌不了 Cloud Run**——`*.run.app` 没有 ICP 备案，配不成业务域名。真机要等 `mp.microelectronics.com` 上线并配好业务域名
5. `apiBase` 的 `develop` 是 `http://127.0.0.1:8080`；真机预览要改成电脑局域网 IP，例如 `http://192.168.1.8:8080`
6. 把 `appid` 从 `touristappid` 换成真实 AppID 后才能上传体验版（游客态不能上传）

### web-view 的几个硬约束

- 一个页面里 `web-view` 会占满，不能和别的组件混排。所以加载失败时是整页替换成原生兜底视图，不是浮层
- 只能内嵌 `https`，`http` 一律不行（工具里也不行）
- 网页里想调 `wx.miniProgram.*`（如 `navigateBack`）要先引微信的 JS-SDK；目前是纯展示，没引

## OSS 缓存桶（冷启动）

```bash
# 按控制台或 aliyun oss 建专用桶，region 与 SAE 一致（默认 cn-hangzhou）
# 对象由应用写入：cube-finder-db/current.json 与 objects/<sha256>/cube-finder-db.db
```

ETag 与 ST zip 一致则从 OSS 拷贝；变化则拉新包、写新对象、再改 pointer。ST 不可达时用上一份，`/api/health` 里 `cache.stale=true`。

## 部署（SAE + ACR）

```powershell
# 一次性：aliyun configure；docker login registry.cn-hangzhou.aliyuncs.com
$env:ACR_NAMESPACE = "st-mcu-selector"
$env:ALIYUN_REGION = "cn-hangzhou"
$env:ST_MCU_OSS_BUCKET = "<oss-bucket>"
# 第二次起：
# $env:SAE_APP_ID = "<sae-app-id>"
python -m unittest tests.test_api tests.test_db_cache
.\scripts\aliyun-deploy.ps1 production
```

```bash
export ACR_NAMESPACE=st-mcu-selector
export ALIYUN_REGION=cn-hangzhou
export ST_MCU_OSS_BUCKET=<oss-bucket>
# export SAE_APP_ID=<sae-app-id>
python -m unittest tests.test_api tests.test_db_cache
bash scripts/aliyun-deploy.sh production
```

首次未设 `SAE_APP_ID` 时，脚本会打印 `CreateApplication`。创建后：

1. SAE / SLB / 网关把 `mp.microelectronics.com` 指到本服务（若域名上已有站点，只反代 `/api/*` 与 `/healthz`）
2. 微信公众平台 request 合法域名：`mp.microelectronics.com`
3. 微信公众平台 **业务域名**：`mp.microelectronics.com`，并把校验文件放到域名根目录
4. 体验版把 `miniprogram/config.js` 的 `ENV` 改为 `production`（`apiBase` 与 `webBase` 一起切到 `https://mp.microelectronics.com`）
5. 上传小程序代码

Health: `/healthz`（器件库未就绪时 503）。Smoke 与回滚见 [deploy-runbook.md](./deploy-runbook.md)。
