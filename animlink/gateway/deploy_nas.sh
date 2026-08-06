#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# AnimaLink Gateway — NAS 一键部署脚本
# 适用：NAS SSH 登录后执行
# 路径：/home/anima/anima-gateway/
# ─────────────────────────────────────────────────────────────
set -e

GATEWAY_DIR="/home/anima/anima-gateway"
NAS_DATA="/mnt/data/gateway"
ADMIN_KEY="${1:-$(openssl rand -hex 16)}"

echo "═══════════════════════════════════════════"
echo "AnimaLink Gateway — NAS Deployment v1.0"
echo "═══════════════════════════════════════════"
echo "Admin Key: $ADMIN_KEY"
echo "Data Dir:  $NAS_DATA"
echo ""

# ── 1. 目录 ──────────────────────────────────────────────
echo "[1/7] 创建目录..."
mkdir -p "$NAS_DATA"
mkdir -p "$GATEWAY_DIR/gateway"
mkdir -p "$NAS_DATA/gateway_data"

# ── 2. 复制代码（从当前目录） ────────────────────────────
echo "[2/7] 复制代码..."
cp app.py              "$GATEWAY_DIR/"
cp gateway/__init__.py "$GATEWAY_DIR/gateway/"
cp requirements.txt    "$GATEWAY_DIR/"

# ── 3. Python 虚拟环境 ──────────────────────────────────
echo "[3/7] 创建虚拟环境..."
cd "$GATEWAY_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ── 4. 环境变量 ─────────────────────────────────────────
echo "[4/7] 写入 .env..."
cat > "$GATEWAY_DIR/.env" << EOF
GATEWAY_ADMIN_KEY=$ADMIN_KEY
SECRET_KEY=$(openssl rand -hex 24)
PYTHONIOENCODING=utf-8
EOF

# ── 5. Systemd 服务 ────────────────────────────────────
echo "[5/7] 注册 systemd 服务..."
cat > /tmp/animlink-gateway.service << EOF
[Unit]
Description=AnimaLink Gateway
After=network.target

[Service]
Type=simple
User=anima
WorkingDirectory=$GATEWAY_DIR
EnvironmentFile=$GATEWAY_DIR/.env
ExecStart=$GATEWAY_DIR/venv/bin/python -u app.py
Restart=unless-stopped
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

cp /tmp/animlink-gateway.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable animlink-gateway
systemctl restart animlink-gateway

# ── 6. Nginx 反代 ───────────────────────────────────────
echo "[6/7] 配置 Nginx..."
cat > /tmp/gateway-nginx.conf << 'EOF'
upstream gw_backend { server 127.0.0.1:8000; }

server {
    listen 8080;
    server_name _;
    location / {
        proxy_pass         http://gw_backend;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location /socket.io/ {
        proxy_pass         http://gw_backend/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
    }
}
EOF
cp /tmp/gateway-nginx.conf /etc/nginx/sites-available/animlink-gateway
ln -sf /etc/nginx/sites-available/animlink-gateway /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# ── 7. 验证 ─────────────────────────────────────────────
echo "[7/7] 健康检查..."
sleep 3
STATUS=$(curl -s http://localhost:8000/health 2>/dev/null || echo '{"status":"fail"}')
echo "Gateway Health: $STATUS"

if echo "$STATUS" | grep -q '"ok"'; then
    echo ""
    echo "✅ 部署成功！"
    echo "   HTTP API:  http://localhost:8000"
    echo "   WebSocket: ws://localhost:8000"
    echo "   Nginx:     http://localhost:8080"
    echo "   Admin Key: $ADMIN_KEY"
else
    echo ""
    echo "⚠️  Gateway 未响应，检查: journalctl -u animlink-gateway -n 30"
fi
