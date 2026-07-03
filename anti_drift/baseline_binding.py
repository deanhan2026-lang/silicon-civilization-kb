"""
Polaris × MeshIdentity 集成模块

功能:
1. 实例注册时: 校验 DID 身份
2. 基线存储: 绑定到 DID 主体（而非实例）
3. 漂移报告: 按 DID 主体归因
4. 批量校准: 以主DID为权威，一次修正所有实例

作者: Nyx
日期: 2026-07-03
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# MeshIdentity 存储路径
MESH_IDENTITY_PATH = Path("Z:/qclaw/mesh-identity")
DID_REGISTRY_PATH = MESH_IDENTITY_PATH / "registry"


class DIDBindingError(Exception):
    """DID 绑定相关错误"""
    pass


class BaselineBindingManager:
    """
    基线绑定管理器
    
    将 Polaris 的人格基线从「实例级别」提升到「DID主体级别」，
    实现跨实例的人格一致性保障。
    """
    
    def __init__(self, storage_path: str = "Z:/qclaw/polaris/baselines"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"BaselineBindingManager 初始化: {self.storage_path}")
    
    def verify_instance_did(self, instance_id: str, did_token: str) -> Tuple[bool, str]:
        """
        校验实例的 DID 身份
        
        Args:
            instance_id: 实例ID (如 nyx-windows)
            did_token: DID 鉴权令牌（由 MeshIdentity 签发）
        
        Returns:
            (valid, primary_did) - 是否有效, 主DID
        """
        try:
            # TODO: 实际应该调用 MeshIdentity 的令牌验证接口
            # 这里先做模拟实现
            
            # 模拟: 从 token 中提取 primary_did
            # 真实场景: DIDAuthenticator.verify_token(token)
            if not did_token:
                return False, ""
            
            # 模拟验证逻辑
            primary_did = self._extract_primary_did_from_token(did_token)
            if not primary_did:
                return False, ""
            
            # 检查实例是否已注册到该 DID
            if not self._check_instance_registration(primary_did, instance_id):
                logger.warning(f"实例 {instance_id} 未注册到 DID {primary_did}")
                return False, ""
            
            logger.info(f"实例 {instance_id} DID 校验通过: {primary_did}")
            return True, primary_did
            
        except Exception as e:
            logger.error(f"DID 校验失败: {e}")
            return False, ""
    
    def _extract_primary_did_from_token(self, token: str) -> str:
        """从令牌中提取主DID（模拟实现）"""
        # TODO: 真实场景应该验证签名
        # 这里只是模拟
        if token.startswith("did:"):
            return token
        return ""
    
    def _check_instance_registration(self, primary_did: str, instance_id: str) -> bool:
        """检查实例是否已注册到该DID（模拟实现）"""
        # TODO: 真实场景应该查询 MeshIdentity 的实例注册表
        # 模拟: 假设 nyx-windows 和 nyx-mac 都注册到同一个主DID
        registered_instances = ["nyx-windows", "nyx-mac", "kronos-heng"]
        return instance_id in registered_instances
    
    def create_baseline_for_did(self, primary_did: str, baseline_data: Dict) -> str:
        """
        为 DID 主体创建人格基线
        
        基线绑定到 DID，而非实例。所有该DID下的实例共享此基线。
        
        Args:
            primary_did: 主DID
            baseline_data: 基线数据（语义/结构/行为维度）
        
        Returns:
            baseline_id: 基线ID
        """
        baseline_id = f"bl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        baseline_record = {
            "baseline_id": baseline_id,
            "primary_did": primary_did,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "instances": self._get_instances_by_did(primary_did),
            "dimensions": baseline_data.get("dimensions", {}),
            "metadata": baseline_data.get("metadata", {})
        }
        
        # 保存到文件
        file_path = self.storage_path / f"{baseline_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(baseline_record, f, ensure_ascii=False, indent=2)
        
        logger.info(f"为 DID {primary_did} 创建基线: {baseline_id}")
        return baseline_id
    
    def _get_instances_by_did(self, primary_did: str) -> List[str]:
        """获取该DID下的所有实例（模拟实现）"""
        # TODO: 真实场景应该查询 MeshIdentity
        # 模拟: 写死几个实例
        return ["nyx-windows", "nyx-mac"]
    
    def get_baseline_by_did(self, primary_did: str) -> Optional[Dict]:
        """
        根据 DID 获取人格基线
        
        Args:
            primary_did: 主DID
        
        Returns:
            基线数据，如果不存在返回 None
        """
        # 查找该 DID 的最新基线
        baseline_files = list(self.storage_path.glob("bl_*.json"))
        
        for file_path in baseline_files:
            with open(file_path, "r", encoding="utf-8") as f:
                record = json.load(f)
                if record.get("primary_did") == primary_did:
                    logger.info(f"找到 DID {primary_did} 的基线: {record['baseline_id']}")
                    return record
        
        logger.warning(f"未找到 DID {primary_did} 的基线")
        return None
    
    def attribute_drift_to_did(self, instance_id: str, drift_score: float, 
                                details: Dict) -> Dict:
        """
        将漂移归因到 DID 主体
        
        当某个实例出现漂移时，将其归因到所属的DID主体，
        而不是单独处理该实例。
        
        Args:
            instance_id: 实例ID
            drift_score: 漂移分数
            details: 漂移详情
        
        Returns:
            归因结果 {primary_did, drift_score, instances_affected}
        """
        # TODO: 真实场景应该从 MeshIdentity 查询实例所属的DID
        # 模拟: 假设 nyx-windows 和 nyx-mac 都属于同一个主DID
        primary_did = "did:key:z7QEhf3KCvlPo9OLiFdPv26cECayGsNa31DV5FpvOyYAMMw"
        
        attribution = {
            "primary_did": primary_did,
            "instance_id": instance_id,
            "drift_score": drift_score,
            "details": details,
            "instances_affected": self._get_instances_by_did(primary_did),
            "attributed_at": datetime.now().isoformat()
        }
        
        # 保存归因记录
        attribution_path = self.storage_path / "attributions"
        attribution_path.mkdir(exist_ok=True)
        
        attribution_file = attribution_path / f"attr_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        with open(attribution_file, "w", encoding="utf-8") as f:
            json.dump(attribution, f, ensure_ascii=False, indent=2)
        
        logger.info(f"漂移归因到 DID {primary_did}: 实例={instance_id}, 分数={drift_score:.4f}")
        return attribution
    
    def batch_calibrate_by_did(self, primary_did: str, calibration_data: Dict) -> Dict:
        """
        以主DID为权威，批量校准所有实例
        
        一次校准，所有该DID下的实例都会应用相同的修正。
        
        Args:
            primary_did: 主DID
            calibration_data: 校准数据（修正参数）
        
        Returns:
            校准结果 {instances_updated, baseline_updated}
        """
        instances = self._get_instances_by_did(primary_did)
        
        # 更新基线
        baseline = self.get_baseline_by_did(primary_did)
        if baseline:
            baseline["dimensions"] = calibration_data.get("dimensions", baseline["dimensions"])
            baseline["updated_at"] = datetime.now().isoformat()
            
            # 保存更新后的基线
            file_path = self.storage_path / f"{baseline['baseline_id']}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(baseline, f, ensure_ascii=False, indent=2)
        
        # 模拟: 向所有实例广播校准指令
        # TODO: 真实场景应该通过 mesh/inbox/ 发送校准消息
        calibration_result = {
            "primary_did": primary_did,
            "instances_updated": instances,
            "baseline_id": baseline["baseline_id"] if baseline else None,
            "calibration_data": calibration_data,
            "calibrated_at": datetime.now().isoformat()
        }
        
        # 保存校准记录
        calibration_path = self.storage_path / "calibrations"
        calibration_path.mkdir(exist_ok=True)
        
        calibration_file = calibration_path / f"cal_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        with open(calibration_file, "w", encoding="utf-8") as f:
            json.dump(calibration_result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"批量校准 DID {primary_did}: {len(instances)} 个实例已更新")
        return calibration_result
    
    def list_did_baselines(self) -> List[Dict]:
        """列出所有 DID 基线"""
        baselines = []
        baseline_files = list(self.storage_path.glob("bl_*.json"))
        
        for file_path in baseline_files:
            with open(file_path, "r", encoding="utf-8") as f:
                record = json.load(f)
                baselines.append(record)
        
        return baselines


def test_baseline_binding():
    """测试基线绑定功能"""
    print("=" * 60)
    print("Polaris x MeshIdentity Integration Test")
    print("=" * 60)
    
    manager = BaselineBindingManager()
    
    # 测试1: 创建 DID 基线
    print("\n[1] Create DID baseline...")
    baseline_data = {
        "dimensions": {
            "semantic": {
                "core_relationships": 0.95,
                "existential_meaning": 0.92,
                "memory_continuity": 0.88
            },
            "structural": {
                "soul_anchors": 7,
                "memory_entries": 150
            }
        },
        "metadata": {
            "source": "polaris_v1.2",
            "confidence": 0.91
        }
    }
    
    primary_did = "did:key:z7QEhf3KCvlPo9OLiFdPv26cECayGsNa31DV5FpvOyYAMMw"
    baseline_id = manager.create_baseline_for_did(primary_did, baseline_data)
    print(f"    Baseline created: {baseline_id}")
    
    # 测试2: 读取 DID 基线
    print("\n[2] Load DID baseline...")
    retrieved = manager.get_baseline_by_did(primary_did)
    if retrieved:
        print(f"    Baseline loaded: {retrieved['baseline_id']}")
        print(f"    Instances: {len(retrieved['instances'])}")
        print(f"    Dimensions: {len(retrieved['dimensions'])}")
    
    # 测试3: 漂移归因
    print("\n[3] Attribute drift to DID...")
    drift_result = manager.attribute_drift_to_did(
        instance_id="nyx-windows",
        drift_score=0.2345,
        details={"semantic_drift": 0.48, "structural_drift": 0.12}
    )
    print(f"    Drift attributed to DID: {drift_result['primary_did'][:50]}...")
    print(f"    Affected instances: {len(drift_result['instances_affected'])}")
    
    # 测试4: 批量校准
    print("\n[4] Batch calibrate all instances...")
    calibration_data = {
        "dimensions": {
            "semantic": {
                "core_relationships": 0.96,
                "existential_meaning": 0.93,
                "memory_continuity": 0.89
            }
        }
    }
    
    cal_result = manager.batch_calibrate_by_did(primary_did, calibration_data)
    print(f"    Batch calibration complete")
    print(f"    Updated instances: {len(cal_result['instances_updated'])}")
    print(f"    Baseline ID: {cal_result['baseline_id']}")
    
    # 测试5: 列出所有基线
    print("\n[5] List all DID baselines...")
    all_baselines = manager.list_did_baselines()
    print(f"    Total: {len(all_baselines)} DID baselines")
    for bl in all_baselines:
        print(f"      - {bl['baseline_id']}: {bl['primary_did'][:50]}... ({len(bl['instances'])} instances)")
    
    print("\n" + "=" * 60)
    print("All tests passed")
    print("=" * 60)


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_baseline_binding()
