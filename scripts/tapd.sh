#!/usr/bin/env bash
# TAPD 便捷操作入口（macOS / Linux）
# 全 REST API，无需 mcporter
# 用法：
#   bash scripts/tapd.sh todo                           # 查今日待办
#   bash scripts/tapd.sh hours <项目ID> <需求ID> <时数>   # 记工时
#   bash scripts/tapd.sh timesheet [日期]                # 查花费
#   bash scripts/tapd.sh schedule <项目ID> <需求ID> <日期> <工作日> # 排期
#   bash scripts/tapd.sh move <项目ID> <天数> <需求ID...>  # 移期

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cmd="${1:-help}"
shift || true

case "$cmd" in
  todo)
    python3 "$SCRIPT_DIR/todo_query.py"
    ;;
  timesheet)
    python3 "$SCRIPT_DIR/timesheet_query.py" "$@"
    ;;
  hours)
    python3 "$SCRIPT_DIR/add_hours.py" "$@"
    ;;
  schedule)
    python3 "$SCRIPT_DIR/schedule.py" "$@"
    ;;
  move)
    python3 "$SCRIPT_DIR/reschedule.py" "$@"
    ;;
  help|"")
    echo "用法: $0 <command> [参数...]"
    echo ""
    echo "命令:"
    echo "  todo                        查今日待办"
    echo "  timesheet [日期]            查花费（默认今天）"
    echo "  hours <项目ID> <需求ID> <时数>  记工时"
    echo "  schedule <项目ID> <需求ID> <日期> <工作日>  排期"
    echo "  move <项目ID> <天数> <需求ID...>  整体移期"
    echo ""
    echo "示例:"
    echo "  $0 todo"
    echo "  $0 hours 30139507 1130139507001006273 4"
    echo "  $0 schedule 30139507 1130139507001006273 2026-07-21 5"
    echo "  $0 move 30139507 3 1130139507001006273"
    ;;
  *)
    echo "未知命令: $cmd"
    echo "可用命令: todo / timesheet / hours / schedule / move"
    exit 1
    ;;
esac
