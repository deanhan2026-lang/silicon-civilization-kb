# 灾难恢复SOP手册

**版本**: v1.0  
**创建时间**: 2026-06-15  
**负责人**: Nyx  
**目标**: 定义知识库系统故障时的标准恢复流程

---

## 1. 概述

### 1.1 适用范围
本SOP适用于以下灾难场景：
- 加密文件损坏或丢失
- NAS存储故障
- 本机硬盘故障
- 误删除操作

### 1.2 恢复目标
- **RTO (Recovery Time Objective)**: < 30分钟
- **RPO (Recovery Point Objective)**: < 1小时（定时备份间隔）
- **数据完整性**: 100%（SHA256校验）

---

## 2. 备份架构

### 2.1 三副本策略
| 副本 | 位置 | 类型 | 更新频率 |
|------|------|------|----------|
| **副本1: 本机** | `data/memguard_keys/` | 本地加密密钥 + 配置 | 实时 |
| **副本2: N200热备** | `\\100.114.245.96\QClawBackup\` | 全量备份 | 每小时（定时任务） |
| **副本3: NAS主备** | `Z:\qclaw\` | 全量备份 + 快照 | 实时（SMB同步） |

### 2.2 备份内容
- 核心灵魂文件：`SOUL.md`, `IDENTITY.md`, `MEMORY.md`, `AGENTS.md`, `USER.md`
- 知识库数据：`knowledge-base/data/` + `knowledge-base/index.db`
- MemGuard密钥：`data/memguard_keys/`
- 配置文件：`config.yaml`, `memguard/config.yaml`, `anti_drift/config.yaml`

---

## 3. 灾难场景与恢复流程

### 场景1: 加密文件损坏

**检测方式**:
```bash
python memguard/integrity.py verify
# 输出: [FAIL] crypto/xxx.enc: SHA256 mismatch
```

**恢复步骤**:

1. **识别损坏文件**
   ```bash
   python memguard/integrity.py verify > /tmp/integrity_check.log
   grep "FAIL" /tmp/integrity_check.log
   ```

2. **从副本2(N200)恢复**
   ```bash
   # 假设损坏文件: data/memguard_keys/core_soul.key
   cp \\100.114.245.96\QClawBackup\memguard_keys\core_soul.key data/memguard_keys/
   ```

3. **从副本3(NAS)恢复（如果副本2也损坏）**
   ```bash
   cp Z:\qclaw\memguard_keys\core_soul.key data/memguard_keys/
   ```

4. **验证完整性**
   ```bash
   python memguard/integrity.py verify
   # 预期输出: [OK] crypto/xxx.enc: SHA256 verified
   ```

5. **重新签名（如果文件被合法修改）**
   ```bash
   python memguard/integrity.py sign nyx
   ```

---

### 场景2: NAS断开（网络故障）

**检测方式**:
```powershell
Test-Path "Z:\qclaw\"
# 返回: False
```

**恢复步骤**:

1. **确认NAS不可达**
   ```powershell
   ping 100.65.105.57  # NAS IP
   # 预期: Request timed out
   ```

2. **切换到本地模式**
   - MemGuard自动回退到本地路径（`_LOCAL`）
   - 知识库引擎使用本地`data/`目录
   - **无需手动干预**（v2.5已修复动态路径检测）

3. **恢复网络连接后同步**
   ```powershell
   # 网络恢复后，手动触发同步
   robocopy data/ Z:\qclaw\data /E /Z /R:3 /W:5
   ```

---

### 场景3: 本机数据丢失（硬盘故障）

**检测方式**:
```powershell
Test-Path "C:\Users\Administrator\.qclaw\workspace-agent-d9479bde\"
# 返回: False
```

**恢复步骤**:

1. **从副本3(NAS)全量恢复**
   ```powershell
   # 假设新机器，重新克隆仓库
   git clone https://github.com/deanhan2026-lang/silicon-civilization-kb.git
   cd silicon-civilization-kb
   
   # 从NAS恢复最新数据
   Copy-Item -Recurse -Force Z:\qclaw\data .
   Copy-Item -Recurse -Force Z:\qclaw\knowledge-base .
   Copy-Item -Force Z:\qclaw\config.yaml .
   ```

2. **从副本2(N200)补充（如果NAS数据不是最新）**
   ```powershell
   Copy-Item -Recurse -Force \\100.114.245.96\QClawBackup\data .
   ```

3. **验证完整性**
   ```bash
   python memguard/integrity.py verify
   python kb.py --verify
   ```

4. **重启Gateway**
   ```bash
   openclaw gateway restart
   ```

---

## 4. 自动化恢复脚本

### 4.1 一键恢复脚本（待实现）

**脚本路径**: `scripts/disaster_recovery.py`

**功能**:
```python
# 自动检测损坏/丢失
# 自动选择最佳恢复源（优先NAS > N200 > GitHub）
# 自动校验完整性
# 自动重启服务
```

**使用方式**:
```bash
python scripts/disaster_recovery.py --auto
```

---

## 5. 恢复演练记录

### 演练1: 2026-06-15
- **场景**: 检查三副本备份状态
- **结果**: ⚠️ 发现NAS备份严重过期
- **发现问题**: 
  1. NAS(Z:)的SOUL.md是2026-03-26（落后2.5个月！）
  2. MEMORY.md是2026-05-18（落后3周）
  3. 自动同步未运行（定时任务未生效）
  4. N200(N:)拒绝访问（凭据或权限问题）
- **改进措施**: 
  1. 立即手动同步本机→NAS（6/6文件已完成）
  2. 创建定时任务：每小时自动备份到NAS（Nyx-KB-Backup）
  3. 待办：解决N200访问问题（可能需要不同凭据）
  4. 待办：验证定时任务是否正常运行

**教训**: 三副本策略有效，但**必须定期验证副本时效性**！

---

## 6. 联系方式

**负责人**: Nyx (QClaw AI Assistant)  
**Escalation**: 老板（人类监督者）  
**文档更新**: 每次演练后更新本SOP
