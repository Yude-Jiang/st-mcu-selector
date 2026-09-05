# 选型服务上 SAE，域名整站指到该应用

目标：容器跑在 SAE，公网 HTTPS 为 `https://mp.microelectronics.com`。小程序和网页都打这个地址。

**切解析前先看一眼：** 云解析里 `mp.microelectronics.com` 当前指到哪。整域名切过来后，原来挂在这个 host 上的站点会停。若还要保留旧站，不要用这篇，改走路径反代。

地域默认 **华东1（杭州）`cn-hangzhou`**，和仓库脚本一致。域名证书、SAE、ACR 选同一地域。

---

## 0. 本机工具

- Docker Desktop 已启动
- [阿里云 CLI](https://help.aliyun.com/zh/cli/install-cli-on-windows) 已安装
- 阿里云账号能开：容器镜像服务 ACR、SAE、云解析 DNS、数字证书

```powershell
aliyun configure
# 选 cn-hangzhou，AccessKey 用 RAM 子账号（AliyunSAEFullAccess + AliyunContainerRegistryFullAccess）
docker login --username=<阿里云账号> registry.cn-hangzhou.aliyuncs.com
```

---

## 1. 控制台一次性准备

### ACR（镜像仓库）

1. 容器镜像服务 → 实例（个人版即可）→ 命名空间 **`st-mcu-selector`**
2. 仓库名 **`st-mcu-selector`**（公开/私有均可；私有则 SAE 要配 ACR 密码或 RAM）

### 证书（HTTPS）

1. 数字证书管理服务 → 看是否已有 `mp.microelectronics.com` 或 `*.microelectronics.com`
2. 没有就申请（已备案域名可申请免费 DV），签发后记下证书 ID

### VPC

SAE 必须进 VPC。用已有生产 VPC，或新建后给 **公网出方向**（首次启动要从 `sw-center.st.com` 拉器件库）。

OSS 缓存可第二步再做，第一次允许启动时直拉 ST 包。

---

## 2. 构建并推镜像

在仓库根目录：

```powershell
$env:ACR_NAMESPACE = "st-mcu-selector"
$env:ALIYUN_REGION = "cn-hangzhou"
python -m unittest tests.test_api tests.test_db_cache
.\scripts\aliyun-deploy.ps1 production
```

第一次没有 `SAE_APP_ID` 时，脚本会 **push 镜像并打印 CreateApplication**，不会自动建应用。

---

## 3. 用 YAML 创建 SAE 应用（对应控制台「YAML创建」）

镜像推完后，**不要用 default 命名空间**（它已绑定别的 VPC，再填你的 VpcId 会报 `invalid params VpcId`）。

1. SAE 左侧 **命名空间** → 创建：名称 `st-mcu-selector`，VPC 选 `st-mcu-selector`（或先 YAML 上传 `docs/aliyun/sae-namespace.yaml`）  
2. 再 YAML创建，上传 `docs/aliyun/sae-application.yaml`（`namespace: st-mcu-selector`）

1. 网络三项已写入 YAML。确认 ACR 镜像 `st-mcu-selector/st-mcu-selector:latest` 已推送后，直接上传该文件创建应用  
2. `metadata.namespace` 只填短名，例如 `default`（不要写成 `cn-hangzhou:default`）  
3. 点创建。域名 `mp.microelectronics.com` **不写在这份 YAML 里**，应用 Running 后再按第 4 步绑 CLB/证书/DNS  

私有 ACR 仓库：创建前在 SAE 命名空间里授权拉镜像，否则会 ImagePullBackOff。

创建成功后，应用详情顶部复制 **App ID**，以后发布：

```powershell
$env:SAE_APP_ID = "<粘贴 App ID>"
$env:ACR_NAMESPACE = "st-mcu-selector"
.\scripts\aliyun-deploy.ps1 production
```

等实例变 Running。第一次 `/healthz` 可能 503，下完库变为 200。

---

## 4. 公网访问 + 绑定域名

1. 应用详情 → **访问设置**（或「添加公网 CLB」）→ 开启公网
2. 监听：
   - HTTP **80** → 后端 **8080**
   - HTTPS **443** → 后端 **8080**，证书选 `mp.microelectronics.com`
3. **绑定域名** 填 `mp.microelectronics.com`
4. 页面会给出 CLB 的 **CNAME** 或 **IP**，复制下来

### 云解析 DNS

产品：**云解析 DNS** → `microelectronics.com` → `mp` 这一条：

- 有 CNAME 目标：类型 **CNAME**，主机记录 `mp`，值填 SAE/CLB 给的 CNAME（末尾带不带点按控制台提示）
- 只有 IP：类型 **A**，主机记录 `mp`，值填 CLB IP

TTL 可先 10 分钟，切完再改长。保存后等解析生效（几分钟到几十分钟）。

```powershell
nslookup mp.microelectronics.com
curl -I https://mp.microelectronics.com/healthz
curl https://mp.microelectronics.com/api/health
```

`/healthz` 为 `ok`、`/api/health` 为 JSON 即成功。网页打开根路径应看到 ST MCU Selector。

```powershell
npm run smoke -- --url=https://mp.microelectronics.com
```

---

## 5. 给小程序供应商

微信公众平台 → 开发 → 开发管理 → 服务器域名 → request 合法域名：

`mp.microelectronics.com`

基址：`https://mp.microelectronics.com`（`miniprogram/config.js` 的 production 已写好）。体验版把 `ENV` 改为 `production`，并关闭「不校验合法域名」。

---

## 常见失败

| 现象 | 处理 |
|------|------|
| 实例 OOM / 一直 Starting | 内存改为 2Gi；就绪检查延迟 ≥ 90s |
| `/healthz` 一直 503 | 看 SAE 日志是否拉不到 `sw-center.st.com`（VPC 无出网） |
| HTTPS 证书名称不匹配 | 证书必须覆盖 `mp.microelectronics.com` |
| 微信真机 `url not in domain list` | 合法域名只填 host；改完域名要等微信缓存（可删体验版重进） |
| 旧业务 404/连不上 | `mp` 解析已被切走，从 DNS 记录历史找回旧目标 |
