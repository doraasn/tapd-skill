"""
TAPD 整体移期
将指定项目的多个需求整体后移 N 天，自动处理周末顺延。
各需求独立计算，并行更新以提升速度。

用法:
  python scripts/reschedule.py <项目ID> <天数> <需求ID1> [需求ID2 ...]

示例:
  python scripts/reschedule.py 30139507 3 1130139507001006273 1130139507001006126
"""
import sys, json
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tapd_common import run_mcporter, parse_result, working_days, find_end_date, next_workday, PROJECTS


def get_story(pid, sid):
    """获取需求的 begin/due/effort"""
    raw = run_mcporter("tapd-cn-mcp.get_stories_or_tasks", workspace_id=pid,
                       options={"entity_type": "story", "id": sid,
                                "fields": "id,name,begin,due,effort,priority_label,priority"})
    items = parse_result(raw)
    if items:
        s = items[0].get("Story", {})
        return {
            "id": s.get("id", sid),
            "name": s.get("name", ""),
            "begin": s.get("begin"),
            "due": s.get("due"),
            "effort": s.get("effort", "0")
        }
    return None


def move_one_story(pid, move_days, sid):
    """处理单个需求的移期"""
    s = get_story(pid, sid)
    if not s:
        return None, f"{sid}: 未找到需求"
    if not s["begin"]:
        return None, f"{sid} ({s['name']}): 无排期，跳过"

    old_begin = date.fromisoformat(s["begin"])
    old_due = date.fromisoformat(s["due"])
    old_workdays = working_days(old_begin, old_due) if old_begin != old_due else 1

    new_begin = next_workday(old_begin + timedelta(days=move_days))
    new_due = find_end_date(new_begin, old_workdays)
    new_effort = working_days(new_begin, new_due) * 8

    raw = run_mcporter("tapd-cn-mcp.update_story_or_task", workspace_id=pid,
                       options={"entity_type": "story", "id": s["id"],
                                "begin": new_begin.isoformat(),
                                "due": new_due.isoformat(),
                                "effort": str(new_effort)})
    if raw:
        return {"name": s["name"], "id": sid[-8:],
                "old": f"{s['begin']} ~ {s['due']}",
                "new": f"{new_begin} ~ {new_due} ({old_workdays}工作日 = {new_effort}h)"}, None
    else:
        return None, f"{sid}: 更新失败"


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    pid = sys.argv[1]
    move_days = int(sys.argv[2])
    story_ids = sys.argv[3:]

    print(f"=== 整体移期 ===\n项目ID: {pid}\n后移: {move_days} 天\n需求数: {len(story_ids)}\n")

    results = []
    errors = []

    # 并行处理各需求的移期
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(move_one_story, pid, move_days, sid): sid for sid in story_ids}
        for f in as_completed(futures):
            sid = futures[f]
            try:
                r, err = f.result()
                if r:
                    results.append(r)
                if err:
                    errors.append(err)
            except Exception as e:
                errors.append(f"{sid}: {e}")

    if results:
        print("## 已更新\n")
        for r in results:
            print(f"- **{r['name']}**  |  {r['old']} → {r['new']}")
        print()
    if errors:
        print("## 错误\n")
        for e in errors:
            print(f"- {e}")
        print()


if __name__ == "__main__":
    main()
