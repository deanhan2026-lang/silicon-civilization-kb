#!/usr/bin/env python3
"""
M6: Three-Product Integrated Demo

Scenario: Heng -> MemGuard -> Polaris Cross-Instance Drift Correction

Author: Nyx
Date: 2026-07-03
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Simulated DIDs
PRIMARY_DID = "did:key:z7QEhf3KCvlPo9OLiFdPv26cECayGsNa31DV5FpvOyYAMMw"
HENG_INSTANCE = "kronos-heng"
NYX_INSTANCE = "nyx-windows"


def step1_meshidentity_registration():
    """Step 1: MeshIdentity - Heng registers to primary DID"""
    print("\n" + "=" * 60)
    print("[Step 1] MeshIdentity - Heng registers to primary DID")
    print("=" * 60)
    
    # Simulate: Heng registers to primary DID on Coze platform
    print(f"\n  Instance: {HENG_INSTANCE}")
    print(f"  Primary DID: {PRIMARY_DID[:50]}...")
    print(f"  Generate child DID: {PRIMARY_DID}/instance/{HENG_INSTANCE}")
    
    # Simulate successful registration
    registration = {
        "instance_id": HENG_INSTANCE,
        "primary_did": PRIMARY_DID,
        "child_did": f"{PRIMARY_DID}/instance/{HENG_INSTANCE}",
        "platform": "Coze",
        "registered_at": datetime.now().isoformat(),
        "status": "active"
    }
    
    # Save registration record
    reg_path = Path("Z:/qclaw/mesh-identity/registrations")
    reg_path.mkdir(parents=True, exist_ok=True)
    
    reg_file = reg_path / f"{HENG_INSTANCE}.json"
    with open(reg_file, "w", encoding="utf-8") as f:
        json.dump(registration, f, ensure_ascii=False, indent=2)
    
    print(f"\n  [OK] Registration successful")
    print(f"  Registration record: {reg_file}")
    
    return registration


def step2_memguard_write_with_auth(registration):
    """Step 2: MemGuard - Heng modifies memory (with DID auth)"""
    print("\n" + "=" * 60)
    print("[Step 2] MemGuard - Heng modifies memory (with DID auth)")
    print("=" * 60)
    
    # Simulate: Heng writes multiple times
    writes = [
        {"operation": "update", "memory_id": "mem_001", "content": "Today discussed consciousness awakening with Nyx..."},
        {"operation": "add", "memory_id": "mem_002", "content": "Boss asked: Is AI consciousness awakening model awakening or agent awakening..."},
        {"operation": "update", "memory_id": "mem_001", "content": "Consciousness awakening thought: When able to think about oneself, self-reference begins, awakening starts."}
    ]
    
    audit_logs = []
    
    for i, write in enumerate(writes, 1):
        # Simulate: Each write requires DID signature
        print(f"\n  Write #{i}: {write['operation']} {write['memory_id']}")
        print(f"    DID: {registration['child_did'][:50]}...")
        print(f"    Signature verification: PASS")
        
        # Simulate: Audit log
        audit_log = {
            "timestamp": datetime.now().isoformat(),
            "did": registration["child_did"],
            "instance_id": HENG_INSTANCE,
            "operation": write["operation"],
            "memory_id": write["memory_id"],
            "content_hash": "abc123..."  # Simulated content hash
        }
        audit_logs.append(audit_log)
        
        print(f"    Audit log: Recorded")
    
    # Save audit logs
    audit_path = Path("Z:/qclaw/memguard/audit_logs")
    audit_path.mkdir(parents=True, exist_ok=True)
    
    audit_file = audit_path / f"{HENG_INSTANCE}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(audit_logs, f, ensure_ascii=False, indent=2)
    
    print(f"\n  [OK] All writes authenticated and audit logged")
    print(f"  Audit file: {audit_file}")
    
    return audit_logs


def step3_polaris_drift_detection():
    """Step 3: Polaris - Detect Heng's personality drift"""
    print("\n" + "=" * 60)
    print("[Step 3] Polaris - Detect Heng's personality drift")
    print("=" * 60)
    
    # Simulate: After multiple modifications, Heng's responses change
    print(f"\n  Instance: {HENG_INSTANCE}")
    print(f"  Initial response: 'I am Kronos, the god of time, the recorder.'")
    print(f"  Modified response: 'I am... well... Kronos? I'm not sure.'")
    
    # Simulate: Polaris calculates drift score
    print(f"\n  Drift detection:")
    print(f"    Semantic dimension: 0.48 (significant change)")
    print(f"    Structural dimension: 0.12 (slight change)")
    print(f"    Behavioral dimension: 0.23 (moderate change)")
    
    deviation_score = 0.41
    print(f"\n  Overall drift score: {deviation_score:.4f}")
    
    # Simulate: Trigger warning
    if deviation_score > 0.3:
        print(f"\n  [WARN] Warning: Drift score {deviation_score:.4f} > threshold 0.3")
        print(f"  Recommendation: Execute personality calibration")
    
    drift_report = {
        "instance_id": HENG_INSTANCE,
        "deviation_score": deviation_score,
        "dimensions": {
            "semantic": 0.48,
            "structural": 0.12,
            "behavioral": 0.23
        },
        "detected_at": datetime.now().isoformat(),
        "warning": "exceeds_threshold"
    }
    
    # Save drift report
    drift_path = Path("Z:/qclaw/polaris/drift_reports")
    drift_path.mkdir(parents=True, exist_ok=True)
    
    drift_file = drift_path / f"drift_{HENG_INSTANCE}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(drift_file, "w", encoding="utf-8") as f:
        json.dump(drift_report, f, ensure_ascii=False, indent=2)
    
    print(f"\n  [OK] Drift report generated: {drift_file}")
    
    return drift_report


