#!/usr/bin/env python3
"""
MemGuard-GM 跨平台安装脚本
支持 Linux / macOS / Windows
"""
import sys
import os
import subprocess
import platform
from pathlib import Path

REQUIREMENTS = [
    'blake3>=1.0.0',
    'flask>=2.0',
    'flask-cors>=3.0'
]

INSTALL_CMD = {
    'Linux': {
        'package': 'python3-pip',
        'install': 'pip3 install -e .'
    },
    'Darwin': {
        'package': 'python3',
        'install': 'pip3 install -e .'
    },
    'Windows': {
        'package': 'python',
        'install': 'pip install -e .'
    }
}


def get_platform():
    """获取平台信息"""
    system = platform.system()
    return {
        'system': system,
        'python': sys.executable,
        'pip': 'pip' if system == 'Windows' else 'pip3'
    }


def check_python():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required, got {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def install_dependencies():
    """安装依赖"""
    print("\n📦 安装依赖...")
    for req in REQUIREMENTS:
        print(f"   安装 {req}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', req], 
                                stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️ 安装失败: {req}")
            return False
    return True


def create_directories():
    """创建默认目录"""
    print("\n📁 创建目录...")
    base = Path(__file__).parent.parent
    dirs = ['memguard_baseline', 'memory', 'audit', 'backup']
    for d in dirs:
        p = base / d
        p.mkdir(parents=True, exist_ok=True)
        print(f"   ✅ {p}")


def create_env_file():
    """创建环境变量配置示例"""
    print("\n⚙️ 创建配置示例...")
    base = Path(__file__).parent.parent
    env_example = base / '.env.example'
    
    content = """# MemGuard-GM 配置示例
# 复制为 .env 并修改

# 基线存储路径
MEMGUARD_BASELINE_DIR=./memguard_baseline

# 记忆文件目录
MEMGUARD_MEMORY_DIR=./memory

# 审计日志目录
MEMGUARD_AUDIT_DIR=./audit

# 备份目录
MEMGUARD_BACKUP_DIR=./backup

# 校验间隔（秒），默认4小时
MEMGUARD_CHECK_INTERVAL=14400

# 随机延迟上限（秒），默认5分钟
MEMGUARD_RANDOM_DELAY=300

# 是否允许基线解锁（生产环境设为false）
MEMGUARD_ALLOW_UNLOCK=false

# API配置
MEMGUARD_API_HOST=0.0.0.0
MEMGUARD_API_PORT=5050
"""
    env_example.write_text(content)
    print(f"   ✅ {env_example}")
    print("   📝 请复制为 .env 文件并修改")


def create_cron_script():
    """创建cron安装脚本"""
    print("\n⏰ 创建定时任务...")
    base = Path(__file__).parent.parent
    
    # Linux/Mac cron脚本
    cron_script = base / 'install_cron.sh'
    content = """#!/bin/bash
# MemGuard-GM 定时校验任务安装脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTERVAL=${1:-4h}

case $INTERVAL in
    1h) SECONDS=3600 ;;
    2h) SECONDS=7200 ;;
    4h) SECONDS=14400 ;;
    8h) SECONDS=28800 ;;
    24h) SECONDS=86400 ;;
    *) SECONDS=14400 ;;
esac

# 创建定时任务
(crontab -l 2>/dev/null | grep -v memguard; echo "0 */$((SECONDS/3600)) * * * cd $SCRIPT_DIR/memguard && python3 scheduler.py >> memguard.log 2>&1") | crontab -

echo "✅ MemGuard-GM 定时任务已安装 (每$INTERVAL)"
echo "📋 查看任务: crontab -l"
echo "📋 查看日志: tail -f $SCRIPT_DIR/memguard.log"
"""
    cron_script.write_text(content)
    os.chmod(cron_script, 0o755)
    print(f"   ✅ {cron_script}")


def create_windows_scheduler():
    """创建Windows计划任务脚本"""
    print("\n⏰ 创建Windows定时任务...")
    base = Path(__file__).parent.parent
    
    ps_script = base / 'memguard' / 'setup_scheduler.ps1'
    
    # 读取现有脚本，在末尾追加安装提示
    print(f"   ℹ️  Windows定时任务脚本已存在:")
    print(f"      {ps_script}")


def print_next_steps():
    """打印下一步"""
    base = Path(__file__).parent
    plat = get_platform()
    
    print("\n" + "="*50)
    print("🎉 安装完成!")
    print("="*50)
    print()
    print("下一步:")
    print("="*50)
    
    if plat['system'] == 'Windows':
        print("""
1. 创建基线:
   cd memguard
   python core.py baseline_create "初始内容"

2. 启动API服务:
   python server.py

3. 设置定时校验:
   powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1
""")
    else:
        print(f"""
1. 创建基线:
   cd {base}
   python3 memguard/core.py baseline_create "初始内容"

2. 启动API服务:
   python3 memguard/server.py

3. 设置定时校验:
   bash install_cron.sh 4h
""")


def main():
    print("="*50)
    print("   MemGuard-GM 跨平台安装")
    print("="*50)
    print()
    
    # 平台检测
    plat = get_platform()
    print(f"平台: {plat['system']}")
    print(f"Python: {plat['python']}")
    print()
    
    # 检查Python
    if not check_python():
        sys.exit(1)
    
    # 安装依赖
    if not install_dependencies():
        print("⚠️ 依赖安装失败，但可以继续...")
    
    # 创建目录
    create_directories()
    
    # 创建配置
    create_env_file()
    
    # 创建定时任务脚本
    if plat['system'] != 'Windows':
        create_cron_script()
    else:
        create_windows_scheduler()
    
    # 打印下一步
    print_next_steps()


if __name__ == '__main__':
    main()
