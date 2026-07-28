"""
TAPD 花费查询（REST API 版）
遍历所有项目，查用户的工时花费，按项目汇总

用法：
  python3 scripts/timesheet_query.py                      # 今天
  python3 scripts/timesheet_query.py 2026-07-20           # 指定日期
  python3 scripts/timesheet_query.py 2026-07-13 2026-07-20  # 日期范围
"""
import sys
from datetime import date, timedelta
from tapd_common import PROJECTS, USER_NICK, get_timesheets_by_api


def main():
    today = date.today().isoformat()
    if len(sys.argv) == 2:
        start_date = end_date = sys.argv[1]
    elif len(sys.argv) >= 3:
        start_date, end_date = sys.argv[1], sys.argv[2]
    else:
        start_date = end_date = today

    user = USER_NICK or input("请输入 TAPD 昵称：").strip()
    print(f"=== 花费查询: {user}  {start_date} ~ {end_date} ===\n")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 日期范围内逐天查询（TAPD timesheets API 只支持单日查询）
    all_dates = []
    d = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    while d <= end:
        all_dates.append(d.isoformat())
        d += timedelta(days=1)

    raw_results = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        def fetch(pid, spentdate):
            items = get_timesheets_by_api(pid, user, spentdate=spentdate)
            return (pid, spentdate, items)

        futures = {}
        for p in PROJECTS:
            for sd in all_dates:
                f = ex.submit(fetch, p["id"], sd)
                futures[f] = (p, sd)
        for f in as_completed(futures):
            p, sd = futures[f]
            try:
                pid, spentdate, items = f.result()
            except Exception:
                continue
            if items:
                raw_results.setdefault(pid, []).extend(items)

    if not raw_results:
        print("(该时间段无花费记录)\n")
        return

    grand_total = 0.0
    for pid in sorted(raw_results.keys(), key=lambda x: next((p["name"] for p in PROJECTS if p["id"] == x), x)):
        items = raw_results[pid]
        pname = next((p["name"] for p in PROJECTS if p["id"] == pid), pid)
        total = 0.0
        lines = []
        for ts in items:
            hours = float(ts.get("timespent", 0) or 0)
            total += hours
            memo = ts.get("memo", "") or ""
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
