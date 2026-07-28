"""TAPD 通用模块 — REST API 为主，mcporter 仅用于 story/task 写入操作
所有 scripts/*.py 都从这里导入配置和公共函数。
"""
import json, sys, os, shutil, subprocess, urllib.parse
from datetime import date, timedelta
import requests

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ----- Token 获取 -----
def _get_token():
    """从 mcporter.json 提取 TAPD Access Token"""
    mcp_path = os.path.join(SKILL_DIR, "config", "mcporter.json")
    try:
        with open(mcp_path, encoding="utf-8") as f:
            cfg = json.load(f)
        args = cfg.get("mcpServers", {}).get("tapd-cn-mcp", {}).get("args", [])
        for i, a in enumerate(args):
            if a == "--access-token" and i + 1 < len(args):
                return args[i + 1]
    except Exception:
        pass
    return None

_TAPD_TOKEN = _get_token()
_TAPD_BASE = "https://api.tapd.cn"

# ----- REST API 通用请求 -----
def _api_get(endpoint, params=None):
    """GET 请求 TAPD REST API，返回 data 列表"""
    if not _TAPD_TOKEN:
        return None
    try:
        r = requests.get(f"{_TAPD_BASE}/{endpoint}", params=params,
                         headers={"Authorization": f"Bearer {_TAPD_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception:
        pass
    return None

def _api_post(endpoint, data):
    """POST 请求 TAPD REST API，返回 data 字典"""
    if not _TAPD_TOKEN:
        return None
    try:
        r = requests.post(f"{_TAPD_BASE}/{endpoint}",
                          data=data,
                          headers={"Authorization": f"Bearer {_TAPD_TOKEN}"}, timeout=15)
        if r.status_code == 200:
            return r.json().get("data")
    except Exception:
        pass
    return None

# ----- 配置加载 -----
config_path = os.path.join(SKILL_DIR, "config.json")
try:
    with open(config_path, encoding="utf-8") as f:
        CONFIG = json.load(f)
    PROJECTS = [p for p in CONFIG.get("projects", []) if p.get("type") == "project"]
    USER_NICK = CONFIG.get("user", {}).get("nick", "")
except Exception:
    print(f"[错误] 无法加载 {config_path}")
    sys.exit(1)


# ===== Timesheet API =====

def get_timesheets_by_api(pid, owner, spentdate=None, entity_id=None):
    """查工时，返回 Timesheet 列表"""
    params = {"workspace_id": pid, "owner": owner, "limit": 200}
    if spentdate:
        params["spentdate"] = spentdate
    if entity_id:
        params["entity_id"] = entity_id
    params["fields"] = "id,entity_id,entity_type,timespent,spentdate,memo,owner,workspace_id"
    data = _api_get("timesheets", params)
    if data is None:
        return []
    return [item.get("Timesheet", item) for item in data]


def add_timesheet_by_api(pid, entity_type, entity_id, timespent, owner, spentdate, memo=""):
    """添加工时记录"""
    data = _api_post("timesheets", {
        "workspace_id": pid,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "timespent": str(timespent),
        "owner": owner,
        "spentdate": spentdate,
        "memo": memo,
    })
    if data:
        return data.get("Timesheet", {})
    return None


def update_timesheet_by_api(ts_id, timespent, memo=""):
    """更新工时记录"""
    data = _api_post("timesheets", {
        "id": ts_id,
        "timespent": str(timespent),
        "memo": memo,
    })
    if data:
        return data.get("Timesheet", {})
    return None


# ===== Story/Task API (REST 只读) =====

def get_stories_by_api(pid, entity_type="story", fields=None):
    """
    直调 TAPD REST API 查询 story/task 列表。
    返回 { id: detail_dict } 格式。
    """
    if entity_type == "story":
        endpoint = "stories"
        type_key = "Story"
    else:
        endpoint = "tasks"
        type_key = "Task"
    params = {"workspace_id": pid, "limit": 200}
    if fields:
        params["fields"] = fields
    data = _api_get(endpoint, params)
    if not data:
        return {}
    result = {}
    for item in data:
        s = item.get(type_key, {})
        result[s.get("id", "")] = s
    return result


# ===== mcporter — 仅用于 story/task 写入操作（REST API 无对应权限） =====

def _get_mcporter():
    """懒查找 mcporter 路径"""
    mcporter = shutil.which("mcporter") or shutil.which("mcporter.cmd")
    if not mcporter:
        print("[错误] 找不到 mcporter，story/task 写入操作将不可用")
        print("请执行 npm install -g mcporter 安装")
        return None
    return mcporter

_MCPORTER = None  # lazy init

def run_mcporter(selector, options=None, **params):
    """
    调用 mcporter MCP 工具（仅用于 story/task 写入）。
    params: 顶级参数如 workspace_id=30139507
    options: dict → 展开为 options.key=value
    """
    global _MCPORTER
    if _MCPORTER is None:
        mp = _get_mcporter()
        if not mp:
            return None
        _MCPORTER = [mp, "--config",
                     os.path.join(SKILL_DIR, "config", "mcporter.json"), "call"]
    args = [f"{k}={v}" for k, v in params.items()]
    if isinstance(options, dict):
        args += [f"options.{k}={v}" for k, v in options.items()]
    elif isinstance(options, str):
        args += [f"options={options}"]
    cmd = _MCPORTER + [selector] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


def parse_result(raw):
    """
    解析 mcporter 返回结果：
    - dict 带 result(key) → 内部 JSON 字符串的 data
    - dict 带 data(key) → 直接返回数组
    """
    if raw is None or not isinstance(raw, dict):
        return []
    result_str = raw.get("result")
    if isinstance(result_str, str):
        try:
            return json.loads(result_str).get("data", [])
        except json.JSONDecodeError:
            return []
    return raw.get("data", [])


# ===== 并行遍历工具 =====

def for_all_projects(entity_types, fn):
    """遍历所有项目并行执行 fn(pid, entity_type)，返回 { pid: { entity_type: [items] } }"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {}
        for p in PROJECTS:
            for et in entity_types:
                f = ex.submit(fn, p["id"], et)
                futures[f] = (p, et)
        for f in as_completed(futures):
            p, et = futures[f]
            try:
                data = f.result()
            except Exception:
                continue
            if data:
                results.setdefault(p["id"], {})[et] = (p["name"], data)
    return results


# ===== 工作日工具 =====

def working_days(start, end):
    """计算 start~end 之间的工作日数（不含周末）"""
    return sum(1 for i in range((end - start).days + 1)
               if (start + timedelta(i)).weekday() < 5)

def find_end_date(start, target_days):
    """从 start 开始数 target_days 个工作日"""
    d, count = start, 0
    while True:
        if d.weekday() < 5:
            count += 1
        if count == target_days:
            return d
        d += timedelta(days=1)

def next_workday(d):
    """如果 d 落在周末，顺延到周一"""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d
