"""TAPD 通用模块 — mcporter 调用、配置加载、工作日工具
所有 scripts/*.py 都从这里导入配置和公共函数。
"""
import subprocess, json, sys, os, shutil
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ----- mcporter 查找 -----
_mcporter = shutil.which("mcporter") or shutil.which("mcporter.cmd")
if not _mcporter:
    print("[错误] 找不到 mcporter，请先执行 npm install -g mcporter")
    sys.exit(1)

MCPORTER = [_mcporter, "--config",
            os.path.join(SKILL_DIR, "config", "mcporter.json"), "call"]

# ----- Token 获取（用于直接调用 TAPD REST API） -----
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


def run_mcporter(selector, options=None, **params):
    """调用 mcporter MCP 工具，返回解析后的 dict
    - params: 顶级参数，如 workspace_id=30139507
    - options: 可以是 dict（展开为 options.key=value）或 str（直接传递 options=<str>）
    """
    args = [f"{k}={v}" for k, v in params.items()]
    if isinstance(options, dict):
        args += [f"options.{k}={v}" for k, v in options.items()]
    elif isinstance(options, str):
        args += [f"options={options}"]
    cmd = MCPORTER + [selector] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def parse_result(raw):
    """
    解析返回结果：
    - dict 带 result(key) → 内部 JSON 字符串的 data（get_stories_or_tasks 等）
    - dict 带 data(key) → 直接返回数组（get_todo 等）
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


def for_all_projects(entity_types, fn):
    """遍历所有项目并行执行 fn(pid, entity_type)，返回 { pid: { entity_type: [items] } }"""
    results = {}
    # N1 为双核设备，限制并发以避免大量 mcporter 子进程争抢 CPU 和内存。
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


# ----- 工作日工具 -----
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


# ----- TAPD REST API 直连（绕过 MCP Server 的 limit bug） -----
_TAPD_TOKEN = _get_token()

def get_stories_by_api(pid, entity_type="story", fields=None):
    """
    直接调用 TAPD REST API 查询功能/任务列表。
    MCP Server 的 get_stories_or_tasks 的 limit/page 都不生效的 bug，
    这里是替代方案。
    返回 { id: detail_dict } 格式。
    """
    if not _TAPD_TOKEN:
        # fallback 走 mcporter
        raw = run_mcporter("tapd-cn-mcp.get_stories_or_tasks",
                           options={"entity_type": entity_type,
                                    "fields": fields or "id,name,begin,due,owner,effort,priority_label,developer"})
        items = parse_result(raw)
        result = {}
        for item in items:
            key = entity_type.capitalize()
            s = item.get(key, {})
            result[s.get("id", "")] = s
        return result

    import requests
    ep = "stories" if entity_type == "story" else "tasks"
    params = {"workspace_id": pid, "limit": 200}
    if fields:
        params["fields"] = fields
    try:
        r = requests.get(f"https://api.tapd.cn/{ep}",
                         params=params,
                         headers={"Authorization": f"Bearer {_TAPD_TOKEN}"},
                         timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", [])
            result = {}
            for item in data:
                key = entity_type.capitalize()
                s = item.get(key, {})
                result[s.get("id", "")] = s
            return result
    except Exception:
        pass
    return {}
