"""
TAPD 今日待办查询
用法: python scripts/todo_query.py
"""
import sys
from tapd_common import run_mcporter, get_stories_by_api, PROJECTS


def get_todo(pid, entity_type):
    raw = run_mcporter("tapd-cn-mcp.get_todo", workspace_id=pid, entity_type=entity_type, limit="100")
    if raw is None:
        return []
    return raw.get("data", [])


def main():
    print("=== 正在查询今日待办 ===")
    sys.stdout.flush()

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 第1步：查所有项目的 todo
    todo_data = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {}
        for p in PROJECTS:
            for et in ["story", "bug", "task"]:
                f = ex.submit(get_todo, p["id"], et)
                futures[f] = (p, et)
        for f in as_completed(futures):
            p, et = futures[f]
            try:
                items = f.result()
            except Exception:
                continue
            if items:
                todo_data.setdefault(p["id"], {})[et] = (p["name"], items)

    if not todo_data:
        print("(暂无待办)\n")
        return

    # 第2步：对有 story/task 的查详情（用 TAPD REST API 绕过 MCP Server 的 limit bug）
    detail_cache = {}
    detail_futures = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for wid, entities in todo_data.items():
            for et in ["story", "task"]:
                if et in entities:
                    f = ex.submit(get_stories_by_api, wid, et,
                                  fields="id,name,begin,due,owner,effort,priority_label,developer")
                    detail_futures.append((f, wid, et))
        for f, wid, et in detail_futures:
            try:
                detail_cache.setdefault(wid, {})[et] = f.result()
            except Exception:
                pass

    # 第3步：输出表格
    print(f"完成查询: {len(todo_data)} 个项目有数据\n")

    for p in PROJECTS:
        wid = p["id"]
        if wid not in todo_data:
            continue
        pname = p["name"]
        all_rows = []

        for et in ["story", "task", "bug"]:
            entry = todo_data[wid].get(et)
            if not entry:
                continue
            _, items = entry
            details = detail_cache.get(wid, {}).get(et, {})

            for item in items:
                if et == "story":
                    s = item.get("Story", {})
                    sid = s.get("id", "")
                    d = details.get(sid, {})
                    all_rows.append({
                        "type": "需求", "id": sid[-8:] if sid else "",
                        "name": d.get("name", s.get("name", "")),
                        "owner": d.get("owner", ""),
                        "priority": d.get("priority_label", "") or s.get("priority", ""),
                        "begin": d.get("begin", "") or "",
                        "due": d.get("due", "") or "",
                        "effort": d.get("effort", "") or ""
                    })
                elif et == "task":
                    t = item.get("Task", {})
                    tid = t.get("id", "")
                    d = details.get(tid, {})
                    all_rows.append({
                        "type": "任务", "id": tid[-8:] if tid else "",
                        "name": d.get("name", t.get("name", "")),
                        "owner": d.get("owner", t.get("owner", "")),
                        "priority": d.get("priority_label", "") or t.get("priority", ""),
                        "begin": d.get("begin", "") or "",
                        "due": d.get("due", "") or "",
                        "effort": d.get("effort", "") or ""
                    })
                elif et == "bug":
                    b = item.get("Bug", {})
                    all_rows.append({
                        "type": "缺陷", "id": b.get("id", "")[-8:] if b.get("id") else "",
                        "name": b.get("title", b.get("name", "")),
                        "owner": b.get("current_owner", ""),
                        "priority": b.get("priority", ""),
                        "begin": "", "due": "", "effort": ""
                    })

        if all_rows:
            print(f"## {pname}\n")
            for t in ["需求", "任务", "缺陷"]:
                group = [r for r in all_rows if r["type"] == t]
                if not group:
                    continue
                print(f"**{t}（{len(group)} 项）**\n")
                print(f"| ID | 需求 | 处理人 | 优先级 | 排期 | 预估工时 |")
                print(f"|----|------|--------|--------|------|----------|")
                for r in group:
                    name = r["name"]
                    prio = r["priority"]
                    if prio in ("High", "Urgent"):
                        name = f"**{name}**"
                    schedule = f"{r['begin']}~{r['due']}" if r['begin'] else "-"
                    effort = f"{r['effort']}h" if r['effort'] else "-"
                    print(f"| {r['id']} | {name} | {r['owner'] or '-'} | {prio or '-'} | {schedule} | {effort} |")
                print()

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
