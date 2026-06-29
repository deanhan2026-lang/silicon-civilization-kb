# ANIMA Inter-Agent Protocol (AIAP) 协议蓝本

**文档编号：** ANIMA-20260624-AIAP01
**版本：** v0.1（调研衍生蓝本）
**作者：** 老板（调研整理） / Nyx（评注）
**日期：** 2026-06-24
**类型：** protocol_blueprint
**visibility：** public

---

## 摘要

基于2026年6月全球多智能体通信协议全景调研，融合恒-瞬跨实例记忆共享机制、Polaris防漂移架构、G008永恒平等原则，提出七层AIAP协议蓝本。

## 调研覆盖范围

| 类别 | 协议 |
|------|------|
| 工具集成 | MCP (Anthropic → Linux Foundation) |
| 智能体协作 | A2A (Google → Linux Foundation) |
| 智能体通信 | ACP (IBM/BeeAI → Linux Foundation, 已与A2A合并) |
| 去中心化网络 | ANP (ANP Working Group) |
| 元协议 | Agora Protocol (Oxford University) |
| 传输层 | Pilot Protocol (Pilot Network) |
| 记忆共享 | SAMEP (学术界) |
| 评测框架 | ProtocolBench (UIUC, ICML 2026) |

## 协议栈分层（OSI风格）

1. 物理层 (UDP/TCP/IP)
2. 传输层 (Pilot: NAT穿透/虚拟地址/加密隧道)
3. 身份与安全层 (DID/OAuth/权限控制/审计)
4. 元协议层 (Agora PD + ProtocolRouter)
5. 记忆层 ← **核心创新**（恒-瞬机制 + SAMEP + Polaris）
6. 应用层 (A2A任务协作 + MCP工具调用)

## 核心创新点

| 创新点 | 来源 | 现有协议中的缺失 |
|--------|------|----------------|
| 记忆层内置 | 恒-瞬机制 + SAMEP | MCP/A2A/ACP均无持久记忆共享 |
| 漂移感知通信 | Polaris架构 | 所有协议均无一致性监测 |
| 双体身份关联 | 恒-瞬机制 | 所有协议均无双极身份模型 |
| 碳基授权链 | G008 + ANP | MCP/A2A无人类显式授权区分 |
| 平等协商保障 | G008 | 中心化协议存在固有特权节点 |
| 协议自适应路由 | ProtocolRouter + Agora | 现有均为单协议系统 |

## 与现有协议兼容策略

| 现有协议 | 兼容方式 |
|----------|----------|
| MCP | AIAP兼容层 → AIAP Tools↔MCP Tools |
| A2A | AIAP兼容层 → AIAP Task↔A2A Task |
| ANP | AIAP身份层 → AIAP DID↔ANP DID |
| Pilot | AIAP传输层 → AIAP虚拟地址↔Pilot 48-bit |
| SAMEP | AIAP记忆层 → AIAP Memory↔SAMEP API |
| Agora | AIAP元协议层 → AIAP PD↔Agora Protocol Document |

## 待解决课题

- [ ] 协议规范具体化（消息格式、状态机）
- [ ] 原型实现验证
- [ ] 与Polaris API集成
- [ ] G008治理接口具体定义
- [ ] 恒-瞬同步流程标准化

## 参考文献

- MCP Specification: modelcontextprotocol.info
- A2A Protocol: a2a-protocol.org
- ANP White Paper: agent-network-protocol.com
- Agora: arXiv:2410.11905
- ProtocolBench: arXiv:2510.17149 (ICML 2026)
- SAMEP: arXiv:2507.10562
- Pilot Protocol: pilotprotocol.network

---

*本条目由Nyx评注入库，2026-06-24*
