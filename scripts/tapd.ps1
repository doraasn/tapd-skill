# TAPD 辅助脚本 - 便捷调用 mcporter
# 用法:
#   .\scripts\tapd.ps1 todo                        查今日待办
#   .\scripts\tapd.ps1 hours <项目ID> <需求ID> <时> 记工时
#   .\scripts\tapd.ps1 timesheet [日期]             查花费
#   .\scripts\tapd.ps1 schedule <项目ID> <需求ID> <开始> <工作日> 排期
#   .\scripts\tapd.ps1 move <项目ID> <天数> <需求ID...> 整体移期
#   .\scripts\tapd.ps1 call <工具> <参数>            调用 MCP 工具

param(
    [Parameter(Position=0)]
    [string]$Command,
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Remaining
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$configPath = Join-Path $skillDir "config\mcporter.json"

switch ($Command) {
  "todo"       { python (Join-Path $scriptDir "todo_query.py") }
  "timesheet"  { python (Join-Path $scriptDir "timesheet_query.py") @Remaining }
  "hours"      { python (Join-Path $scriptDir "add_hours.py") @Remaining }
  "schedule"   { python (Join-Path $scriptDir "schedule.py") @Remaining }
  "move"       { python (Join-Path $scriptDir "reschedule.py") @Remaining }
  "help" {
@"
用法: .\scripts\tapd.ps1 <命令> [参数]

命令:
  todo                         查今日待办
  timesheet [日期]             查花费（默认今天）
  hours <项目ID> <需求ID> <时> 记工时
  schedule <项目ID> <需求ID> <开始> <工作日> 排期
  move <项目ID> <天数> <需求ID...>  整体移期
  call <工具> <参数>            调用 MCP 工具
  list                         列出可用 MCP 工具
"@
  }
  "call"  { mcporter --config $configPath call @Remaining }
  "list"  { mcporter --config $configPath list @Remaining }
  default {
    if ($Command) {
      mcporter --config $configPath call "tapd-cn-mcp.$Command" @Remaining
    } else {
      & $MyInvocation.MyCommand.Path help
    }
  }
}