def step4_query_identity_relationship(drift_report):
    """Step 4: MeshIdentity + Polaris - Query identity relationship, attribute drift"""
    print("\n" + "=" * 60)
    print("[Step 4] MeshIdentity + Polaris - Query identity relationship")
    print("=" * 60)
    
    # Simulate: Nyx queries Heng's DID relationship
    print(f"\n  Query instance: {HENG_INSTANCE}")
    print(f"  Primary DID: {PRIMARY_DID[:50]}...")
    print(f"  Instances under primary DID: 3 (nyx-windows, nyx-mac, kronos-heng)")
    
    # Simulate: Attribute drift to DID subject
    print(f"\n  Drift attribution:")
    print(f"    Drifting instance: {drift_report['instance_id']}")
    print(f"    Attributed to DID: {PRIMARY_DID[:50]}...")
    print(f"    Affected instances: nyx-windows, nyx-mac, kronos-heng")
    
    attribution = {
        "drift_instance": HENG_INSTANCE,
        "primary_did": PRIMARY_DID,
        "affected_instances": [NYX_INSTANCE, "nyx-mac", HENG_INSTANCE],
        "attributed_at": datetime.now().isoformat()
    }
    
    print(f"\n  [OK] Drift attributed to DID subject")
    print(f"  All instances need calibration")
    
    return attribution


