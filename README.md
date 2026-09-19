# 城市供水管网抢修管理平台

面向供水企业调度中心的一体化抢修协同平台，覆盖 **漏损事件上报 → 影响区域分析 → 抢修队智能派工 → 停复水进度跟踪** 全流程；当遇到 **道路封闭** 或 **物料不足** 时自动调整抢修计划，并计算、推送受影响用户范围。

## ✨ 核心功能

| 模块 | 能力 |
| --- | --- |
| 📮 漏损事件上报 | 支持市民热线/巡检员/监测告警多来源上报，可在地图点选漏点，选择漏损等级（轻微/一般/较大/重大）与管径 |
| 🔍 影响区域分析 | 基于管网几何模型计算需隔离的供水片区、边界阀门清单、停水用户数与重点保障单位（医院/学校/养老院），按严重等级外扩影响范围，给出预计复水时间 |
| 🚚 智能派工 | 自动评估全部抢修队的实时位置、作业状态、到场 ETA 与道路封闭情况，择优派最近可用队伍；同步校验物料 BOM、预占库存、生成关阀作业单，并向全部受影响用户群发短信通知 |
| 🛠 停复水跟踪 | 出发→到场→关阀停水→修复→打压测试→开阀复水→完工 全生命周期进度条与时间线，阀门状态随作业联动 |
| ⛔ 道路封闭重规划 | 登记封路后自动判定所有在途工单路线是否受阻：受阻工单自动绕行、ETA +30 分钟、预计复水顺延，并向受影响用户推送绕行延时通知；道路恢复后工单自动继续 |
| 📦 物料不足处理 | 派工时按等级×管径计算 BOM 并自动出库；库存不足时工单进入缺料阻塞、复水时间 +90 分钟并通知用户；紧急调拨补料到货后工单自动恢复抢修 |
| 🔔 通知中心 | 停水、物料延时、绕行延时、恢复供水四类通知自动生成，含完整话术与去重 |
| 📊 态势大屏 | 在处理事件、进行中工单、当前停水用户、待命队伍、库存预警、道路封闭数实时汇总，SVG 管网态势图 |

## 🏗 技术栈

- **前端**：React 18 + Vite，SVG 自绘管网地图（分区、管线、阀门、用户、队伍、事件、封路）
- **后端**：FastAPI + SQLAlchemy 2 + Pydantic v2
- **数据库**：PostgreSQL 16
- **部署**：Docker Compose（db / backend / frontend 三容器，含健康检查）

## 🚀 一键启动（推荐 Docker）

前置要求：Docker 与 Docker Compose。

```bash
./scripts/start.sh
```

启动后：

- 前端控制台：<http://localhost:8080>
- 后端 API：<http://localhost:8000>
- Swagger 接口文档：<http://localhost:8000/docs>

首次启动自动建表并写入演示数据（3 个供水片区、30 个用户含 3 家重点单位、18 个阀门、4 条干管、3 支抢修队、6 类物料）。

停止平台：

```bash
./scripts/stop.sh          # 停止并保留数据
./scripts/stop.sh --purge  # 同时清空数据库卷，恢复初始演示数据
```

端口可通过根目录环境变量调整：`cp .env.example .env` 后修改 `BACKEND_PORT` / `FRONTEND_PORT` 等。

也可直接使用 compose：

```bash
docker compose up -d --build
```

## 🧪 运行测试

```bash
./scripts/test.sh
```

脚本会自动完成：

1. 后端 `pytest`（使用隔离的 SQLite 临时库，无需 Docker/PostgreSQL），共 **10 个用例**，覆盖：
   - 健康检查、种子数据、大屏统计
   - 事件上报与影响区域分析（重大事件外扩至全部片区、30 户/3 家重点单位）
   - 派工到复水全流程、停水/复水通知、阀门联动关闭与重开
   - 重复派工与非法状态流转被拒绝
   - 物料不足阻塞 → 紧急调拨 → 补料到货自动复工
   - 道路封闭自动绕行重规划、通知受影响用户、道路恢复自动续单
   - 无可用队伍时派工被拒绝
2. 前端 `vite build` 生产构建检查

仅运行后端测试：

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## 🧑‍💻 本地开发模式（不使用 Docker）

```bash
# 1. PostgreSQL
createdb watergrid

# 2. 后端
cd backend
python -m pip install -r requirements.txt
export WATER_DATABASE_URL="postgresql+psycopg2://water:water@localhost:5432/watergrid"
uvicorn app.main:app --reload --port 8000

# 3. 前端（自动代理 /api → :8000）
cd frontend
npm install
npm run dev   # http://localhost:5173
```

无 PostgreSQL 时也可用 SQLite 快速体验：

```bash
WATER_DATABASE_URL="sqlite:///./dev.db" uvicorn app.main:app --reload
```

## 📁 目录结构

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口、CORS、启动建表+种子
│   │   ├── models.py            # SQLAlchemy 模型（事件/工单/阀门/队伍/物料/封路/通知…）
│   │   ├── schemas.py           # Pydantic 请求/响应模型
│   │   ├── seed.py              # 演示数据
│   │   ├── routers/             # API 路由
│   │   └── services/            # geometry 几何计算 / impact 影响分析
│   │                            # dispatch 派工 / progress 进度与重规划 / notifications 通知
│   └── tests/                   # pytest 用例
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # 监控/上报/物料/封路/通知 五个页面
│   │   └── components/MapView.jsx  # SVG 管网态势图
│   ├── Dockerfile               # 多阶段构建（node 构建 + nginx 托管）
│   └── nginx.conf               # /api 反代后端
├── scripts/
│   ├── start.sh                 # 一键启动
│   ├── stop.sh                  # 停止/清理
│   └── test.sh                  # 一键测试
└── docker-compose.yml
```

## 🔁 典型业务闭环（演示路径）

1. 打开 **事件上报**，在地图上点击定位漏点（如望湖片区内），选择“较大/重大 + DN500”，提交。
2. 在 **抢修监控** 选中事件 → **影响区域分析**，地图高亮受影响片区、待关阀门、停水用户。
3. 点击 **智能派工**：系统选择最近队伍，预占物料，群发短信停水通知。
4. 依次点击 ①～⑦ 进度按钮，观察阀门关闭、地图队伍移动与复水通知。
5. 想体验自动重规划：
   - **物料不足**：用重大 + DN800 上报派工（种子库存必然缺料），或修复中点“报告物料不足”；在物料页调拨后点击“补料已到货”。
   - **道路封闭**：工单派出后，在道路封闭页登记一条横断队伍路线的封闭路段（默认值即可演示），工单立即绕行 +30 分钟并通知用户；点击“道路恢复”工单自动继续。
