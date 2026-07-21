"""
TAPD 脚本共享模块 — mcporter 连接、配置加载、公共工具函数
所有 scripts/*.py 都从此导入，避免重复代码。
"""
import subprocess, json, sys, os, shutil
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- mcporter 自动查找 ----
_mcporter = shutil.which("mcporter") or shutil.which("mcporter.cmd")
if not _mcporter:
    print("[错误] 未找到 mcporter，请执行 npm install -g mcporter")
    sys.exit(1)

MCPORTER = [_mcporter, "--config",
            os.path.join(SKILL_DIR, "config", "mcporter.json"), "call"]

# ---- Token 提取（用于直接调 TAPD REST API） ----
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

# ---- 配置加载 ----
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
    - options: 可以是 dict（转为 options.key=value）或 str（直接作为 options=<str> 传递）
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
    - dict 且含 result(key) → 嵌套 JSON 字符串（get_stories_or_tasks 等）
    - dict 且有 data(key) → 直接数据（get_todo 等）
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
    """并行对所有项目执行 fn(pid, entity_type)，返回 { pid: { entity_type: [items] } }"""
    results = {}
    with ThreadPoolExecutor(max_workers=20) as ex:
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


# ---- 工作日工具 ----
def working_days(start, end):
    """计算 start~end 之间的工作日数（含两端）"""
    return sum(1 for i in range((end - start).days + 1)
               if (start + timedelta(i)).weekday() < 5)


def find_end_date(start, target_days):
    """从 start 往后找第 target_days 个工作日"""
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


# ---- TAPD REST API 直调（绕过 MCP Server 的 limit 等 bug） ----
_TAPD_TOKEN = _get_token()

def get_stories_by_api(pid, entity_type="story", fields=None):
    """
    通过 TAPD REST API 直接查需求/任务详情。
    MCP Server 的 get_stories_or_tasks 有 limit/page 不生效的 bug，
    此函数作为替代。
    返回 { id: detail_dict } 字典。
    """
    if not _TAPD_TOKEN:
        # fallback 到 mcporter
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