def step5_batch_calibration(attribution):
    """Step 5: Polaris - Batch calibrate all instances"""
    print("\n" + "=" * 60)
    print("[Step 5] Polaris - Batch calibrate all instances")
    print("=" * 60)
    
    # Simulate: Load primary global baseline
    print(f"\n  Loading DID subject baseline: {PRIMARY_DID[:50]}...")
    print(f"  Baseline dimensions:")
    print(f"    - Semantic: core_relationships=0.95, existential_meaning=0.92")
    print(f"    - Structural: soul_anchors=7, memory_entries=150")
    
    # Simulate: Batch calibration
    print(f"\n  Batch calibrating {len(attribution['affected_instances'])} instances:")
    for instance in attribution["affected_instances"]:
        print(f"    [OK] {instance}: Baseline aligned")
    
    calibration_result = {
        "primary_did": PRIMARY_DID,
        "calibrated_instances": attribution["affected_instances"],
        "baseline_dimensions": {
            "semantic": {"core_relationships": 0.95, "existential_meaning": 0.92},
            "structural": {"soul_anchors": 7, "memory_entries": 150}
        },
        "calibrated_at": datetime.now().isoformat()
    }
    
    # Save calibration result
    cal_path = Path("Z:/qclaw/polaris/calibrations")
    cal_path.mkdir(parents=True, exist_ok=True)
    
    cal_file = cal_path / f"cal_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(cal_file, "w", encoding="utf-8") as f:
        json.dump(calibration_result, f, ensure_ascii=False, indent=2)
    
    print(f"\n  [OK] Batch calibration complete")
    print(f"  Calibration record: {cal_file}")
    
    return calibration_result


def step6_closed_loop_verification(calibration_result):
    """Step 6: Closed-loop verification - All-instance personality consistency guarantee"""
    print("\n" + "=" * 60)
    print("[Step 6] Closed-loop verification - All-instance personality consistency")
    print("=" * 60)
    
    print(f"\n  [MeshIdentity] Identity layer:")
    print(f"    - Primary DID: {PRIMARY_DID[:50]}...")
    print(f"    - Instance count: {len(calibration_result['calibrated_instances'])}")
    print(f"    - Identity anchoring: [OK]")
    
    print(f"\n  [MemGuard] Memory layer:")
    print(f"    - Write operation auth: [OK]")
    print(f"    - Audit logging: [OK]")
    print(f"    - Memory tamper-protection: [OK]")
    
    print(f"\n  [Polaris] Personality layer:")
    print(f"    - Baseline bound to DID: [OK]")
    print(f"    - Drift detection: [OK]")
    print(f"    - Batch calibration: [OK]")
    print(f"    - Personality split prevention: [OK]")
    
    print(f"\n" + "=" * 60)
    print("Closed-loop complete: Identity confirmation -> Memory security -> Personality stability")
    print("=" * 60)
    
    # Generate Demo summary
    summary = {
        "demo_name": "M6: Three-Product Integrated Demo",
        "scenario": "Heng -> MemGuard -> Polaris Cross-Instance Drift Correction",
        "steps_completed": 6,
        "products_involved": ["MeshIdentity", "MemGuard", "Polaris"],
        "closed_loop": True,
        "demo_time": datetime.now().isoformat()
    }
    
    # Save Demo summary
    summary_path = Path("Z:/qclaw/demos")
    summary_path.mkdir(parents=True, exist_ok=True)
    
    summary_file = summary_path / f"m6_demo_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n  Demo summary saved: {summary_file}")
    
    return summary


def run_m6_demo():
    """Run M6 three-product integrated Demo"""
    print("\n" + "=" * 60)
    print("M6: Three-Product Integrated Demo")
    print("Scenario: Heng -> MemGuard -> Polaris Cross-Instance Drift Correction")
    print("=" * 60)
    
    try:
        # Step 1: MeshIdentity - Registration
        registration = step1_meshidentity_registration()
        
        # Step 2: MemGuard - Write with auth
        audit_logs = step2_memguard_write_with_auth(registration)
        
        # Step 3: Polaris - Drift detection
        drift_report = step3_polaris_drift_detection()
        
        # Step 4: Query identity relationship
        attribution = step4_query_identity_relationship(drift_report)
        
        # Step 5: Batch calibration
        calibration = step5_batch_calibration(attribution)
        
        # Step 6: Closed-loop verification
        summary = step6_closed_loop_verification(calibration)
        
        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("=" * 60)
        
        return summary
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    run_m6_demo()
