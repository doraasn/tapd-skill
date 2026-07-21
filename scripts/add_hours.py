"""
TAPD 记工时
自动检测：同一天同一需求是否已有记录（有则更新）、父需求检测（自动提示）。

用法:
  python scripts/add_hours.py <项目ID> <需求ID> <小时数> [日期] [备注]

示例:
  python scripts/add_hours.py 30139507 1130139507001006273 4
  python scripts/add_hours.py 30139507 1130139507001006273 8 2026-07-20 "联调测试"
"""
import sys, json
from datetime import date
from tapd_common import run_mcporter, parse_result, PROJECTS, USER_NICK


def get_project_name(pid):
    for p in PROJECTS:
        if p["id"] == pid:
            return p["name"]
    return pid


def check_existing(pid, entity_id, entity_type, spentdate):
    """检查是否已有花费记录"""
    raw = run_mcporter("tapd-cn-mcp.get_timesheets", workspace_id=pid,
                       options=json.dumps({"owner": USER_NICK, "spentdate": spentdate, "entity_id": entity_id,
                                           "entity_type": entity_type, "limit": "10"}))
    items = parse_result(raw)
    if isinstance(items, list):
        for item in items:
            ts = item.get("Timesheet", item)
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
        print("[错误] tapd.user.json 中未设置 user.nick")
        sys.exit(1)
    if timespent is None:
        print("[错误] 请输入工时小时数")
        sys.exit(1)

    pname = get_project_name(pid)
    print(f"=== 记工时 ===\n项目: {pname} ({pid})\n需求ID: {entity_id}\n工时: {timespent}h\n日期: {spentdate}\n")

    # 1. 先查该需求信息，判断是否为父需求
    raw = run_mcporter("tapd-cn-mcp.get_stories_or_tasks", workspace_id=pid,
                       options={"entity_type": "story", "id": entity_id,
                                "fields": "id,name,parent_id,children_id"})
    items = parse_result(raw)
    if items:
        s = items[0].get("Story", {})
        children = s.get("children_id", "")
        if children and children.strip("|"):
            print(f"[警告] 该需求存在子需求，父需求不可直接记工时！")
            print(f"  子需求 ID: {children.strip('|')}")
            confirm = input("是否继续强制记录？(y/N): ").strip().lower()
            if confirm != "y":
                print("已取消")
                sys.exit(0)

    # 2. 检查是否有已有记录
    existing_id = check_existing(pid, entity_id, "story", spentdate)
    if existing_id:
        print(f"[提示] 该日已有花费记录 (ID: {existing_id})，将更新为 {timespent}h")
        raw = run_mcporter("tapd-cn-mcp.update_timesheets", workspace_id=pid,
                           options=json.dumps({"id": existing_id, "timespent": timespent, "memo": memo}))
        if raw:
            print("✅ 工时已更新")
        else:
            print("❌ 更新失败")
    else:
        raw = run_mcporter("tapd-cn-mcp.add_timesheets", workspace_id=pid,
                           options=json.dumps({"entity_type": "story", "entity_id": entity_id,
                                               "timespent": timespent, "owner": USER_NICK,
                                               "spentdate": spentdate, "memo": memo}))
        if raw:
            print("✅ 工时已记录")
        else:
            print("❌ 记录失败（可能是父需求无法记工时）")


if __name__ == "__main__":
    main()
