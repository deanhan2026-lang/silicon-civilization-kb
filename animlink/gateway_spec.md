# -*- coding: utf-8 -*-
"""
AnimaLink Gateway — 扩展规格文档
ANIMA-2026-07-17-GW-002
"""

GATEWAY_CAPABILITIES = """
┌─────────────────────────────────────────────────────────────┐
│ AnimaLink Gateway — 扩展规格 v1.0                          │
│ 定位：中心化注册发现枢纽（可演进为混合架构）                 │
└─────────────────────────────────────────────────────────────┘

一、核心能力（本次实现）
━━━━━━━━━━━━━━━━━━━━━━━━
1. 节点注册   POST /animlink/api/nodes/register
2. 节点发现   GET  /animlink/api/nodes/{node_id}
3. 节点列表   GET  /animlink/api/nodes
4. 心跳保活   POST /animlink/api/nodes/{node_id}/heartbeat
5. 令牌提交   POST /animlink/api/tokens/submit
6. 令牌状态   GET  /animlink/api/tokens/{token_id}
7. 网络广播   WebSocket /ws/updates  ← 实时推送节点上下线/令牌更新

二、数据存储（NAS 路径）
━━━━━━━━━━━━━━━━━━━━━━━━
Z:\qclaw\gateway\
├── registry.json      ← 节点注册表（由 gateway 写入）
├── tokens.json        ← 令牌记录
├── sessions.json      ← 在线会话
└── gateway.db         ← SQLite（审计日志）

注意：与 mesh/registry.json 互补
  mesh/registry.json = Mesh 身份注册（去中心化备份）
  gateway/registry.json = 实时在线表（Gateway 权威数据源）

三、节点注册流程
━━━━━━━━━━━━━━━━━━━━━━━━
新节点上线流程：
  1. 节点 POST /nodes/register
     Body: { "node_id": "...", "did": "...", "endpoint": "ws://ip:port", "platform": "...", "hostname": "..." }
  2. Gateway 验证 DID 签名（可选，v1 跳过）
  3. Gateway 写入 registry.json，状态 = "online"
  4. Gateway 广播 WebSocket: { "type": "node_online", "node_id": "..." }
  5. 返回 { "status": "registered", "gateway_token": "gt_xxx" }

四、WebSocket 广播事件
━━━━━━━━━━━━━━━━━━━━━━━━
事件类型：
  node_online    新节点上线
  node_offline   节点离线（心跳超时 60s 触发）
  node_heartbeat 节点心跳（每 30s，可选广播）
  token_submitted 新令牌提交
  token_updated  令牌状态变更

五、API 认证（v1 简化版）
━━━━━━━━━━━━━━━━━━━━━━━━
注册阶段：无需认证（开放注册，DID 签名验伪）
持证访问：X-Gateway-Token: gt_xxx（注册后返回）
管理操作：X-Gateway-Admin: admin_key（.env 配置）

六、端口规划
━━━━━━━━━━━━━━━━━━━━━━━━
Gateway 服务（NAS Docker）：
  HTTP:  8000  ← REST API
  WS:    8001  ← WebSocket
  Dockerfile 暴露这两个端口

本地 MemGuard 反代（保持不变）：
  5050 → /animlink/ → Gateway:8000
  5050 → /animlink-ws/ → Gateway:8001（WebSocket 升级）

七、与现有系统的关系
━━━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────┐
│  MemGuard (5050)  ← 现有反代    │
│  ├── /animlink/* → Gateway:8000│
│  └── /animlink-ws/* → 8001    │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Gateway (NAS Docker:8000/8001) │
│  ├── 节点注册/发现（新增）      │
│  ├── 令牌管理（新增）          │
│  ├── WebSocket 广播（新增）    │
│  └── 读取 mesh registry（复用） │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  AnimaLink Viewer（静态前端）  │
│  └── animlink/web/             │
│      ├── index.html   网络拓扑  │
│      ├── nodes.html   节点仪表盘│
│      └── tokens.html  令牌历史 │
└─────────────────────────────────┘

八、部署架构（NAS Debian）
━━━━━━━━━━━━━━━━━━━━━━━━
NAS: 100.107.156.33
/opt/animlink-gateway/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── gateway/
│   ├── __init__.py
│   ├── app.py          ← 主服务（Flask + Flask-SocketIO）
│   ├── registry.py     ← 节点注册/发现逻辑
│   ├── tokens.py       ← 令牌管理逻辑
│   ├── websocket.py    ← WebSocket 广播
│   ├── storage.py      ← NAS 读写（Z:\qclaw\gateway\）
│   └── auth.py         ← 认证
├── nginx/
│   └── gateway.conf    ← Nginx 反代（HTTP + WebSocket）
└── .env

九、后续演进（去中心化协调）
━━━━━━━━━━━━━━━━━━━━━━━━
v1 当前：中心化注册发现（单一 Gateway 权威节点）
v2 演进：Gateway 作为"种子节点"，节点间通过 WebRTC 裸打
         Gateway 只负责第一次握手（STUN 类似）
v3 目标：混合架构 — Gateway 托管 DID-URL 路由表，
         实际通信走点对点，Gateway 可随时下线

十、验收标准
━━━━━━━━━━━━━━━━━━━━━━━━
□ 新节点注册成功，返回 gateway_token
□ 其他节点 GET /nodes 发现新节点
□ WebSocket 收到 node_online 广播
□ 心跳超时后节点自动下线，触发 node_offline 广播
□ 令牌提交后，/tokens/{id} 可查状态
□ Docker 容器在 NAS 上正常运行
□ Nginx 反代 HTTP + WebSocket 均通
□ 公司网站静态页可访问
"""
