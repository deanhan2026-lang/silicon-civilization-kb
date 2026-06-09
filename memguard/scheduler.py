#!/usr/bin/env python3
"""
MemGuard-GM 定时校验任务
"""
import sys
import time
import random
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from core import MemGuardEngine, Config, Storage

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('memguard_scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IntegrityChecker:
    """完整性校验器"""
    
    def __init__(self):
        self.engine = MemGuardEngine()
        self.checked_count = 0
        self.frozen_count = 0
    
    def scan_memory_files(self) -> list:
        """扫描记忆文件"""
        memory_dir = Path(Config.MEMORY_DIR)
        if not memory_dir.exists():
            return []
        
        memory_files = []
        for ext in ['.md', '.json', '.txt']:
            memory_files.extend(memory_dir.glob(f'*{ext}'))
        return memory_files
    
    def verify_file(self, file_path: Path) -> tuple:
        """校验单个文件"""
        try:
            content = file_path.read_text(encoding='utf-8')
            # 计算内容Hash（排除元数据行）
            lines = content.split('\n')
            data_lines = [l for l in lines if not l.startswith('#') and not l.startswith('{')]
            data_content = '\n'.join(data_lines)
            
            computed = self.engine.compute_memory_hash(data_content)
            baseline = self.engine.baseline_mgr.read_baseline()
            
            if not baseline.get('sha256'):
                return 'no_baseline', computed
            
            # 对比
            if computed['sha256'] == baseline['sha256']:
                return 'ok', computed
            else:
                return 'mismatch', computed
        except Exception as e:
            return f'error:{str(e)}', None
    
    def run_check(self):
        """执行校验"""
        logger.info('=' * 50)
        logger.info('开始完整性校验')
        
        # 随机延迟（防止时序攻击）
        delay = random.uniform(0, 300)  # 0-5分钟随机
        logger.info(f'随机延迟: {delay:.1f}秒')
        time.sleep(delay)
        
        files = self.scan_memory_files()
        logger.info(f'发现记忆文件: {len(files)}个')
        
        results = {
            'ok': [],
            'mismatch': [],
            'no_baseline': [],
            'error': []
        }
        
        for f in files:
            status, data = self.verify_file(f)
            results[status].append(str(f))
            
            if status == 'mismatch':
                # 冻结该文件关联的记忆
                memory_id = f.stem
                self.engine.status_mgr.freeze(
                    memory_id,
                    f'Hash校验失败: {data["sha256"][:16]}',
                    'validator'
                )
                self.engine.audit_mgr.append(
                    event='integrity_violation',
                    memory_id=memory_id,
                    operator='validator',
                    detail=f'文件{f.name} Hash不匹配'
                )
                logger.warning(f'⚠️  完整性违规: {f.name}')
                self.frozen_count += 1
        
        logger.info(f'校验完成: {len(files)}个文件')
        logger.info(f'  ✅ 正常: {len(results["ok"])}')
        logger.info(f'  ❌ 异常: {len(results["mismatch"])} (已冻结)')
        logger.info(f'  ⭕ 无基线: {len(results["no_baseline"])}')
        
        # 验证审计链
        valid, msg = self.engine.audit_mgr.verify_chain()
        logger.info(f'审计链: {"✅ " + msg if valid else "❌ " + msg}')
        
        self.checked_count = len(files)
        
        return results


def main():
    """主入口"""
    checker = IntegrityChecker()
    results = checker.run_check()
    
    # 汇总报告
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_files': checker.checked_count,
        'frozen': checker.frozen_count,
        'results': results
    }
    
    # 保存报告
    report_file = Path(Config.AUDIT_DIR) / f'check_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    Storage.ensure_dir(str(report_file.parent))
    with open(report_file, 'w', encoding='utf-8') as f:
        import json
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info(f'报告已保存: {report_file}')
    logger.info('校验任务完成')


if __name__ == '__main__':
    main()
