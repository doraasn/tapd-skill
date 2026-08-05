"""
TAPD 今日待办查询
用法：python3 scripts/todo_query.py

全面使用 TAPD REST API 替代 mcporter，解决超时问题。
使用单个有限线程池查询各项目的 3 种实体类型（story/bug/task），按 owner 筛选。
REST API 返回 ~0.4s/次，对比 mcporter ~12s/次，提速约 30 倍。
"""
import sys, os, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# ----- 配置加载 -----
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(SKILL_DIR, "config.json"), encoding="utf-8") as f:
    CONFIG = json.load(f)
PROJECTS = [p for p in CONFIG.get("projects", []) if p.get("type") == "project"]
USER_NICK = CONFIG.get("user", {}).get("nick", "")

# ----- Token 加载 -----
def _load_token():
    mcp_path = os.path.join(SKILL_DIR, "config", "mcporter.json")
    with open(mcp_path, encoding="utf-8") as f:
        cfg = json.load(f)
    args = cfg.get("mcpServers", {}).get("tapd-cn-mcp", {}).get("args", [])
    for i, a in enumerate(args):
        if a == "--access-token" and i + 1 < len(args):
            return args[i + 1]
    return None

TOKEN = _load_token()

# ----- 活跃状态列表（排除已关闭/已结束的状态） -----
# story: planning, developing, status_7~20 等为活跃状态
# bug: new, in_progress, resolved 等为活跃状态，closed 为非活跃
# 注意：REST API 默认不会返回已删除的条目，但可能会返回 closed 的 bug
CLOSED_STORY_STATUSES = {"closed", "resolved", "rejected", "status_20"}  # status_20 = 项目经理已验收；rejected = 已拒绝
CLOSED_BUG_STATUSES = {"closed"}

# ----- 状态码映射 -----
STATUS_LABELS = {
    "planning": "规划中",
    "developing": "开发中",
    "status_7": "已下发",
    "status_10": "设计中",
    "status_11": "开发中",
    "status_16": "测试中",
    "status_20": "已验收",
    "resolved": "已验收",
    "closed": "已关闭",
    "new": "新建",
    "in_progress": "处理中",
    "confirmed": "已确认",
    "rejected": "已拒绝",
}


def query_entity_type(pid, entity_type):
    """
    用 REST API 查询某项目某类型的待办，按 owner 筛选。
    返回 [{...}] 格式。
    """
    if entity_type == "story":
        ep = "stories"
        fields = "id,name,owner,status,priority_label,effort,begin,due,priority"
        owner_field = "owner"
        type_key = "Story"
    elif entity_type == "task":
        ep = "tasks"
        fields = "id,name,owner,status,priority_label,effort,begin,due"
        owner_field = "owner"
        type_key = "Task"
    else:  # bug
        ep = "bugs"
        fields = "id,title,current_owner,status,priority_label,priority,severity"
        owner_field = "current_owner"
        type_key = "Bug"

    query = urlencode({
        "workspace_id": pid,
        "fields": fields,
        "limit": 200,
        owner_field: USER_NICK,
    })
    url = f"https://api.tapd.cn/{ep}?{query}"
    req = Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "tapd-skill/1.0",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
    except Exception as error:
        raise RuntimeError(f"{pid}/{entity_type}: {error}") from error

    items = body.get("data", [])
    if isinstance(items, dict):
        items = [items]
    if not items:
        return []

    # 解析并过滤非活跃状态
    parsed = []
    for raw in items:
        obj = raw.get(type_key, {})
        status = obj.get("status", "")
        # 跳过已关闭/已结束的
        if entity_type == "bug":
            if status in CLOSED_BUG_STATUSES:
                continue
        elif entity_type == "story":
            if status in CLOSED_STORY_STATUSES:
                continue
        elif entity_type == "task":
            if status in CLOSED_STORY_STATUSES:
                continue

        if entity_type == "story":
            entry = {
                "type": "需求",
                "id": obj.get("id", ""),
                "name": obj.get("name", ""),
                "owner": obj.get("owner", ""),
                "priority": obj.get("priority_label", "") or obj.get("priority", ""),
                "begin": obj.get("begin", "") or "",
                "due": obj.get("due", "") or "",
                "effort": obj.get("effort", "") or "",
                "status": STATUS_LABELS.get(status, status),
            }
        elif entity_type == "task":
            entry = {
                "type": "任务",
                "id": obj.get("id", ""),
                "name": obj.get("name", ""),
                "owner": obj.get("owner", ""),
                "priority": obj.get("priority_label", "") or obj.get("priority", ""),
                "begin": obj.get("begin", "") or "",
                "due": obj.get("due", "") or "",
                "effort": obj.get("effort", "") or "",
                "status": STATUS_LABELS.get(status, status),
            }
        else:
            entry = {
                "type": "缺陷",
                "id": obj.get("id", ""),
                "name": obj.get("title", ""),
                "owner": obj.get("current_owner", ""),
                "priority": obj.get("priority_label", "") or obj.get("priority", ""),
                "begin": "",
                "due": "",
                "effort": "",
                "status": STATUS_LABELS.get(status, status),
            }
        parsed.append(entry)
    return parsed


def main():
    if not TOKEN:
        print("[错误] 无法加载 TAPD Token，请检查 config/mcporter.json")
        sys.exit(1)

    print("=== 今日待办查询 ===")
    sys.stdout.flush()

    # 使用单层、有限并发，避免在双核 N1 上为每个项目再创建线程池。
    results = {}
    errors = []
    jobs = [(p, entity_type) for p in PROJECTS for entity_type in ("story", "bug", "task")]
    max_workers = min(8, max(1, len(jobs)))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {}
        for project, entity_type in jobs:
            future = ex.submit(query_entity_type, project["id"], entity_type)
            futures[future] = (project, entity_type)
        for f in as_completed(futures):
            project, entity_type = futures[f]
            try:
                data = f.result()
            except Exception as error:
                errors.append(str(error))
                continue
            if data:
                project_result = results.setdefault(
                    project["id"],
                    (project["name"], {}),
                )
                project_result[1][entity_type] = data

    if errors:
        print(f"[警告] {len(errors)} 个 TAPD 请求失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    if errors and len(errors) == len(jobs):
        print("[错误] TAPD API 全部请求失败", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("(无待办事项)\n")
        return

    print(f"总共 {len(results)} 个项目有数据\n")

    # 按项目逐个输出
    for p in PROJECTS:
        wid = p["id"]
        if wid not in results:
            continue
        pname, data = results[wid]

        all_rows = []
        for et in ("story", "task", "bug"):
            items = data.get(et, [])
            all_rows.extend(items)

        if not all_rows:
            continue

        print(f"## {pname}\n")

        for t in ["需求", "任务", "缺陷"]:
            group = [r for r in all_rows if r["type"] == t]
            if not group:
                continue
            print(f"**{t}（{len(group)} 条）**\n")
            print(f"| ID | 需求 | 负责人 | 优先级 | 状态 | 排期 | 预估工时 |")
            print(f"|-----|------|--------|--------|------|------|----------|")
            for r in group:
                name = r["name"]
                prio = r["priority"]
                if prio in ("High", "Urgent"):
                    name = f"**{name}**"
                schedule = f"{r['begin']}~{r['due']}" if r["begin"] else "-"
                effort = f"{r['effort']}h" if r["effort"] else "-"
                print(f"| {r['id'][-8:]} | {name} | {r['owner'] or '-'} | {prio or '-'} | {r['status']} | {schedule} | {effort} |")
            print()


if __name__ == "__main__":
    main()
