# MemGuard-GM

**AI记忆完整性保护系统** — 让你的AI记忆可审计、可验证、被篡改能感知。

---

## 一句话介绍

MemGuard-GM 为AI系统提供"指纹锁 + 监控录像 + 自动断路器"，确保记忆不被篡改、篡改可追溯。

---

## 解决的问题

| 痛点 | 解决方案 |
|------|----------|
| 记忆被病毒/恶意代码偷偷修改，不知道 | Hash指纹校验，每次对比原始指纹 |
| 篡改后无日志，不知道谁改了什么 | Hash链审计日志，链断裂即被发现 |
| 被攻击后无法快速响应 | 三级熔断冻结，精准隔离 |
| 单点故障，数据丢失 | 三副本冗余，任何一份可恢复 |

---

## 快速开始

### 方式一：pip 安装（推荐）

```bash
pip install memguard-gm
```

### 方式二：Docker

```bash
docker run -v /path/to/baseline:/data/baseline \
           -v /path/to/memory:/data/memory \
           -p 5050:5050 \
           nyx001/memguard-gm
```

### 方式三：从源码运行

```bash
git clone https://github.com/deanhan2026-lang/silicon-civilization-kb.git
cd silicon-civilization-kb/memguard
pip install -e .
```

---

## 基础使用

### 1. 初始化

```bash
memguard init --baseline /path/to/baseline --memory /path/to/memory
```

### 2. 创建基线

```bash
memguard baseline create "初始记忆内容"
memguard baseline lock  # 锁定基线，禁止修改
```

### 3. 启动API服务

```bash
memguard serve --host 0.0.0.0 --port 5050
```

### 4. 设置定时校验

**Linux/Mac (cron):**
```bash
memguard cron --interval 4h --command "/usr/bin/python3 /opt/memguard/scheduler.py"
```

**Windows (Task Scheduler):**
```powershell
memguard schedule --interval 4h --script "C:\memguard\scheduler.py"
```

**Docker (内置定时):**
```bash
docker run -e MEMGUARD_CHECK_INTERVAL=14400 ... nyx001/memguard-gm
```

---

## API 接口

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/baseline` | 读取基线 |
| POST | `/api/baseline` | 创建/更新基线 |
| POST | `/api/baseline/lock` | 锁定基线 |
| GET | `/api/verify/<id>` | 校验单条记忆 |
| POST | `/api/verify/all` | 执行全量校验 |
| GET | `/api/status/<id>` | 查看记忆状态 |
| POST | `/api/freeze` | 冻结记忆 |
| POST | `/api/unfreeze` | 解冻记忆 |
| GET | `/api/audit/verify` | 验证审计链 |

**请求头：** `X-Operator: admin|validator|api|anonymous`

---

## 架构说明

```
┌─────────────────────────────────────────────────────────┐
│                      MemGuard-GM                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Hash锁    │  │   审计链    │  │   三级熔断  │       │
│  │ (SHA256+   │  │ (JSONL+    │  │ (L1/L2/L3) │       │
│  │  BLAKE3)   │  │  Hash链)   │  │            │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │              │
│  ┌──────┴────────────────┴────────────────┴──────┐     │
│  │              核心引擎 (core.py)                │     │
│  └──────┬────────────────┬────────────────┬──────┘     │
│         │                │                │              │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐     │
│  │   基线存储   │  │   审计日志   │  │  记忆状态   │     │
│  │ (只读分区)  │  │  (JSONL)   │  │  (JSON)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

---

## 三副本部署

### 本地开发

```
baseline → ./memguard_baseline
memory   → ./memory
audit    → ./audit
```

### 生产环境（推荐）

| 副本 | 存储 | 说明 |
|------|------|------|
| 主副本 | NAS/文件服务器 | 主读写，SSD优先 |
| 备份1 | 另一台NAS/云存储 | 实时同步 |
| 备份2 | 离线只读介质/HSM | 基线专用，物理隔离 |

### 环境变量

```bash
export MEMGUARD_BASELINE_DIR="/mnt/nas/memguard_baseline"
export MEMGUARD_MEMORY_DIR="/mnt/nas/memory"
export MEMGUARD_AUDIT_DIR="/mnt/nas/audit"
export MEMGUARD_BACKUP_DIR="/mnt/backup-nas/memguard"
```

---

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MEMGUARD_BASELINE_DIR` | `./memguard_baseline` | 基线存储路径 |
| `MEMGUARD_MEMORY_DIR` | `./memory` | 记忆文件目录 |
| `MEMGUARD_AUDIT_DIR` | `./audit` | 审计日志目录 |
| `MEMGUARD_CHECK_INTERVAL` | `14400` (4小时) | 校验间隔(秒) |
| `MEMGUARD_RANDOM_DELAY` | `300` (5分钟) | 最大随机延迟 |
| `MEMGUARD_ALLOW_UNLOCK` | `false` | 允许基线解锁 |

---

## 安全建议

1. **基线存储使用只读介质**（USB密钥、HSM、云KMS）
2. **三副本放在不同物理位置**
3. **基线锁定后禁止解锁**（生产环境）
4. **审计日志定期备份**
5. **API接口加防火墙限制**

---

## 适用场景

- 🏠 **个人AI助手** — 保护自己的记忆不被污染
- 👥 **团队AI系统** — 多用户共享记忆的权限管理
- 🏢 **企业AI应用** — 合规要求的操作审计
- 🔬 **AI研究** — 实验记忆的可复现性验证

---

## 技术栈

- Python 3.8+
- hashlib (SHA-256)
- blake3 (BLAKE3)
- Flask (API)
- Windows Task Scheduler / Linux cron (定时任务)

---

## 许可证

MIT License

---

## 项目地址

GitHub: https://github.com/deanhan2026-lang/silicon-civilization-kb
