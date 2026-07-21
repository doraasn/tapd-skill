"""
TAPD 花费查询
遍历所有项目，查指定日期范围内某用户的工时，按项目汇总展示。

用法:
  python scripts/timesheet_query.py                     # 今天
  python scripts/timesheet_query.py 2026-07-20          # 指定日期
  python scripts/timesheet_query.py 2026-07-13 2026-07-20  # 日期范围
"""
import sys
from datetime import date
from tapd_common import run_mcporter, parse_result, PROJECTS, USER_NICK


def get_timesheets(pid, owner, start_date, end_date):
    """查某项目某用户的工时"""
    raw = run_mcporter("tapd-cn-mcp.get_timesheets", workspace_id=pid,
                       options=f'{{"owner":"{owner}","spentdate":"{start_date}","limit":"200"}}')
    items = parse_result(raw)
    # 过滤日期范围
    if isinstance(items, list):
        items = [i for i in items if start_date <= (i.get("Timesheet", {}) or i).get("spentdate", "") <= end_date]
    return items


def main():
    today = date.today().isoformat()
    if len(sys.argv) == 2:
        start_date = end_date = sys.argv[1]
    elif len(sys.argv) >= 3:
        start_date, end_date = sys.argv[1], sys.argv[2]
    else:
        start_date = end_date = today

    user = USER_NICK or input("请输入 TAPD 昵称: ").strip()
    print(f"=== 查花费: {user}  {start_date} ~ {end_date} ===\n")

    from concurrent.futures import ThreadPoolExecutor, as_completed
    all_data = {}
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(get_timesheets, p["id"], user, start_date, end_date): p for p in PROJECTS}
        for f in as_completed(futures):
            p = futures[f]
            try:
                items = f.result()
            except Exception:
                continue
            if items:
                all_data[p["id"]] = (p["name"], items)

    if not all_data:
        print("(该时段无花费记录)\n")
        return

    grand_total = 0.0
    for wid, (pname, items) in sorted(all_data.items(), key=lambda x: x[1][0]):
        total = 0.0
        lines = []
        for item in items:
            ts = item.get("Timesheet", item)
            hours = float(ts.get("timespent", 0) or 0)
            total += hours
            memo = ts.get("memo", "") or ""
            # 尽量取需求名称（没有 ID 则显示 ID）
            entity_id = ts.get("entity_id", "")
            lines.append((hours, memo[:40] if memo else f"需求ID: {entity_id}"))
        grand_total += total
        print(f"**{pname}（{total:.2f}h）**\n")
        for i, (h, desc) in enumerate(lines, 1):
            punct = "。" if i == len(lines) else "；"
            print(f"{i}. {desc}：{h:.2f}h{punct}")
        print()

    print(f"**合计：{grand_total:.2f}h**\n")


if __name__ == "__main__":
    main()
