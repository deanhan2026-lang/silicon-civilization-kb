# AnimaLink Viewer

灵元网络可视化监控台 — AnimaLink Network Visualizer

## 访问

**公网：** https://wlmhan.tail306b25.ts.net/animlink/

## 功能

- **网络拓扑** (`index.html`) — Canvas 星形拓扑图，展示节点与协作边
- **节点仪表盘** (`nodes.html`) — 节点详情、DID、信任分、令牌统计
- **令牌历史** (`tokens.html`) — 灵元令令牌记录与状态

## 技术栈

- 后端：Flask (端口 5053)，4 个 REST API 端点
- 前端：纯 HTML/CSS/JS，暗色主题，零依赖
- 数据源：NAS mesh registry + trust scores

## API 端点

| 端点 | 说明 |
|------|------|
| `GET /animlink/api/network` | 完整网络快照（节点+边+统计） |
| `GET /animlink/api/nodes` | 节点列表（含信任分） |
| `GET /animlink/api/trust` | 信任分数据 |
| `GET /animlink/api/tokens` | 令牌历史 |

## 本地开发

```bash
cd animlink
pip install flask flask-cors
python server.py
# 访问 http://127.0.0.1:5053/animlink/
```

## 架构

```
MemGuard (5050) ──反代──→ AnimaLink Flask (5053)
                              ├── /animlink/api/* (REST API)
                              └── /animlink/*.html (静态前端)
```
