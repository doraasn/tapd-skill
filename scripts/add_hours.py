"""
TAPD 记工时（REST API 版）
注意：同一天同一需求是否已有记录（有则 update），父需求不可记工时

用法：
  python3 scripts/add_hours.py <项目ID> <需求ID> <时数> [日期] [备注]

示例：
  python3 scripts/add_hours.py 30139507 1130139507001006273 4
  python3 scripts/add_hours.py 30139507 1130139507001006273 8 2026-07-20 "对接测试"
"""
import sys
from datetime import date
from tapd_common import (
    PROJECTS, USER_NICK,
    get_timesheets_by_api, add_timesheet_by_api, update_timesheet_by_api,
    get_stories_by_api
)


def get_project_name(pid):
    for p in PROJECTS:
        if p["id"] == pid:
            return p["name"]
    return pid


def check_existing(pid, entity_id, spentdate):
    """查询是否已有工时记录，有则返回 timesheet id"""
    items = get_timesheets_by_api(pid, USER_NICK, spentdate=spentdate, entity_id=entity_id)
    for ts in items:
        if ts.get("entity_id") == entity_id and ts.get("spentdate") == spentdate:
            return ts.get("id")
    return None


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    pid = sys.argv[1]
    entity_id = sys.argv[2]
    timespent = float(sys.argv[3]) if len(sys.argv) > 3 else None
    spentdate = sys.argv[4] if len(sys.argv) > 4 else date.today().isoformat()
    memo = sys.argv[5] if len(sys.argv) > 5 else ""

    if not USER_NICK:
        print("[错误] config.json 中未配置 user.nick")
        sys.exit(1)
    if timespent is None:
        print("[错误] 请输入工时小时数")
        sys.exit(1)

    pname = get_project_name(pid)
    print(f"=== 记工时 ===\n项目: {pname} ({pid})\n需求ID: {entity_id}\n工时: {timespent}h\n日期: {spentdate}\n")

    # 1. 检测父需求
    stories = get_stories_by_api(pid, "story", fields="id,name,parent_id,children_id")
    s = stories.get(entity_id)
    if s:
        children = s.get("children_id", "")
        if children and children.strip("|"):
            print(f"[警告] 该需求下有子需求，父需求不可记工时！")
            print(f"  子需求 ID: {children.strip('|')}")
            confirm = input("是否仍然继续？(y/N): ").strip().lower()
            if confirm != "y":
                print("已取消")
                sys.exit(0)

    # 2. 检测是否已有记录
    existing_id = check_existing(pid, entity_id, spentdate)
    if existing_id:
        print(f"[更新] 已有工时记录 (ID: {existing_id})，更新为 {timespent}h")
        result = update_timesheet_by_api(existing_id, timespent, memo)
        if result:
            print("✓ 工时已更新")
        else:
            print("✘ 更新失败")
    else:
        result = add_timesheet_by_api(pid, "story", entity_id, timespent, USER_NICK, spentdate, memo)
        if result:
            print("✓ 工时已记录")
        else:
            print("✘ 记录失败（可能原因是父需求不可记工时）")


if __name__ == "__main__":
    main()
