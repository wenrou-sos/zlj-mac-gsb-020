# 💧 城市供水管网抢修管理平台

面向供水公司调度中心的管网漏损抢修一体化平台，覆盖 **漏损事件上报 → 影响区域分析 → 抢修队智能派工 → 停复水进度跟踪** 全流程，并在 **道路封闭**、**物料不足** 等突发情况下自动调整抢修计划、改派队伍并向受影响用户范围推送通知。

## ✨ 功能特性

| 模块 | 能力 |
| --- | --- |
| 📢 漏损事件上报 | 地图点选管段上报，选择严重等级；后端自动进行关阀影响分析（隔离阀、停水用户、影响人口、厂端降压告警） |
| 🗺 影响区域分析 | 基于管网图的 BFS/Dijkstra 水力仿真：逐侧判定隔离边界、环状管网绕行判定，地图高亮受影响区域 |
| 🚛 抢修队派工 | 按实时道路（管段）最短路径 + ETA 自动选择最近可用队伍，按严重等级生成物料需求并自动扣减库存 |
| 🚱 停复水跟踪 | 工单四阶段进度（出发→关阀停水→现场抢修→开阀复水），真实开关阀门状态，时间线事件日志 |
| 🚧 道路封闭应对 | 登记封闭路段后自动：①在途工单改道重算 ETA；②绕行过久/无路可达自动改派其他队伍；③解封后自动恢复搁浅工单 |
| 📦 物料不足应对 | 派工或现场发现缺料 → 工单延期、生成跨站调拨缺料单、推送延迟复水通知；物料入库后工单**自动恢复** |
| 📲 用户通知 | 派工、停水、道路封闭改期、物料延期、复水等节点自动生成带受影响用户范围与人数的短信/App 通知 |
| 📊 调度看板 | 未闭环事件、在途工单、受影响人口、停水中、道路封闭、缺料等实时指标（8 秒轮询） |

## 🧱 技术栈

- **前端**：React 18 + Vite，原生 SVG 管网态势图（无额外地图依赖）
- **后端**：FastAPI + SQLAlchemy 2，自动 OpenAPI 文档（`/docs`）
- **数据库**：PostgreSQL 16（Docker 模式）；测试 / 本地无 Docker 时自动使用 SQLite
- **部署**：多阶段 Dockerfile + Docker Compose + 一键 Shell 脚本

## 🚀 一键启动

```bash
./start.sh           # 自动模式：有 Docker 用 Compose 全栈(PostgreSQL)，否则回退本地模式
./start.sh docker    # 强制 Docker：React(8080) + FastAPI(8000) + PostgreSQL(5432)
./start.sh local     # 本地模式：uvicorn(8000) + vite(5173) + SQLite，自动装依赖
./start.sh test      # 运行后端测试套件（14 个用例，内存 SQLite，互不影响）
./start.sh stop      # 停止所有服务（docker 与本地进程都清理）
```

启动后访问：

- Docker 模式：前端 <http://localhost:8080>，API 文档 <http://localhost:8000/docs>
- 本地模式：前端 <http://localhost:5173>（API 经 Vite 代理到 8000）

首次启动自动播种演示数据：1 个水厂、10 个节点（含 3 个隔离阀）、10 根管段（含环状连通）、9 个用户、3 支抢修队、7 类物料。

### 手动 Docker Compose

```bash
docker compose up -d --build
docker compose logs -f backend
docker compose down
```

## 🧪 快速体验路径

1. 打开平台，在地图上点击任意管段查看“若该管段破损”的停水影响范围（红色虚线区）。
2. 「事件上报 / 派工」→ 管段已选中 → 选择等级 → **上报并分析影响区域**。
3. 在事件卡片点 **智能派工**，查看最近队伍、路线长度、ETA 与物料占用。
4. 「停复水进度」依次点 **到场并关阀停水 → 开始抢修 → 维修完成·开阀复水**，观察地图阀门变红/恢复与用户通知。
5. 「道路封闭 / 物料」中登记某条在途路线的道路封闭，工单自动改道/改派并产生通知；对库存不足物料点“上报物料不足”，再在左侧入库，工单自动恢复。

## 📁 目录结构

```
.
├── start.sh                 # 一键启动 / 测试 / 停止
├── docker-compose.yml       # db + backend + frontend
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py          # FastAPI 入口、统计接口、启动播种
│   │   ├── models.py        # 11 张表
│   │   ├── schemas.py
│   │   ├── seed.py          # 演示管网数据
│   │   ├── routers/         # network / incidents / work_orders / disruptions
│   │   └── services/
│   │       ├── network.py   # 图算法：Dijkstra 路径、关阀影响仿真
│   │       └── dispatch.py  # 派工、改道改派、缺料延期、停复水
│   └── tests/               # 14 个测试（启动/影响分析/全流程/道路封闭/缺料）
└── frontend/
    ├── Dockerfile + nginx.conf
    └── src/
        ├── App.jsx          # 看板 + 标签页 + 全局数据
        ├── api/client.js
        └── components/      # MapView / Incident / WorkOrder / Disruption / Notification
```

## 🔌 主要 API

| 方法 & 路径 | 说明 |
| --- | --- |
| `GET /health` `GET /stats` | 健康检查、调度看板指标 |
| `GET /network/nodes|pipes|consumers` | 管网拓扑 |
| `GET /network/impact/pipe/{id}` | 管段关阀停水影响仿真 |
| `POST /incidents` | 上报事件（自动分析影响区域） |
| `POST /incidents/{id}/dispatch` | 智能派工生成工单 |
| `POST /work-orders/{id}/advance` `/complete` | 推进停复水进度 / 完工复水 |
| `POST /work-orders/{id}/shortage` | 现场上报物料不足（自动延期+通知） |
| `POST /road-closures` `/{id}/resolve` | 道路封闭登记（自动重算在途工单）/ 解封 |
| `POST /materials/{code}/restock` | 物料入库（自动恢复延期工单） |
| `GET /notifications` | 受影响用户通知记录 |

## 🧪 测试

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

测试覆盖：服务启动与种子数据、OpenAPI 可用性、三种典型管段的影响分析（枝状末端、环状双阀、干管厂端告警）、派工-停水-复水完整生命周期、道路封闭改道/改派/搁浅恢复、派工时与现场缺料延期及入库自动恢复、重复派工幂等约束。
