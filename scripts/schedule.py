"""
TAPD 排期（全 REST API）
为需求设置排期（begin / due / effort），自动计算工作日和工时

用法：
  python3 scripts/schedule.py <项目ID> <需求ID> <开始日期> <工作日数>
  python3 scripts/schedule.py <项目ID> <需求ID> <开始日期> <结束日期>

示例：
  python3 scripts/schedule.py 30139507 1130139507001006273 2026-07-21 5
  python3 scripts/schedule.py 30139507 1130139507001006273 2026-07-21 2026-07-25
"""
import sys
from datetime import date
from tapd_common import working_days, find_end_date, next_workday, update_story_by_api


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    pid = sys.argv[1]
    entity_id = sys.argv[2]
    begin_str = sys.argv[3]

    # 判断第四个参数是工作日数还是结束日期
    if len(sys.argv) >= 5:
        arg4 = sys.argv[4]
        if "-" in arg4:
            end_date = date.fromisoformat(arg4)
            workdays = working_days(date.fromisoformat(begin_str), end_date)
            due_str = arg4
        else:
            workdays = int(arg4)
            start = next_workday(date.fromisoformat(begin_str))
            end = find_end_date(start, workdays)
            due_str = end.isoformat()
            begin_str = start.isoformat()
    else:
        print("[错误] 请输入工作日数或结束日期")
        sys.exit(1)

    effort = workdays * 8
    print(f"=== 排期设置 ===\n需求ID: {entity_id}\n开始: {begin_str}\n结束: {due_str}")
    print(f"工作日: {workdays} 天 = {effort}h\n")

    result = update_story_by_api(pid, "story", entity_id,
                                  begin=begin_str, due=due_str, effort=str(effort))
    if result:
        print(f"✓ 排期已更新: {result.get('begin', begin_str)} ~ {result.get('due', due_str)}, "
              f"工时 {result.get('effort', effort)}h")
    else:
        print("✘ 更新失败（REST API 返回异常）")


if __name__ == "__main__":
    main()
