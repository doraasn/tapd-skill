---
name: tapd-skill
description: 通过 TAPD REST API 连接和管理需求/任务/缺陷/工时/迭代/排期。当用户需要查询、修改 TAPD 项目中需求、缺陷、任务、迭代等信息时使用。
allowed-tools:
disable: false
---

# TAPD 接入与操作 Skill

通过 TAPD REST API 连接 TAPD，管理需求/任务/缺陷/工时/迭代/排期。所有操作均走 REST API，不需要 mcporter。

Skill 涉及的角色：
- **研发**：查待办、记工时、排期、缺陷跟进
- **测试**：需求关联 bug 跟进、bug 创建与跟踪
- **研发 leader**：团队工作汇总、迭代进度
- **项目管理**：迭代管理、发布计划、工作总结

---

## 初始化流程（AI 首次加载时执行）

AI 加载本 Skill 后，按以下步骤做初始化检查：

### Step 1 — 检查环境依赖

| 工具 | 检查/安装 | 必要性 |
|------|-----------|--------|
| Python ≥ 3.10 | `python3 --version` | **必需** |
| requests | `pip3 install requests` | **必需** |

不再需要 mcporter 或 mcp-server-tapd，所有操作均走 REST API。

### Step 2 — 获取 Token（必填）

向用户询问 TAPD Access Token，写入 `config/mcporter.json` 的 `args[1]` 位置。

