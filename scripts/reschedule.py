"""
TAPD 整体移期（全 REST API）
批量后移多个需求的排期 N 天，周末自动顺延

用法：
  python3 scripts/reschedule.py <项目ID> <天数> <需求ID1> [需求ID2 ...]

示例：
  python3 scripts/reschedule.py 30139507 3 1130139507001006273 1130139507001006126
"""
import sys
from datetime import date, timedelta
from tapd_common import get_stories_by_api, update_story_by_api, working_days, find_end_date, next_workday


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    pid = sys.argv[1]
    move_days = int(sys.argv[2])
    story_ids = sys.argv[3:]

    print(f"=== 整体移期 ===\n项目ID: {pid}\n后移: {move_days} 天\n需求数: {len(story_ids)}\n")

    # 批量查需求详情（REST API）
    stories = get_stories_by_api(pid, "story", fields="id,name,begin,due,effort")

    results = []
    errors = []
    for sid in story_ids:
        s = stories.get(sid)
        if not s:
            errors.append(f"{sid}: 找不到需求")
            continue
        if not s.get("begin"):
            errors.append(f"{sid} ({s['name']}): 无排期，跳过")
            continue

        old_begin = date.fromisoformat(s["begin"])
        old_due = date.fromisoformat(s["due"])
        old_workdays = working_days(old_begin, old_due) if old_begin != old_due else 1

        # 新开始 = 旧开始 + 移动天数，周末顺延
        new_begin = next_workday(old_begin + timedelta(days=move_days))
        new_due = find_end_date(new_begin, old_workdays)
        new_effort = working_days(new_begin, new_due) * 8

        ret = update_story_by_api(pid, "story", s["id"],
                                   begin=new_begin.isoformat(),
                                   due=new_due.isoformat(),
                                   effort=str(new_effort))
        if ret:
            results.append({
                "name": s["name"], "id": sid[-8:],
                "old": f"{s['begin']} ~ {s['due']}",
                "new": f"{new_begin} ~ {new_due} ({old_workdays}工作日 = {new_effort}h)"
            })
        else:
            errors.append(f"{sid}: 更新失败")

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
