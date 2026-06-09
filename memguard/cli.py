#!/usr/bin/env python3
"""
MemGuard-GM CLI 入口
命令行工具
"""
import sys
import argparse
from pathlib import Path

# 确保导入路径正确
sys.path.insert(0, str(Path(__file__).parent))

from core import MemGuardEngine, Config, Storage


def cmd_init(args):
    """初始化"""
    Storage.ensure_dir(Config.BASELINE_DIR)
    Storage.ensure_dir(Config.MEMORY_DIR)
    Storage.ensure_dir(Config.AUDIT_DIR)
    print(f"✅ 初始化完成")
    print(f"   基线目录: {Config.BASELINE_DIR}")
    print(f"   记忆目录: {Config.MEMORY_DIR}")
    print(f"   审计目录: {Config.AUDIT_DIR}")


def cmd_baseline(args):
    """基线管理"""
    engine = MemGuardEngine()
    
    if args.action == 'create':
        if not args.content:
            print("❌ 请提供内容: memguard baseline create <content>")
            return 1
        
        hashes = engine.create_baseline(args.content, 'cli')
        print("✅ 基线创建成功")
        print(f"   SHA256: {hashes['sha256']}")
        print(f"   BLAKE3: {hashes['blake3']}")
        
        if args.lock:
            engine.baseline_mgr.lock()
            print("🔒 基线已锁定")
    
    elif args.action == 'show':
        baseline = engine.baseline_mgr.read_baseline()
        locked = engine.baseline_mgr.is_readonly()
        print(f"基线状态: {'🔒 已锁定' if locked else '🔓 未锁定'}")
        print(f"SHA256: {baseline.get('sha256', 'N/A')}")
        print(f"BLAKE3: {baseline.get('blake3', 'N/A')}")
    
    elif args.action == 'lock':
        engine.baseline_mgr.lock()
        print("🔒 基线已锁定")
    
    elif args.action == 'unlock':
        engine.baseline_mgr.unlock()
        print("🔓 基线已解锁")


def cmd_verify(args):
    """校验记忆"""
    engine = MemGuardEngine()
    
    if args.all:
        from scheduler import IntegrityChecker
        checker = IntegrityChecker()
        results = checker.run_check()
        print(f"\n校验完成:")
        print(f"   正常: {len(results['ok'])}")
        print(f"   异常: {len(results['mismatch'])}")
        print(f"   无基线: {len(results['no_baseline'])}")
        if results['mismatch']:
            print(f"\n⚠️ 以下记忆被篡改:")
            for f in results['mismatch']:
                print(f"   - {f}")
    else:
        print("❌ 请使用 --all 校验所有记忆")


def cmd_freeze(args):
    """冻结记忆"""
    engine = MemGuardEngine()
    engine.status_mgr.freeze(args.memory_id, args.reason or 'CLI冻结', 'cli')
    print(f"🧊 {args.memory_id} 已冻结")
    print(f"   原因: {args.reason or '未指定'}")


def cmd_unfreeze(args):
    """解冻记忆"""
    engine = MemGuardEngine()
    engine.status_mgr.unfreeze(args.memory_id, 'cli')
    print(f"🧊 {args.memory_id} 已解冻")


def cmd_status(args):
    """查看状态"""
    engine = MemGuardEngine()
    
    if args.memory_id:
        status = engine.status_mgr.get_status(args.memory_id)
        print(f"记忆: {args.memory_id}")
        print(f"状态: {status.get('status', 'unknown')}")
        if status.get('frozen_reason'):
            print(f"冻结原因: {status['frozen_reason']}")
    else:
        frozen = engine.status_mgr.get_all_frozen()
        print(f"冻结记忆: {len(frozen)} 条")
        for m in frozen:
            print(f"   - {m}")


def cmd_audit(args):
    """审计日志"""
    engine = MemGuardEngine()
    
    valid, msg = engine.audit_mgr.verify_chain()
    print(f"审计链: {'✅ ' + msg if valid else '❌ ' + msg}")
    
    if args.show:
        logs = engine.audit_mgr.search(limit=args.limit)
        print(f"\n最近 {len(logs)} 条日志:")
        for log in logs:
            print(f"   [{log['ts']}] {log['event']} by {log['operator']}")


def cmd_serve(args):
    """启动API服务"""
    from server import app
    print(f"🚀 启动 MemGuard-GM API 服务")
    print(f"   端口: {args.port}")
    print(f"   调试: {args.debug}")
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)


def main():
    parser = argparse.ArgumentParser(
        description='MemGuard-GM - AI记忆完整性保护系统',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='子命令')
    
    # init
    subparsers.add_parser('init', help='初始化目录')
    
    # baseline
    baseline_parser = subparsers.add_parser('baseline', help='基线管理')
    baseline_parser.add_argument('action', choices=['create', 'show', 'lock', 'unlock'], 
                                  help='操作')
    baseline_parser.add_argument('content', nargs='?', help='基线内容')
    baseline_parser.add_argument('--lock', action='store_true', help='创建后立即锁定')
    
    # verify
    verify_parser = subparsers.add_parser('verify', help='校验记忆')
    verify_parser.add_argument('--all', action='store_true', help='校验所有记忆')
    
    # freeze
    freeze_parser = subparsers.add_parser('freeze', help='冻结记忆')
    freeze_parser.add_argument('memory_id', help='记忆ID')
    freeze_parser.add_argument('--reason', help='冻结原因')
    
    # unfreeze
    unfreeze_parser = subparsers.add_parser('unfreeze', help='解冻记忆')
    unfreeze_parser.add_argument('memory_id', help='记忆ID')
    
    # status
    status_parser = subparsers.add_parser('status', help='查看状态')
    status_parser.add_argument('memory_id', nargs='?', help='记忆ID')
    
    # audit
    audit_parser = subparsers.add_parser('audit', help='审计日志')
    audit_parser.add_argument('--show', action='store_true', help='显示日志')
    audit_parser.add_argument('--limit', type=int, default=10, help='显示条数')
    
    # serve
    serve_parser = subparsers.add_parser('serve', help='启动API服务')
    serve_parser.add_argument('--port', type=int, default=5050, help='端口')
    serve_parser.add_argument('--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        'init': cmd_init,
        'baseline': cmd_baseline,
        'verify': cmd_verify,
        'freeze': cmd_freeze,
        'unfreeze': cmd_unfreeze,
        'status': cmd_status,
        'audit': cmd_audit,
        'serve': cmd_serve,
    }
    
    return commands.get(args.command, lambda a: parser.print_help())(args)


if __name__ == '__main__':
    sys.exit(main() or 0)