**Token 获取方式**：
1. 浏览器打开 [个人访问令牌设置](https://www.tapd.cn/personal_settings/index?tab=personal_token)
2. 点击 **"创建个人访问令牌"**
3. 设置名称和有效期，创建后复制 Token 值

### Step 3 — 验证连通性

```bash
python3 -c "from scripts.tapd_common import PROJECTS; print(f'已加载 {len(PROJECTS)} 个项目')"
```

### Step 4 — 自动发现项目列表

连接成功后，从 `config.json` 查看已发现的项目列表。如需刷新，调用 REST API 重新查询。

---

## 目录结构

```
tapd/                          # skill 根目录
├── SKILL.md                   # 本文件 — Skill 主说明（AI 加载入口）
├── config.json                # 个人配置（用户身份、项目列表、优先级映射）
├── scripts/
│   ├── tapd_common.py         # 共享模块（REST API 请求、配置加载、工作日工具）
│   ├── todo_query.py          # 查今日待办（遍历所有项目）
│   ├── timesheet_query.py     # 查花费（按日期范围，自动汇总）
│   ├── add_hours.py           # 记工时（含父需求检测、重复检测）
│   ├── schedule.py            # 排期（自动计算工作日和工时）
│   ├── reschedule.py          # 整体移期（周末自动顺延）
│   └── tapd.sh                # 总入口脚本（Linux / macOS）
└── config/
    └── mcporter.json          # 配置文件（含 Token，仅用于存 Token 和 s=mcp 写入）
```

---

## 连接方式

所有操作均通过 TAPD REST API 直连：
- Token 从 `config/mcporter.json` 提取
- 支持 endpoints: `/stories`, `/tasks`, `/bugs`, `/timesheets`
- 响应极快（~0.4s/请求），不限制返回条数
- story/task 更新需使用 JSON body + `?s=mcp` 参数（参考 `_api_post_json()` 实现）
- 不再需要 mcporter / mcp-server-tapd

### 用户身份

| 字段 | 值 |
|------|-----|
| 昵称 | 俞金涛 |

---

## 脚本速查

| 操作 | 脚本 | REST 端点 |
|------|------|-----------|
| 查待办 | `todo_query.py` | `GET /stories?owner=俞金涛`、`GET /bugs?current_owner=` |
| 查工时 | `timesheet_query.py` | `GET /timesheets?owner=&spentdate=` |
| 记工时 | `add_hours.py` | `POST /timesheets` |
| 排期 | `schedule.py` | `POST /stories?s=mcp`（JSON body） |
| 移期 | `reschedule.py` | `GET /stories` + `POST /stories?s=mcp` |

**便捷入口：**
```bash
bash scripts/tapd.sh todo
bash scripts/tapd.sh timesheet [日期]
bash scripts/tapd.sh hours <项目ID> <需求ID> <时数> [日期] [备注]
bash scripts/tapd.sh schedule <项目ID> <需求ID> <日期> <工作日数>
bash scripts/tapd.sh move <项目ID> <天数> <需求ID...>
```

### 内置脚本说明

| 脚本 | 功能 | 自动处理的坑 |
|------|------|-------------|
| `todo_query.py` | 查今日待办，按项目+类型分组展示 | 并行查所有项目（避免串行超时） |
| `timesheet_query.py` | 查花费，按项目汇总，支持日期范围 | 自动补全需求名称 |
| `add_hours.py` | 记工时 | ① 检测同一天同一需求是否已有记录（有则 update） ② 检测父需求（API 422） |
| `schedule.py` | 排期，自动计算工作日和工时 | 开始日期遇周末自动顺延到周一 |
| `reschedule.py` | 整体移期，多需求批量后移 | 每个需求从新的开始日重新推算，周末顺延 |

---

## 展示格式

### 待办
```
| ID | 需求 | 负责人 | 优先级 | 状态 | 排期 | 预估工时 |
```
- 必须包含**负责人**列，展示给用户时不可省略
- High 标粗；排期为空显示 "-"；按项目分组
- **状态显示中文**：每次查询时动态获取各项目的 `workflows/status_map` 映射（内存缓存），状态码转中文，不硬编码
- **过滤规则：终态（已验收/已拒绝/已关闭/已实现）条目不展示**

### 花费
```
**项目名（总工时）**
1. 需求名称：花费备注；
2. 需求名称：花费备注。
**合计：xh**
```
- 末条句号，其余分号；工时统一 h；不需要链接/表格/ID
- 需求名称由脚本自动补全（查 timesheets API 后关联 stories API）

### 排期
```
| 需求 | 排期 | 工作日 | 预估工时 |
```

---

## 优先级映射

| TAPD | 中文 |
|------|------|
| Urgent | 紧急 |
| High | 高 |
| Middle | 中 |
| Low | 低 |
| Nice To Have | 无关紧要 |

---

## 踩坑记录

1. **父需求不可记工时**：有子需求的父级 story 调用 `POST /timesheets` 返回 422
2. **bug 查 developer 无效**：缺陷查询不要用 `developer` 参数，改用 `current_owner`
3. **effort 是字符串**：TAPD API 返回的 `effort` 字段是字符串而非数字
4. **查待办不要加状态过滤**：用户要所有未完成的，让脚本自动过滤终态（已验收/已拒绝/已关闭/已实现）的
5. **并发查询优先**：用 ThreadPoolExecutor 并行查项目，避免串行超时
6. **REST API > mcporter**：查询和工时操作全部使用 REST API（`https://api.tapd.cn/*`），速度比 mcporter 快约 30 倍（0.4s vs 12s）
7. **story/task 更新需要 JSON body + ?s=mcp**：普通 form POST 到 `/stories/update` 返回 403。必须用 JSON body + `?s=mcp` 参数 + `Via: mcp` header，直接 POST 到 `/stories`（不是 `/stories/update`）
8. **待办表格必须包含"负责人"列**：任何时候都不可省略"负责人"列
9. **各项目状态码含义不同**：同一 status_18 在芜湖=产品已验收、在其他项目可能是别的含义。不要硬编码状态码映射，每次查询时动态获取各项目 `workflows/status_map` 并缓存（`get_status_map()`），用中文名判断终态（含"已验收/已拒绝/已关闭/已实现"即过滤）
9. **花费查询格式**：需求名称 + 备注，不要显示单独工时。格式为 `1. 需求名称：花费备注；`
