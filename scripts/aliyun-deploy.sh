#!/usr/bin/env bash
# Build the FastAPI image, push to ACR, deploy SAE.
# Required: docker, aliyun CLI, ACR_NAMESPACE
# Optional: SAE_APP_ID (omit on first run — script prints CreateApplication)
set -euo pipefail

ENVIRONMENT="${1:-production}"
REGION="${ALIYUN_REGION:-cn-hangzhou}"
REGISTRY="${ACR_REGISTRY:-registry.${REGION}.aliyuncs.com}"
NAMESPACE="${ACR_NAMESPACE:-}"
APP_NAME="${SAE_APP_NAME:-st-mcu-selector}"
NAMESPACE_ID="${SAE_NAMESPACE_ID:-${REGION}}"
TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M)}"

if [[ -z "$NAMESPACE" ]]; then
  echo "Set ACR_NAMESPACE to your ACR namespace (容器镜像服务命名空间)." >&2
  exit 1
fi

IMAGE="${REGISTRY}/${NAMESPACE}/${APP_NAME}:${TAG}"
IMAGE_LATEST="${REGISTRY}/${NAMESPACE}/${APP_NAME}:latest"
ENVS='[{"name":"PORT","value":"8080"},{"name":"ST_MCU_AUTO_UPDATE","value":"if_missing"},{"name":"FORWARDED_ALLOW_IPS","value":"*"}'
if [[ -n "${ST_MCU_OSS_BUCKET:-}" ]]; then
  OSS_ENDPOINT="${ST_MCU_OSS_ENDPOINT:-https://oss-${REGION}-internal.aliyuncs.com}"
  ENVS="${ENVS},{\"name\":\"ST_MCU_OSS_BUCKET\",\"value\":\"${ST_MCU_OSS_BUCKET}\"},{\"name\":\"ST_MCU_OSS_ENDPOINT\",\"value\":\"${OSS_ENDPOINT}\"},{\"name\":\"ALIYUN_REGION\",\"value\":\"${REGION}\"}"
fi
ENVS="${ENVS}]"
READINESS='{"httpGet":{"path":"/healthz","port":8080,"scheme":"HTTP"},"initialDelaySeconds":90,"timeoutSeconds":5,"periodSeconds":10}'

echo "==> [${ENVIRONMENT}] docker build ${IMAGE}"
docker build -t "$IMAGE" -t "$IMAGE_LATEST" .

if [[ "${SKIP_PUSH:-0}" != "1" ]]; then
  echo "==> docker push"
  docker push "$IMAGE"
  docker push "$IMAGE_LATEST"
fi

if [[ -z "${SAE_APP_ID:-}" ]]; then
  cat <<EOF
==> SAE_APP_ID not set. Create the app once, then rerun with SAE_APP_ID:

aliyun sae CreateApplication \\
  --region ${REGION} \\
  --AppName ${APP_NAME} \\
  --NamespaceId ${NAMESPACE_ID} \\
  --PackageType Image \\
  --ImageUrl ${IMAGE} \\
  --Cpu 1000 \\
  --Memory 2048 \\
  --Replicas 1 \\
  --Port 8080 \\
  --Deploy true \\
  --Envs '${ENVS}' \\
  --TerminationGracePeriodSeconds 30 \\
  --Readiness '${READINESS}'

Then bind an ICP-filed HTTPS domain in SAE (应用设置 → SLB/网关/自定义域名)
and put that host in miniprogram/config.js production + 微信 request 合法域名.
EOF
  exit 0
fi

echo "==> SAE DeployApplication AppId=${SAE_APP_ID}"
aliyun sae DeployApplication \
  --region "$REGION" \
  --AppId "$SAE_APP_ID" \
  --PackageType Image \
  --ImageUrl "$IMAGE" \
  --Deploy true \
  --Envs "$ENVS" \
  --Readiness "$READINESS"

echo "==> Deploy submitted: ${IMAGE}"
echo "Smoke: npm run smoke -- --url=https://<your-icp-domain>"
