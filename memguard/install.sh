#!/bin/bash
# MemGuard-GM Linux/macOS 一键安装脚本

set -e

echo "======================================"
echo "  MemGuard-GM 跨平台安装"
echo "======================================"
echo ""

# 检测平台
PLATFORM="$(uname -s)"
echo "平台: $PLATFORM"

# 检测Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    if [ "$PLATFORM" == "Linux" ]; then
        echo "   Ubuntu/Debian: sudo apt install python3 python3-pip"
        echo "   CentOS/RHEL:   sudo yum install python3 python3-pip"
    elif [ "$PLATFORM" == "Darwin" ]; then
        echo "   macOS: brew install python3"
    fi
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✅ Python: $PYTHON_VERSION"

# 安装依赖
echo ""
echo "📦 安装依赖..."
pip3 install blake3 flask flask-cors --quiet

# 创建目录
echo ""
echo "📁 创建目录..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$BASE_DIR/memguard_baseline"
mkdir -p "$BASE_DIR/memory"
mkdir -p "$BASE_DIR/audit"
mkdir -p "$BASE_DIR/backup"

echo "   ✅ 基线目录: $BASE_DIR/memguard_baseline"
echo "   ✅ 记忆目录: $BASE_DIR/memory"
echo "   ✅ 审计目录: $BASE_DIR/audit"

# 创建cron任务
echo ""
echo "⏰ 设置定时校验任务..."
INSTALL_CRON_SCRIPT="$SCRIPT_DIR/install_cron.sh"
if [ -f "$INSTALL_CRON_SCRIPT" ]; then
    chmod +x "$INSTALL_CRON_SCRIPT"
    echo "   运行 $INSTALL_CRON_SCRIPT 4h 来设置定时任务"
fi

echo ""
echo "======================================"
echo "✅ 安装完成!"
echo "======================================"
echo ""
echo "下一步:"
echo "----------------------------------------"
echo "1. 创建基线:"
echo "   cd $SCRIPT_DIR"
echo "   python3 -m memguard.cli baseline create \"初始内容\""
echo ""
echo "2. 启动API服务:"
echo "   python3 $SCRIPT_DIR/server.py"
echo ""
echo "3. 设置定时校验 (Linux/macOS):"
echo "   bash $INSTALL_CRON_SCRIPT 4h"
echo ""
