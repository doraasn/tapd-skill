---
name: tapd-skill
description: 通过 mcporter + MCP Server 连接 TAPD，管理需求/任务/缺陷/工时/迭代/排期。当用户需要查询、修改 TAPD 项目中需求、缺陷、任务、迭代等信息时使用。
allowed-tools:
disable: false
---

# TAPD 接入与操作 Skill

通过 mcporter + MCP Server 连接 TAPD，管理需求/任务/缺陷/工时/迭代/排期。

Skill 涉及的角色：
- **研发**：查待办、记工时、排期、缺陷跟进
- **测试**：需求关联 bug 跟进、bug 创建与跟踪
- **研发 leader**：团队工作汇总、迭代进度
- **项目管理**：迭代管理、发布计划、工作总结

---

## 初始化流程（AI 首次加载时执行）

AI 加载本 Skill 后，按以下步骤做初始化检查：

### Step 1 — 检查并安装环境依赖

首先检测操作系统（`sys.platform`），然后按平台执行安装检查：

**检查顺序：若某工具未安装，则执行安装命令后再继续。**

| 工具 | 检查命令 | 安装命令 |
|------|----------|----------|
| mcporter | `mcporter --help` | `npm install -g mcporter` |
| mcp-server-tapd | `mcp-server-tapd --help` 或 `python -m pip show mcp-server-tapd` | `python -m pip install mcp-server-tapd` |

**查找 mcp-server-tapd 的安装路径（用于后续写入 config）：**

Windows:
```powershell
python -c "import sys; print(sys.exec_prefix)"
# 结果类似 C:\DevTools\Python\Python313
# mcp-server-tapd 在 {exec_prefix}\Scripts\mcp-server-tapd.exe
```

macOS / Linux:
```bash
which mcp-server-tapd 2>/dev/null || python3 -c "import sys; print(f'{sys.exec_prefix}/bin/mcp-server-tapd')"
```

### Step 2 — 创建/验证配置文件

**2a. 检查 `config/mcporter.json` 是否存在**

- 若文件**不存在**：参考 `config/mcporter.template.json` 创建。需要确定两个关键信息：
  1. **mcp-server-tapd 路径**（Step 1 中已找到）→ 填入 `command` 字段
  2. **TAPD Access Token** → 向用户询问（见下方 2b）

- 若文件**存在但 Token 为 `<your-token>` 占位符**：直接进入 2b

**2b. 获取 Token（必填）**

向用户询问：

> "请提供你的 TAPD Access Token"

将 Token 写入 `config/mcporter.json` 的 `args[1]` 位置。

