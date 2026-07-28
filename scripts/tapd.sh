#!/usr/bin/env bash
# TAPD 便捷操作入口（macOS / Linux）
# 用法：
#   bash scripts/tapd.sh todo                           # 查今日待办
#   bash scripts/tapd.sh hours <项目ID> <需求ID> <时数>   # 记工时
#   bash scripts/tapd.sh timesheet [日期]                # 查花费
#   bash scripts/tapd.sh schedule <项目ID> <需求ID> <日期> <工作日> # 排期
#   bash scripts/tapd.sh move <项目ID> <天数> <需求ID...>  # 移期
#   bash scripts/tapd.sh call <工具名> [参数]            # 直接调用 MCP 工具

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

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
  call|list)
    CONFIG_PATH="$SKILL_DIR/config/mcporter.json"
    if ! command -v mcporter &>/dev/null; then
      echo "[错误] 找不到 mcporter，请执行 npm install -g mcporter"
      exit 1
    fi
    mcporter --config "$CONFIG_PATH" "$cmd" "$@"
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
    echo "  call <工具名> [参数]           调用 MCP 工具（需安装 mcporter）"
    echo "  list                        列出可用 MCP 工具（需安装 mcporter）"
    echo ""
    echo "示例:"
    echo "  $0 todo"
    echo "  $0 hours 30139507 1130139507001006273 4"
    echo "  $0 schedule 30139507 1130139507001006273 2026-07-21 5"
    echo "  $0 move 30139507 3 1130139507001006273"
    echo "  $0 call tapd-cn-mcp.get_todo workspace_id=30139507 entity_type=story"
    ;;
  *)
    # 未知命令尝试走 mcporter（兼容旧用法）
    CONFIG_PATH="$SKILL_DIR/config/mcporter.json"
    if command -v mcporter &>/dev/null; then
      mcporter --config "$CONFIG_PATH" call "tapd-cn-mcp.$cmd" "$@"
    else
      echo "未知命令: $cmd"
      exit 1
    fi
    ;;
esac
