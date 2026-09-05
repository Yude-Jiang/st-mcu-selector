# ST MCU Selector

终端用户（硬件/软件工程师、产品主管工程师）在网页或微信小程序上完成 MCU 短名单：按需求推荐、竞品对照、查看订货号。计算逻辑与 MCP/skill 相同，使用 ST 公开 `cube-finder-db`。

小程序不能直接执行 Claude skill。三种查询已做成 HTTP API，表单提交后拿到同一套短名单。

| 入口 | 调用 |
|------|------|
| 微信小程序表单 | `wx.request` → 阿里云 SAE HTTPS |
| 网页表单 | `fetch` → 同一 API |
| ChatGPT MCP | 仍走引擎，不作为终端用户入口 |

## 本地开发

```bash
pip install -r server/requirements.txt
python run.py
# http://127.0.0.1:8080
```

首次启动会从 `sw-center.st.com` 下载器件库；生产建议设 `ST_MCU_OSS_BUCKET`，冷启动走 OSS 缓存。

### 微信开发者工具

1. 导入本仓库，`project.config.json` 已指向 `miniprogram/`
2. 详情 → 本地设置：勾选不校验合法域名、web-view、TLS
3. `miniprogram/config.js` 开发环境默认 `http://127.0.0.1:8080`
4. 真机预览把 `apiBase` 改成电脑局域网 IP，例如 `http://192.168.1.8:8080`

把 `appid` 换成你们的小程序 AppID 后再上传体验版。

## 阿里云部署（SAE + ACR）

不使用 Google Cloud。镜像推到容器镜像服务 ACR，应用跑在 SAE，端口 **8080**，内存 2Gi，单实例。

```powershell
# 一次性：aliyun configure；docker login registry.cn-hangzhou.aliyuncs.com
$env:ACR_NAMESPACE = "<your-acr-namespace>"
$env:ALIYUN_REGION = "cn-hangzhou"
$env:ST_MCU_OSS_BUCKET = "<oss-bucket>"
# 第二次起：
# $env:SAE_APP_ID = "<sae-app-id>"
python -m unittest tests.test_api
.\scripts\aliyun-deploy.ps1 production
```

```bash
export ACR_NAMESPACE=<your-acr-namespace>
export ALIYUN_REGION=cn-hangzhou
# export SAE_APP_ID=<sae-app-id>
python -m unittest tests.test_api
bash scripts/aliyun-deploy.sh production
```

首次未设 `SAE_APP_ID` 时，脚本会打印 `CreateApplication`。创建后：

1. SAE 绑定**已 ICP 备案**的 HTTPS 自定义域名（微信不接受未备案域名，也不接受 `*.run.app`）
2. 微信公众平台 → 开发 → 开发管理 → 服务器域名：把该 host 填入 **request 合法域名**
3. `miniprogram/config.js` 把 `ENV` 改为 `production`，`HOSTS.production` 写成该 HTTPS 地址
4. 上传小程序代码

Health: `/healthz`（器件库未就绪时 503）

Smoke:

```bash
npm run smoke -- --url=https://<your-icp-domain>
```