**Token 获取方式**：
1. 浏览器打开 [https://www.tapd.cn/personal_settings/index?tab=personal_token](https://www.tapd.cn/personal_settings/index?tab=personal_token)
2. 点击右上角 **"创建个人访问令牌"** 按钮
3. 设置名称和有效期，创建后复制 Token 值

### Step 3 — 验证连接并自动发现身份

用 Token 测试连通性并自动获取用户昵称：

```powershell
# 查项目列表（验证 Token 有效性）
mcporter --config <skill>/config/mcporter.json call tapd-cn-mcp.get_user_participant_projects
```

**昵称自动发现**：Token 有效后，调用 `get_todo` 查看返回数据中的 `creator` 字段即可确认当前用户的昵称，或者从 `get_workspace_users` 列表中推断。将发现的昵称写入 `config.json` 的 `user.nick`。

> **注意**：所有数据的"处理人"字段都使用用户昵称（如 `owner`、`developer`、`current_owner`），不依赖 `user_id`，因此只需昵称即可完成全部查询操作。

### Step 4 — 自动发现并保存项目列表

连接成功后，调用 `get_user_participant_projects` 获取完整的项目列表，然后将结果写入 `config.json` 的 `projects` 字段：

```json
"projects": [
  { "id": "30139507", "name": "敬业研发大数据", "type": "project" },
  ...
]
```

> 过滤掉 `category: "organization"` 的项目（组织/公司，非项目空间）。

### Step 5 — 确认可用

通知用户已就绪，列出其参与的项目总数。

---

## 配置更新规则

| 场景 | 操作 | 目标文件 |
|------|------|----------|
| 用户主动提供新 Token | 更新 `args[1]` 值 | `config/mcporter.json` |
| 用户发起查待办/查花费等操作 | 自动使用 `config.json` 中的项目列表遍历 | （只读）|
| 用户新增项目参与 | 重新运行 Step 4 同步项目列表 | `config.json` |
| 用户提供新的优先级映射 | 更新 `priority_mapping` | `config.json` |

> **重要**：任何时候都不要硬编码 Token 到 SKILL.md 或 Python 脚本中。Token 只存在于 `config/mcporter.json`。

---

## 目录结构

```
tapd/                          # skill 根目录
├── SKILL.md                   # 本文件 — Skill 主说明（AI 加载入口）
├── config.json                # 个人配置（用户身份、项目列表、优先级映射）
├── config.template.json       # 配置模板（供新用户初始化参考）
├── scripts/
│   ├── tapd_common.py         # 共享模块（mcporter 连接、配置加载、工作日工具）
│   ├── todo_query.py          # 查今日待办（遍历所有项目）
│   ├── timesheet_query.py     # 查花费（按日期范围，自动汇总）
│   ├── add_hours.py           # 记工时（含父需求检测、重复检测）
│   ├── schedule.py            # 排期（自动计算工作日和工时）
│   ├── reschedule.py          # 整体移期（周末自动顺延）
│   ├── tapd.ps1               # 总入口脚本（Windows PowerShell）
│   └── tapd.sh                # 总入口脚本（macOS / Linux Bash）
└── config/
    ├── mcporter.json          # MCP Server 运行时配置（含 Token）
    └── mcporter.template.json # mcporter 配置模板
```

**跨平台概览：**

| | Windows | macOS | Linux |
|--|---------|-------|-------|
| mcporter 安装 | `npm install -g mcporter` | 同左 | 同左 |
| mcp-server-tapd | `pip install mcp-server-tapd` | `pip3 install mcp-server-tapd` | 同左 |
| 命令行工具 | `mcporter.cmd` | `mcporter` | `mcporter` |
| 便捷脚本 | `.\scripts\tapd.ps1` | `bash scripts/tapd.sh` | 同左 |
| Python | `python` | `python3` | `python3` |

### 内置脚本速查

| 脚本 | 功能 | 自动处理的坑 |
|------|------|-------------|
| `todo_query.py` | 查今日待办，按项目+类型分组展示 | 并行查所有项目（避免串行超时） |
| `timesheet_query.py` | 查花费，按项目汇总，支持日期范围 | 遍历所有项目，展示格式符合约定 |
| `add_hours.py` | 记工时 | ① 检测同一天同一需求是否已有记录（有则 update） ② 检测父需求（API 422） |
| `schedule.py` | 排期，自动计算工作日和工时 | 开始日期遇周末自动顺延到周一 |
| `reschedule.py` | 整体移期，多需求批量后移 | 每个需求从新的开始日重新推算，周末顺延 |

**便捷入口（推荐）：**
- Windows: `.\scripts\tapd.ps1 <命令> [参数]`
- macOS/Linux: `bash scripts/tapd.sh <命令> [参数]`

其中 `<命令>` 支持 `todo` / `timesheet` / `hours` / `schedule` / `move` / `call` / `list`。

---

## 前提安装

| 工具 | Windows | macOS / Linux | 验证 |
|------|---------|---------------|------|
| Node.js | `node --version` | `node --version` | ≥ v18 |
| mcporter | `npm install -g mcporter` | `npm install -g mcporter` | `mcporter --help` |
| Python | `python --version` | `python3 --version` | ≥ v3.10 |
| pip | `python -m pip --version` | `python3 -m pip --version` | — |
| mcp-server-tapd | `python -m pip install mcp-server-tapd` | `python3 -m pip install mcp-server-tapd` | `mcp-server-tapd --help` |

---

## 连接方式

### MCP 配置

MCP Server 定义在 `config/mcporter.json`。

**Linux 示例：**
```json
{
  "mcpServers": {
    "tapd-cn-mcp": {
      "command": "/usr/local/bin/mcp-server-tapd",
      "args": ["--access-token", "<TOKEN>", "--mode", "stdio"],
      "env": {}
    }
  }
}
```

**调用方式：**
```
mcporter --config <skill>/config/mcporter.json call tapd-cn-mcp.<工具名> [key=value ...]
```

### 参数传递

- 顶级参数：`key=value` 格式，如 `workspace_id=30139507`
- options 嵌套参数：`options.entity_type=story`（mcporter 点号嵌套语法）

### 用户身份

| 字段 | 值 |
|------|-----|
| 昵称 | 俞金涛 |

### 参与项目

详见 `config.json` 的 `projects` 字段。

---

## MCP 工具参考

### 项目

| 工具 | 用途 | 示例 |
|------|------|------|
| `get_user_participant_projects` | 获取参与的项目列表 | `nick="俞金涛"` |
| `get_workspace_info` | 获取项目信息 | `workspace_id=<id>` |

### 需求/任务

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `get_stories_or_tasks` | 查询需求/任务详情 | `workspace_id`, `options.entity_type` |
| `get_story_or_task_count` | 获取需求数量 | `workspace_id`, `options.entity_type` |
| `create_story_or_task` | 创建需求/任务 | `workspace_id`, `name` |
| `update_story_or_task` | 更新需求/任务（含排期、工时） | `workspace_id`, `options` |
| `get_todo` | 获取当前用户待办 | `workspace_id`, `entity_type` |
| `get_stories_fields_info` | 获取需求字段及候选值 | `workspace_id` |
| `get_entity_custom_fields` | 获取自定义字段配置 | `workspace_id`, `options.entity_type` |

### 缺陷

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `get_bug` | 查询缺陷 | `workspace_id` |
| `get_bug_count` | 获取缺陷数量 | `workspace_id` |
| `create_bug` | 创建缺陷 | `workspace_id`, `title` |
| `update_bug` | 更新缺陷 | `workspace_id`, `options` |

### 工时

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `add_timesheets` | 添加工时花费 | `workspace_id`, `options` |
| `update_timesheets` | 更新工时花费 | `workspace_id`, `options` |
| `get_timesheets` | 查询已有工时 | `workspace_id` |

### 迭代

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `get_iterations` | 获取迭代列表 | `workspace_id` |
| `create_iteration` | 创建迭代 | `workspace_id`, `name` |
| `update_iteration` | 更新迭代 | `workspace_id`, `options` |

### 工作流

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `get_workflows_status_map` | 状态中英文映射 | `workspace_id`, `options.system` |
| `get_workflows_all_transitions` | 工作流流转细则 | `workspace_id` |
| `get_workflows_last_steps` | 工作流结束状态 | `workspace_id` |

### 关联 & 其他

| 工具 | 用途 |
|------|------|
| `get_related_bugs` | 需求关联的缺陷 |
| `get_entity_relations` / `entity_relations` | 获取/创建关联关系 |
| `get_image` | 获取图片下载链接 |
| `get_entity_attachments` | 获取附件信息 |
| `create_comments` | 添加评论 |
| `get_tcases` | 获取测试用例 |
| `get_wiki` | 获取 Wiki |
| `get_release_info` | 获取发布计划 |
| `get_workspace_users` | 获取项目成员列表 |
| `send_qiwei_message` | 发送企业微信消息 |

---

## 角色场景

### 研发

#### 查待办
- 今日有哪些待处理的需求、缺陷、任务
- 脚本：`bash scripts/tapd.sh todo`
- MCP：`get_todo` 遍历所有项目（story / bug / task）
- 查询规则：不要加状态过滤，需求看 `developer`/`owner`，缺陷看 `current_owner`

#### 缺陷跟进
- 有多少分配给自己的 bug 单、分别是什么状态
- MCP：`get_bug` 查处理人为我、筛选状态（非结束状态）
- 提示：缺陷查询**不要用 developer 参数**，改用 `current_owner` 过滤

#### 记工时
- 记录今天在某需求上的工时花费
- 脚本：`bash scripts/tapd.sh hours <项目ID> <需求ID> <时数>`
- 规则：同一天同一需求只能记一条（有则自动 update），父需求不可记

#### 排期
- 为需求设置开始/结束时间
- 脚本：`bash scripts/tapd.sh schedule <项目ID> <需求ID> <开始日期> <工作日数>`
- 规则：1 天 = 8 小时，遇周末自动顺延

#### 个人工作总结
- 今天/昨天完成了哪些需求，解决了哪些 bug，还有哪些待办
- 适用于日报/站会同步

### 测试

#### 需求关联 bug 跟进
- 某需求在测试阶段还有多少未解决的 bug
- 作法和工具：
  1. `get_related_bugs` 传入需求 ID，获取关联的缺陷 ID
  2. 遍历缺陷 ID 用 `get_bug` 查状态

#### Bug 创建与跟踪
- 创建新缺陷：`create_bug workspace_id=<id> title="<标题>"`
- 更新缺陷状态：`update_bug` + `get_workflows_all_transitions` 先查可流转状态

### 研发 Leader

#### 团队工作汇总
- 今天团队产生了/修复了多少 bug 单

#### 迭代进度
- 当前迭代完成了哪些需求

### 项目管理

#### 发布计划
- 各版本/发布计划里包含哪些需求

#### 工作总结
- 本迭代完成的需求汇总，用于发布日志

---

## 常用操作

### 1. 查待办

```bash
bash scripts/tapd.sh todo
```

### 2. 查花费

```bash
bash scripts/tapd.sh timesheet
bash scripts/tapd.sh timesheet 2026-07-20
```

### 3. 记工时

```bash
bash scripts/tapd.sh hours 30139507 <需求ID> 4
bash scripts/tapd.sh hours 30139507 <需求ID> 8 2026-07-20 "备注"
```

### 4. 排期

```bash
bash scripts/tapd.sh schedule 30139507 <需求ID> 2026-07-21 5
```

### 5. 整体移期

```bash
bash scripts/tapd.sh move 30139507 3 <需求ID1> <需求ID2> ...
```

### 6. 直接调 MCP

```bash
bash scripts/tapd.sh call tapd-cn-mcp.get_stories_or_tasks workspace_id=30139507 options.entity_type=story
```

---

## 展示格式

### 待办
```
| 项目 | ID | 需求 | 处理人 | 优先级 | 排期 | 预估工时 |
```
- High 标粗；排期为空显示 "-"；按项目分组

### 花费
```
**项目名（总工时）**
1. 需求名称：花费备注；
2. 需求名称：花费备注。
**合计：xh**
```
- 末条句号，其余分号；工时统一 h；不需要链接/表格/ID

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

1. **result 字段嵌套**：`get_stories_or_tasks` 的 result 是 JSON 字符串，需二次 `json.loads`
2. **update 返回值**同理也是嵌套 JSON
3. **add_timesheets 422**：缺少 entity_type/entity_id
4. **get_timesheets 无 result 包装**：返回直接是 data 数组
5. **effort 是字符串**，非数字
6. **父需求不可记工时**（API 422）
7. **bug 查 developer 有 bug**：返回不相关数据；改用 current_owner
8. **查待办不要加状态过滤**：用户要全部未完成的
9. **并发查询**：用 ThreadPoolExecutor 并行，避免串行超时
10. **Windows 环境 Token 必须用 --access-token 参数传递**，不能仅依赖环境变量
11. **mcporter 参数不要拼成一个字符串**：Python subprocess 中每个参数是列表中的独立元素
12. **options.id 过滤不生效**：MCP Server 的 id 参数不可用，无法按 ID 过滤查询
13. **options.limit / page 不生效**：`get_stories_or_tasks` 的分页和 limit 均被忽略，始终只返回固定 10 条
14. **TAPD REST API 替代方案**：`tapd_common.py` 中提供了 `get_stories_by_api()` 函数，直接用 TAPD REST API（`https://api.tapd.cn/stories`）查询，可获取全部数据。Token 自动从 `config/mcporter.json` 中提取
15. **macOS/Linux 脚本权限**：`scripts/tapd.sh` 首次使用前需 `chmod +x scripts/tapd.sh`
16. **macOS/Linux Python 命令**：使用 `python3` 而非 `python`，`pip3` 而非 `pip`
