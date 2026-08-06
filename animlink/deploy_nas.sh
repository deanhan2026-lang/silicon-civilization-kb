#!/bin/bash
# AnimaLink Gateway — NAS 部署脚本
# 用法: bash deploy_nas.sh [build|start|stop|restart|logs|status]
# 需要先通过 SSH 复制到 NAS: scp -r animlink/ anima@100.107.156.33:/opt/

set -e

CMD=${1:-build}
IMAGE="animlink-gateway:latest"
CONTAINER="animlink-gateway"
APP_DIR="/opt/animlink-gateway"

NAS_GATEWAY_PATH="/mnt/data/qclaw/gateway"

# 确保数据目录存在
ssh anima@100.107.156.33 "mkdir -p $NAS_GATEWAY_PATH"

build() {
    echo ">>> Building Docker image..."
    docker build -t $IMAGE $APP_DIR
    echo ">>> Done: $IMAGE"
}

start() {
    echo ">>> Starting AnimaLink Gateway..."
    NAS_ROOT=$NAS_GATEWAY_PATH \
    GATEWAY_ADMIN_KEY=${GATEWAY_ADMIN_KEY:-changeme} \
    docker compose -f $APP_DIR/docker-compose.yml up -d
    echo ">>> Gateway started on port 8000 (HTTP) + 8001 (WS)"
}

stop() {
    echo ">>> Stopping..."
    docker compose -f $APP_DIR/docker-compose.yml down
}

restart() {
    stop; start
}

logs() {
    docker compose -f $APP_DIR/docker-compose.yml logs -f
}

status() {
    docker compose -f $APP_DIR/docker-compose.yml ps
    echo ""
    echo ">>> Health check:"
    curl -s http://localhost:8000/health || echo "FAIL: Gateway unreachable"
}

case $CMD in
    build)  build ;;
    start)  start ;;
    stop)   stop ;;
    restart) restart ;;
    logs)   logs ;;
    status) status ;;
    *)      echo "Usage: $0 {build|start|stop|restart|logs|status}" ;;
esac
