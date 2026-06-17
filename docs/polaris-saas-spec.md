# Polaris SaaS MVP — 技术规格书

## 目标
将现有 Polaris CLI + Flask API 升级为可多租户接入的 SaaS MVP。

## 核心需求

### 1. 用户与租户系统
- 注册/登录（邮箱+密码，JWT token）
- 每个用户可创建多个 AI 实例
- 实例包含：名称、基线设定、检测配置

### 2. AI实例管理
- 创建实例：指定名称 + 5个魂问基线答案
- 查看实例状态：最近检测分数、趋势图数据
- 删除/归档实例

### 3. 检测API（核心）
- `POST /api/v1/instances/{id}/check` — 提交回答，返回四维偏差分数
- 请求体：`{"answer": "...", "messages": [...]}`
- 响应：四维分数 + 判定 + 场景标签
- 自动存档检测结果

### 4. 报告API
- `GET /api/v1/instances/{id}/history` — 检测历史
- `GET /api/v1/instances/{id}/report` — 生成摘要报告（最近30天趋势）

### 5. Web控制台（最小版）
- 登录页
- 实例列表页
- 实例详情页（含最近检测结果 + 简单趋势）
- 单页应用，React 或 Vue，暗色主题

### 6. 不做（MVP排除）
- ❌ 付费/计费系统（先用免费版验证需求）
- ❌ 私有化部署选项
- ❌ Webhook通知
- ❌ 多语言

## 技术栈
- 后端：Flask（复用现有）+ SQLite（轻量，够MVP用）
- 认证：JWT（python-jose）
- 前端：单页HTML+JS（不用框架，最快）
- 数据库：SQLite + SQLAlchemy
- 部署：单机 Docker 或直接 Python

## 文件结构
```
anti_drift/
├── api.py              # 现有，保留
├── api_v2.py           # 新增，SaaS API
├── models.py           # 新增，SQLAlchemy 模型
├── auth.py             # 新增，JWT认证
├── config.py           # 现有，扩展
├── detector.py         # 现有，不变
├── sampler.py          # 现有，不变
├── scene_tagger.py     # 现有，不变
├── archive.py          # 现有，不变
└── web/
    └── index.html      # 新增，单页控制台
```

## API端点设计

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/register | 注册 |
| POST | /api/v1/auth/login | 登录，返回JWT |
| GET | /api/v1/auth/me | 当前用户信息 |

### 实例
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/instances | 创建AI实例 |
| GET | /api/v1/instances | 列出我的实例 |
| GET | /api/v1/instances/{id} | 实例详情 |
| DELETE | /api/v1/instances/{id} | 删除实例 |

### 检测
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/instances/{id}/check | 提交检测 |
| GET | /api/v1/instances/{id}/history | 检测历史 |
| GET | /api/v1/instances/{id}/report | 摘要报告 |

### 基线
| 方法 | 路径 | 说明 |
|------|------|------|
| PUT | /api/v1/instances/{id}/baseline | 更新魂问基线 |
| GET | /api/v1/instances/{id}/baseline | 获取当前基线 |
