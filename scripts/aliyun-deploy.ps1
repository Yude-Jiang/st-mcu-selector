# Build FastAPI image, push ACR, deploy SAE.
# Required: docker, aliyun CLI, ACR_NAMESPACE
# Optional: SAE_APP_ID
param(
  [string]$Environment = "production"
)

$ErrorActionPreference = "Stop"
$Region = if ($env:ALIYUN_REGION) { $env:ALIYUN_REGION } else { "cn-hangzhou" }
$Registry = if ($env:ACR_REGISTRY) { $env:ACR_REGISTRY } else { "registry.$Region.aliyuncs.com" }
$Namespace = $env:ACR_NAMESPACE
$AppName = if ($env:SAE_APP_NAME) { $env:SAE_APP_NAME } else { "st-mcu-selector" }
$NamespaceId = if ($env:SAE_NAMESPACE_ID) { $env:SAE_NAMESPACE_ID } else { $Region }
$Tag = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else {
  try { (git rev-parse --short HEAD).Trim() } catch { Get-Date -Format "yyyyMMddHHmm" }
}

if (-not $Namespace) {
  throw "Set ACR_NAMESPACE to your ACR namespace."
}

$Image = "$Registry/$Namespace/${AppName}:$Tag"
$ImageLatest = "$Registry/$Namespace/${AppName}:latest"
$Envs = '[{"name":"PORT","value":"8080"},{"name":"ST_MCU_AUTO_UPDATE","value":"if_missing"},{"name":"FORWARDED_ALLOW_IPS","value":"*"}'
if ($env:ST_MCU_OSS_BUCKET) {
  $OssEndpoint = if ($env:ST_MCU_OSS_ENDPOINT) { $env:ST_MCU_OSS_ENDPOINT } else { "https://oss-$Region-internal.aliyuncs.com" }
  $Envs += ",{`"name`":`"ST_MCU_OSS_BUCKET`",`"value`":`"$($env:ST_MCU_OSS_BUCKET)`"},{`"name`":`"ST_MCU_OSS_ENDPOINT`",`"value`":`"$OssEndpoint`"},{`"name`":`"ALIYUN_REGION`",`"value`":`"$Region`"}"
}
$Envs += "]"
$Readiness = '{"httpGet":{"path":"/healthz","port":8080,"scheme":"HTTP"},"initialDelaySeconds":90,"timeoutSeconds":5,"periodSeconds":10}'

Write-Host "==> [$Environment] docker build $Image"
docker build -t $Image -t $ImageLatest .

if ($env:SKIP_PUSH -ne "1") {
  Write-Host "==> docker push"
  docker push $Image
  docker push $ImageLatest
}

if (-not $env:SAE_APP_ID) {
  Write-Host @"
==> SAE_APP_ID not set. Create the app once, then rerun with SAE_APP_ID:

aliyun sae CreateApplication --region $Region --AppName $AppName --NamespaceId $NamespaceId --PackageType Image --ImageUrl $Image --Cpu 1000 --Memory 2048 --Replicas 1 --Port 8080 --Deploy true --Envs '$Envs' --TerminationGracePeriodSeconds 30 --Readiness '$Readiness'

Bind an ICP-filed HTTPS domain, then set miniprogram/config.js production + WeChat request 合法域名.
"@
  exit 0
}

Write-Host "==> SAE DeployApplication AppId=$($env:SAE_APP_ID)"
aliyun sae DeployApplication --region $Region --AppId $env:SAE_APP_ID --PackageType Image --ImageUrl $Image --Deploy true --Envs $Envs --Readiness $Readiness
Write-Host "==> Deploy submitted: $Image"
