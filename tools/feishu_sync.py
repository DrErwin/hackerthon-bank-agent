#!/usr/bin/env python3
"""飞书文档系统同步工具

用法：
    python tools/feishu_sync.py plan           # 列出会同步哪些文档（不碰飞书）
    python tools/feishu_sync.py publish        # 把团队阅读白名单同步到飞书
    python tools/feishu_sync.py check          # 校验凭证与权限
    python tools/feishu_sync.py setup          # 建文件夹、上传文档、建任务看板，输出链接
    python tools/feishu_sync.py resync         # 按本地 md 重新覆盖飞书文档内容
    python tools/feishu_sync.py tasks          # 仅重建任务看板记录

同步范围由 `tools/feishu_publish_all.py` 的 `CURATED_SOURCES` 白名单决定。
仓库保存完整事实源，飞书只展示当前团队需要阅读的内容。状态保存在 .feishu_state.json。
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://open.feishu.cn/open-apis"

# FEISHU_IDENTITY=user 时，所有请求改由 lark-cli 以「用户身份」发出，
# 这样创建的资源所有者就是用户本人，而不是应用侧身份。
USE_CLI = os.environ.get("FEISHU_IDENTITY", "tenant") == "user"
# FEISHU_PARENT=library 时，新建文档放进「我的文档」库（my_library 位置）。
# 注意：my_library 只能用于创建，不能用于移动；多维表格不支持该位置。
USE_LIBRARY = os.environ.get("FEISHU_PARENT") == "library"
STATE_FILE = ROOT / os.environ.get("FEISHU_STATE", ".feishu_state.json")

# 要同步的文档：本地路径 -> 飞书标题
DOCS = [
    ("docs/00-项目文档索引.md", "00 项目文档索引"),
    ("docs/01-项目跟踪.md", "01 项目跟踪"),
    ("官方资料/参赛规则与提交要求.md", "02 参赛规则与提交要求"),
    ("docs/architecture/business-architecture.md", "03 产品全景（非技术版）"),
    ("docs/architecture/technical-architecture.md", "04 技术架构"),
    ("官方资料/模板/source-code-readme-template.md", "05 源码 README 模板"),
]


# ---------- 基础设施 ----------

def load_env():
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _cli_api(method, path, body=None, params=None):
    """经 lark-cli 以用户身份调用接口，返回与 urllib 路径一致的 {code,msg,data}。"""
    tmp_files = []
    cmd = ["lark-cli", "api", method, path, "--as", "user", "--json"]

    def dump(obj):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(obj, f, ensure_ascii=False)
        f.close()
        tmp_files.append(f.name)
        return f.name

    if params:
        cmd += ["--params", "@" + dump(params)]
    if body is not None:
        cmd += ["--data", "@" + dump(body)]

    # Git Bash 会把 /open-apis 当路径改写，必须禁用 MSYS 路径转换
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    exe = shutil.which("lark-cli")
    if exe and exe.lower().endswith((".cmd", ".bat")):
        # Windows 上 lark-cli 是 .cmd 包装脚本，需经 shell 执行
        proc = subprocess.run(subprocess.list2cmdline(cmd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, shell=True)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, shell=False)
    raw = (proc.stdout or "").strip()
    for f in tmp_files:
        Path(f).unlink(missing_ok=True)
    if not raw:
        return {"code": -1, "msg": f"lark-cli 无输出: {proc.stderr[:300]}"}
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {"code": -1, "msg": f"lark-cli 输出非 JSON: {raw[:300]}"}
    if result.get("ok"):
        return {"code": 0, "msg": "success", "data": result.get("data")}
    err = result.get("error", {}) or {}
    return {"code": err.get("code", -1), "msg": err.get("message", raw[:300]),
            "error": err}


def api(method, path, token=None, body=None, params=None, expect_ok=True):
    if USE_CLI:
        result = _cli_api(method, path, body, params)
    else:
        url = BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json; charset=utf-8")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} on {method} {path}: {e.read().decode('utf-8', 'ignore')}")
    if expect_ok and result.get("code") != 0:
        raise RuntimeError(f"API 失败 {method} {path}: {result}")
    return result


_token_cache = {}


def get_token():
    if USE_CLI:
        return "user-identity"  # 用户身份由 lark-cli 自行附令牌
    if _token_cache.get("token") and time.time() < _token_cache.get("expire", 0):
        return _token_cache["token"]
    env = load_env()
    r = api("POST", "/auth/v3/tenant_access_token/internal", body={
        "app_id": env["FEISHU_APP_ID"], "app_secret": env["FEISHU_APP_SECRET"]})
    _token_cache["token"] = r["tenant_access_token"]
    _token_cache["expire"] = time.time() + r.get("expire", 7200) - 300
    return _token_cache["token"]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- Markdown -> 飞书 block ----------

def _runs(text):
    """把 **粗体** 和 `代码` 解析为 text_run 元素数组。"""
    parts = re.split(r"(\*\*.+?\*\*|`[^`]+`)", text)
    out = []
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            out.append({"text_run": {"content": p[2:-2], "text_element_style": {"bold": True}}})
        elif p.startswith("`") and p.endswith("`") and len(p) > 2:
            out.append({"text_run": {"content": p[1:-1], "text_element_style": {"inline_code": True}}})
        else:
            out.append({"text_run": {"content": p}})
    return out


HEADING_TYPES = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8}


def _simple(block_type, key, text, extra_style=None):
    style = extra_style or {}
    return {"block_type": block_type, key: {"elements": _runs(text), "style": style}}


def md_to_blocks(md):
    """解析 markdown，返回 (simple_blocks, tables) 两类，按序交错。"""
    items = []  # ("block", dict) 或 ("table", rows)
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        # 代码块（mermaid 走画板，其余为代码块）
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            code = "\n".join(buf)
            if lang.lower() in ("mermaid", "mmd"):
                items.append(("mermaid", code))
                continue
            items.append(("block", {"block_type": 14, "code": {
                "elements": [{"text_run": {"content": code}}],
                "style": {"language": _code_lang(lang), "wrap": True}}}))
            continue

        # 分隔线
        if re.match(r"^\s*-{3,}\s*$", line):
            items.append(("block", {"block_type": 22, "divider": {}}))
            i += 1
            continue

        # 表格
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            rows = []
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(header)
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            items.append(("table", rows))
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            items.append(("block", _simple(HEADING_TYPES[level], f"heading{level}", m.group(2))))
            i += 1
            continue

        # 引用
        if line.strip().startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            items.append(("block", _simple(15, "quote", " ".join(buf))))
            continue

        # 列表
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            items.append(("block", _simple(12, "bullet", m.group(1))))
            i += 1
            continue
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if m:
            items.append(("block", _simple(13, "ordered", m.group(1))))
            i += 1
            continue

        # 空行
        if not line.strip():
            i += 1
            continue

        # 普通段落
        items.append(("block", _simple(2, "text", line.strip())))
        i += 1
    return items


def _code_lang(lang):
    mapping = {"": 1, "plaintext": 1, "text": 1, "python": 24, "py": 24,
               "javascript": 27, "js": 27, "typescript": 28, "ts": 28,
               "json": 30, "bash": 7, "shell": 7, "sh": 7, "sql": 35}
    return mapping.get(lang.lower(), 1)


# ---------- 文档写入 ----------

def create_doc(title, folder_token=""):
    if USE_LIBRARY:
        return create_doc_in_library(title)
    body = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token
    r = api("POST", "/docx/v1/documents", get_token(), body)
    return r["data"]["document"]["document_id"]


def create_doc_in_library(title):
    """在「我的文档」库中创建文档。my_library 位置只能经 CLI 的 --parent-position 指定，
    且不支持移动，因此需要迁移时只能重建。"""
    cmd = ["lark-cli", "docs", "+create", "--title", title,
           "--parent-position", "my_library", "--as", "user", "--json"]
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    exe = shutil.which("lark-cli")
    if exe and exe.lower().endswith((".cmd", ".bat")):
        proc = subprocess.run(subprocess.list2cmdline(cmd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, shell=True)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, shell=False)
    out = (proc.stdout or "").strip()
    result = json.loads(out) if out.startswith("{") else {"ok": False, "raw": out[:300]}
    if not result.get("ok"):
        raise RuntimeError(f"在「我的文档」中创建《{title}》失败: {str(result)[:200]}")
    return result["data"]["document"]["document_id"]


def _flush_blocks(doc_id, blocks):
    """批量写入简单 block（每批 50 个）。"""
    token = get_token()
    for n in range(0, len(blocks), 50):
        api("POST", f"/docx/v1/documents/{doc_id}/blocks/{doc_id}/children", token,
            {"children": blocks[n:n + 50], "index": -1})


def _write_table(doc_id, rows):
    """用 descendant 接口写入带单元格的表格，并追加到文档末尾。"""
    token = get_token()
    n_rows = len(rows)
    n_cols = max(len(r) for r in rows)
    children_id = ["tb_main"]
    descendants = [{
        "block_id": "tb_main",
        "block_type": 31,
        "table": {"property": {"row_size": n_rows, "column_size": n_cols, "header_row": True}},
        "children": [f"cell_{r}_{c}" for r in range(n_rows) for c in range(n_cols)],
    }]
    for r in range(n_rows):
        for c in range(n_cols):
            cell_id = f"cell_{r}_{c}"
            text_id = f"txt_{r}_{c}"
            content = rows[r][c] if c < len(rows[r]) else ""
            descendants.append({
                "block_id": cell_id, "block_type": 32, "table_cell": {}, "children": [text_id]})
            descendants.append({
                "block_id": text_id, "block_type": 2,
                "text": {"elements": _runs(content), "style": {}}})
    api("POST", f"/docx/v1/documents/{doc_id}/blocks/{doc_id}/descendant", token,
        {"index": -1, "children_id": children_id, "descendants": descendants})


def clear_doc(doc_id):
    """清空文档正文内容，便于重新同步（批量删除块，POST children/batch_delete）。"""
    token = get_token()
    r = api("GET", f"/docx/v1/documents/{doc_id}/blocks", token, params={"page_size": 500})
    root = next((b for b in r["data"]["items"] if b["block_id"] == doc_id), None)
    n = len(root.get("children", [])) if root else 0
    if n:
        api("POST", f"/docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_delete", token,
            {"start_index": 0, "end_index": n})


def append_whiteboard(doc_id, mermaid_code):
    """把 Mermaid 作为飞书原生画板块追加进文档（需 lark-cli 用户身份）。

    原生 docx block API 不支持创建画板，必须走 `docs +update --command append`
    并传入 <whiteboard type="mermaid"> 形式的 DocxXML。
    """
    xml = '<whiteboard type="mermaid">\n' + mermaid_code.strip() + '\n</whiteboard>\n'
    f = tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8")
    f.write(xml)
    f.close()
    try:
        cmd = ["lark-cli", "docs", "+update", "--doc", doc_id, "--command", "append",
               "--content", "@" + f.name, "--as", "user", "--json"]
        env = dict(os.environ, MSYS_NO_PATHCONV="1")
        exe = shutil.which("lark-cli")
        if exe and exe.lower().endswith((".cmd", ".bat")):
            proc = subprocess.run(subprocess.list2cmdline(cmd), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, shell=True)
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", env=env, shell=False)
        out = (proc.stdout or "").strip()
        result = json.loads(out) if out.startswith("{") else {"ok": False, "raw": out[:300]}
        return result.get("ok", False), result
    finally:
        Path(f.name).unlink(missing_ok=True)


def push_md_doc(doc_id, md_path):
    """用 CLI 的 overwrite 以 markdown 整体推送文档（保真度最高）。

    markdown 模式原生支持 GFM 表格、任务勾选框、引用；画板不在 markdown 语法内，
    但 `<whiteboard>` XML 标签在 markdown 模式下同样会被解析，故先把 ```mermaid
    代码块替换成 whiteboard 标签。要求 --content 用 cwd 下的相对路径。
    """
    s = (ROOT / md_path).read_text(encoding="utf-8")
    s = re.sub(r"```mermaid\n(.*?)```",
               lambda m: '<whiteboard type="mermaid">\n' + m.group(1).strip() + "\n</whiteboard>\n",
               s, flags=re.S)
    tmp = ROOT / "_push.md"
    tmp.write_text(s, encoding="utf-8")
    try:
        cmd = ["lark-cli", "docs", "+update", "--doc", doc_id, "--command", "overwrite",
               "--doc-format", "markdown", "--content", "@./_push.md", "--as", "user", "--json"]
        env = dict(os.environ, MSYS_NO_PATHCONV="1")
        exe = shutil.which("lark-cli")
        if exe and exe.lower().endswith((".cmd", ".bat")):
            proc = subprocess.run(subprocess.list2cmdline(cmd), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, shell=True)
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", env=env, shell=False)
        out = (proc.stdout or "").strip()
        result = json.loads(out) if out.startswith("{") else {"ok": False, "raw": out[:300]}
        return result.get("ok", False), result
    finally:
        tmp.unlink(missing_ok=True)


def sync_md_to_doc(doc_id, md_path):
    """把本地 markdown 同步进飞书文档：优先走 CLI overwrite（含画板），失败回落 block 流水线。"""
    ok, res = push_md_doc(doc_id, md_path)
    if ok:
        boards = res.get("data", {}).get("document", {}).get("new_blocks", [])
        n_board = sum(1 for b in boards if b.get("block_type") == "whiteboard")
        print(f"    已推送（画板 {n_board} 个）")
        return
    print(f"    CLI 推送失败，回落 block 流水线: {str(res)[:150]}")
    md = (ROOT / md_path).read_text(encoding="utf-8")
    items = md_to_blocks(md)
    buffer = []
    for kind, payload in items:
        if kind == "block":
            buffer.append(payload)
        else:
            _flush_blocks(doc_id, buffer)
            buffer = []
            if kind == "table":
                _write_table(doc_id, payload)
            elif kind == "mermaid":
                ok2, res2 = append_whiteboard(doc_id, payload)
                print(f"    画板: {'已插入' if ok2 else '失败 -> ' + str(res2)[:120]}")
    _flush_blocks(doc_id, buffer)


# ---------- 多维表格 ----------

def create_bitable(name, folder_token=""):
    body = {"name": name}
    if folder_token:
        body["folder_token"] = folder_token
    r = api("POST", "/bitable/v1/apps", get_token(), body)
    return r["data"]["app"]["app_token"], r["data"]["app"]["default_table_id"]


def list_fields(app_token, table_id):
    r = api("GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", get_token(),
            params={"page_size": 100})
    return r["data"]["items"]


def add_field(app_token, table_id, name, ftype, options=None, prop=None):
    body = {"field_name": name, "type": ftype}
    if options:
        body["property"] = {"options": [{"name": o} for o in options]}
    if prop:
        body["property"] = prop
    r = api("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields", get_token(), body)
    return r["data"]["field"]["field_id"]


def rename_field(app_token, table_id, field_id, name, ftype=1):
    api("PUT", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}", get_token(),
        {"field_name": name, "type": ftype})


def delete_field(app_token, table_id, field_id):
    api("DELETE", f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{field_id}",
        get_token(), expect_ok=False)


def add_records(app_token, table_id, records):
    token = get_token()
    for n in range(0, len(records), 100):
        api("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            token, {"records": [{"fields": r} for r in records[n:n + 100]]})


def purge_blank_records(app_token, table_id, primary_field="任务名称"):
    """删除主字段为空的占位行（新建表格自带，会干扰视图统计）。"""
    token = get_token()
    r = api("GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", token,
            params={"page_size": 500})
    blanks = [rec["record_id"] for rec in r["data"].get("items", [])
              if not rec["fields"].get(primary_field)]
    if blanks:
        api("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
            token, {"records": blanks})
    return len(blanks)


def add_view(app_token, table_id, name, view_type):
    r = api("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/views", get_token(),
            {"view_name": name, "view_type": view_type}, expect_ok=False)
    return r.get("code") == 0, r


def share_public(token_, type_):
    """设为「互联网上获得链接的人可阅读」，让尚未入队的队员也能看。"""
    r = api("PATCH", f"/drive/v1/permissions/{token_}/public", get_token(),
            {"link_share_entity": "anyone_readable", "external_access_entity": "open"},
            params={"type": type_}, expect_ok=False)
    if r.get("code") != 0:
        r = api("PATCH", f"/drive/v1/permissions/{token_}/public", get_token(),
                {"link_share_entity": "tenant_readable"}, params={"type": type_}, expect_ok=False)
    return r.get("code") == 0


def set_link_share(token_, type_, entity):
    """entity: tenant_readable / tenant_editable / anyone_readable / anyone_editable / closed"""
    return api("PATCH", f"/drive/v1/permissions/{token_}/public", get_token(),
               {"link_share_entity": entity}, params={"type": type_}, expect_ok=False)


def add_member_variants(token_, type_, member_id, member_type="email", perm="full_access"):
    """飞书 v1 成员接口的 body 形状有多个版本，逐个尝试，返回 (成功?, 用到的形状, 最后错误)。

    实测（2026-09-16）：member_type 合法枚举 [email,openid,unionid,openchat,opendepartmentid,
    userid,groupid,wikispaceid,appid]；body 另可带 type=[user,chat,department,group,...]。
    用不存在的账号测试时所有形状都返回 1063001 Invalid parameter，需真实账号才能确认。
    """
    shapes = [
        ("basic", {"member_type": member_type, "member_id": member_id, "perm": perm}),
        ("with-type", {"member_type": member_type, "member_id": member_id, "perm": perm, "type": "user"}),
        ("with-perm-type", {"member_type": member_type, "member_id": member_id, "perm": perm,
                            "perm_type": "container"}),
    ]
    last = None
    for name, body in shapes:
        r = api("POST", f"/drive/v1/permissions/{token_}/members", get_token(), body,
                params={"type": type_, "need_notification": "false"}, expect_ok=False)
        if r.get("code") == 0:
            return True, name, None
        last = f"{name}: {r.get('code')} {r.get('msg')}"
    return False, None, last


def keep_app_access(token_, type_, app_id):
    """确保应用本身仍是「可管理」协作者，否则转移所有权后 ZCode 将无法再编辑。

    实测：应用是所有者时重复添加会返回 1063003 Invalid operation（已具备权限）；
    转移后若成员列表里没有应用，则用 basic 形状补加。
    """
    r = api("GET", f"/drive/v1/permissions/{token_}/members", get_token(),
            params={"type": type_}, expect_ok=False)
    members = r.get("data", {}).get("items", []) if r.get("code") == 0 else []
    if any(m.get("member_id") == app_id for m in members):
        return "已具备权限"
    r2 = api("POST", f"/drive/v1/permissions/{token_}/members", get_token(),
             {"member_type": "appid", "member_id": app_id, "perm": "full_access"},
             params={"type": type_, "need_notification": "false"}, expect_ok=False)
    return "已补加协作者" if r2.get("code") == 0 else f"补加失败 -> {r2.get('msg')}"


def transfer_owner(token_, type_, member_id, member_type="email"):
    """把文档所有者转给指定成员（应用创建的资源默认属应用，必须转移）。

    remove_old_owner=false：保留应用作为协作者，保证转移后仍可经 API 编辑。
    """
    for body in ({"member_type": member_type, "member_id": member_id},
                 {"member_type": member_type, "member_id": member_id, "type": "user"}):
        r = api("POST", f"/drive/v1/permissions/{token_}/members/transfer_owner", get_token(),
                body, params={"type": type_, "remove_old_owner": "false", "stay_put": "false"},
                expect_ok=False)
        if r.get("code") == 0:
            return r
    return r


def cmd_transfer():
    """python tools/feishu_sync.py transfer <飞书邮箱或 user_id> [--type email|userid]"""
    if len(sys.argv) < 3:
        print("用法：python tools/feishu_sync.py transfer <飞书邮箱>"); return
    member_id = sys.argv[2]
    member_type = "userid" if "--type" in sys.argv and "userid" in sys.argv else "email"
    state = load_state()
    targets = [("docx", m["doc_id"], t) for t, m in state.get("docs", {}).items()]
    if state.get("bitable"):
        targets.append(("bitable", state["bitable"]["app_token"], "项目任务看板"))

    ok_all = True
    app_id = load_env()["FEISHU_APP_ID"]
    for t, tk, label in targets:
        ok, shape, err = add_member_variants(tk, t, member_id, member_type)
        if not ok:
            print(f"{label}：加协作者失败 -> {err}"); ok_all = False; continue
        r2 = transfer_owner(tk, t, member_id, member_type)
        if r2.get("code") != 0:
            print(f"{label}：所有者转移失败 -> {r2.get('msg')}"); ok_all = False; continue
        # 转移后确认应用（ZCode）仍可编辑
        kept = keep_app_access(tk, t, app_id)
        print(f"{label}：所有权已转移（协作者形状={shape}），应用访问权：{kept}")
    if ok_all:
        print("\n完成。建议随后用 resync 或 tasks 跑一次写操作，确认应用仍有编辑权限。")
    else:
        print("\n若失败：① 确认邮箱与飞书账号一致 ② 确认应用已开通 docs:permission.member 并发布版本")
        print("   ③ 改用 userid：transfer <user_id> --type userid")
        print("   ④ 兜底：admin.feishu.cn → 云文档 → 文档管理 → 转移所有者（注意勾选保留应用协作者）")


# ---------- 命令 ----------

def cmd_check():
    print("凭证校验：", end=" ")
    get_token()
    print("OK")
    state = load_state()
    checks = [("消息与群组", "GET", "/im/v1/chats", {"page_size": 1})]
    if state.get("bitable"):
        app = state["bitable"]["app_token"]
        tid = state["bitable"]["table_id"]
        checks.append(("多维表格", "GET", f"/bitable/v1/apps/{app}/tables/{tid}/fields", {"page_size": 1}))
    if state.get("docs"):
        first = next(iter(state["docs"].values()))
        checks.append(("云文档", "GET", f"/docx/v1/documents/{first['doc_id']}/blocks", {"page_size": 1}))
    for label, method, path, params in checks:
        r = api(method, path, get_token(), params=params, expect_ok=False)
        print(f"{label}：{'OK' if r.get('code') == 0 else '失败 -> ' + str(r.get('msg'))}")


def cmd_setup():
    state = load_state()
    token = get_token()

    if not state.get("folder"):
        r = api("POST", "/drive/v1/files/create_folder", token,
                {"name": "FinTechathon 2026 项目文档", "folder_token": ""})
        state["folder"] = r["data"]["token"]
        print(f"已建文件夹：{state['folder']}")
        save_state(state)
    folder = state["folder"]

    state.setdefault("docs", {})
    for local, title in DOCS:
        if title in state["docs"]:
            continue
        doc_id = create_doc(title, folder)
        sync_md_to_doc(doc_id, local)
        state["docs"][title] = {"doc_id": doc_id, "local": local}
        share_public(doc_id, "docx")
        print(f"已同步文档：{title} -> https://feishu.cn/docx/{doc_id}")
        save_state(state)

    if not state.get("bitable"):
        app_token, table_id = create_bitable("项目任务看板", folder)
        state["bitable"] = {"app_token": app_token, "table_id": table_id}
        save_state(state)
        build_task_table(app_token, table_id)
        share_public(app_token, "bitable")
        print(f"已建任务看板 -> https://feishu.cn/base/{app_token}")

    print_links()


def build_task_table(app_token, table_id):
    fields = list_fields(app_token, table_id)
    primary = next((f for f in fields if f["is_primary"]), fields[0])
    rename_field(app_token, table_id, primary["field_id"], "任务名称", 1)
    for f in fields:
        if not f["is_primary"]:
            delete_field(app_token, table_id, f["field_id"])

    add_field(app_token, table_id, "负责人", 1)
    add_field(app_token, table_id, "板块", 3, options=["PRD", "安全合规", "系统基建", "开发", "交付物"])
    add_field(app_token, table_id, "优先级", 3, options=["P0", "P1", "P2"])
    add_field(app_token, table_id, "状态", 3, options=["未开始", "进行中", "已完成", "已阻塞"])
    add_field(app_token, table_id, "开始日期", 5, prop={"date_formatter": "yyyy/MM/dd", "auto_fill": False})
    add_field(app_token, table_id, "截止日期", 5, prop={"date_formatter": "yyyy/MM/dd", "auto_fill": False})
    add_field(app_token, table_id, "交付内容", 1)

    add_records(app_token, table_id, TASK_RECORDS)
    purge_blank_records(app_token, table_id)
    for vname, vtype in [("进度甘特图", "gantt"), ("状态看板", "kanban"), ("任务清单", "grid")]:
        ok, r = add_view(app_token, table_id, vname, vtype)
        print(f"视图 {vname}：{'已创建' if ok else r.get('msg')}")


def ts(date_str):
    """把 2026-09-18 转成飞书日期字段需要的毫秒时间戳（UTC+8 当天 00:00）。"""
    y, m, d = (int(x) for x in date_str.split("-"))
    import datetime
    dt = datetime.datetime(y, m, d, tzinfo=datetime.timezone(datetime.timedelta(hours=8)))
    return int(dt.timestamp() * 1000)


# 任务看板初始数据（2026-09-15 会议决议）
TASK_RECORDS = [
    {"任务名称": "PRD · 转账场景调研（业务流程 / 边界情况 / 本场景安全点）", "负责人": "梁爽",
     "板块": "PRD", "优先级": "P0", "状态": "进行中", "开始日期": ts("2026-09-15"),
     "截止日期": ts("2026-09-18"), "交付内容": "场景 PRD 初稿 + 交付人：梁爽"},
    {"任务名称": "PRD · 账单分析场景调研（业务流程 / 边界情况 / 本场景安全点）", "负责人": "贾淼淼（六水）",
     "板块": "PRD", "优先级": "P0", "状态": "进行中", "开始日期": ts("2026-09-15"),
     "截止日期": ts("2026-09-18"), "交付内容": "场景 PRD 初稿"},
    {"任务名称": "PRD · 跨场景联动调研（业务流程 / 边界情况 / 本场景安全点）", "负责人": "周恩宇（Ethan）",
     "板块": "PRD", "优先级": "P0", "状态": "进行中", "开始日期": ts("2026-09-15"),
     "截止日期": ts("2026-09-18"), "交付内容": "场景 PRD 初稿"},
    {"任务名称": "PRD · 安全合规专项（权限分级 / 四类攻击 / 隐私）", "负责人": "Ringo",
     "板块": "安全合规", "优先级": "P0", "状态": "进行中", "开始日期": ts("2026-09-15"),
     "截止日期": ts("2026-09-18"), "交付内容": "安全需求初稿（对齐官方安全自评提纲）"},
    {"任务名称": "PRD · 银行基建与系统框架", "负责人": "Erwin",
     "板块": "系统基建", "优先级": "P0", "状态": "进行中", "开始日期": ts("2026-09-15"),
     "截止日期": ts("2026-09-18"), "交付内容": "基建 PRD + 协作流程（分支/仓库规范）"},
    {"任务名称": "里程碑 · PRD 各模块初稿汇总截止（周五例会）", "负责人": "全员",
     "板块": "PRD", "优先级": "P0", "状态": "未开始", "开始日期": ts("2026-09-18"),
     "截止日期": ts("2026-09-18"), "交付内容": "五人分模块初稿交齐，周五晚例会"},
    {"任务名称": "PRD 整合为项目总 PRD", "负责人": "Erwin",
     "板块": "PRD", "优先级": "P0", "状态": "未开始", "开始日期": ts("2026-09-19"),
     "截止日期": ts("2026-09-21"), "交付内容": "总 PRD（含产品概述/场景章/评测验收总纲）"},
    {"任务名称": "官方 · 人工智能赛道线上答疑", "负责人": "Erwin",
     "板块": "交付物", "优先级": "P1", "状态": "未开始", "开始日期": ts("2026-10-28"),
     "截止日期": ts("2026-10-28"), "交付内容": "确认安全自评报告是否必交等口径问题"},
    {"任务名称": "官方 · 报名截止（提交全员信息）", "负责人": "Erwin",
     "板块": "交付物", "优先级": "P0", "状态": "未开始", "开始日期": ts("2026-10-25"),
     "截止日期": ts("2026-11-01"), "交付内容": "队伍信息表提交，建议提前一周完成"},
    {"任务名称": "官方 · 作品提交截止", "负责人": "全员",
     "板块": "交付物", "优先级": "P0", "状态": "未开始", "开始日期": ts("2026-10-26"),
     "截止日期": ts("2026-11-02"), "交付内容": "技术文档 + PPT + 源码 + 安全自评（+演示视频）"},
]


def cmd_resync():
    state = load_state()
    for title, meta in state.get("docs", {}).items():
        print(f"同步 {title} …")
        # push_md_doc 用 overwrite 整体替换，无需先清空
        sync_md_to_doc(meta["doc_id"], meta["local"])
    print_links()


def cmd_relocate():
    """把全部文档重建到「我的文档」库（my_library），并授予应用协作者权限。

    用法：FEISHU_IDENTITY=user FEISHU_PARENT=library FEISHU_STATE=.feishu_state.lib.json \
          python tools/feishu_sync.py relocate
    多维表格不支持 my_library，本命令只处理文档。
    """
    state = load_state()
    state.setdefault("docs", {})
    app_id = load_env()["FEISHU_APP_ID"]
    for local, title in DOCS:
        if title in state["docs"]:
            print(f"跳过（已存在）：{title}")
            continue
        doc_id = create_doc_in_library(title)
        print(f"已创建《{title}》-> {doc_id}")
        state["docs"][title] = {"doc_id": doc_id, "local": local}
        save_state(state)
        sync_md_to_doc(doc_id, local)
        r = api("POST", f"/drive/v1/permissions/{doc_id}/members", None,
                {"member_type": "appid", "member_id": app_id, "perm": "full_access"},
                params={"type": "docx", "need_notification": "false"}, expect_ok=False)
        print(f"    应用协作者：{'已添加' if r.get('code') == 0 else str(r.get('msg'))[:60]}")
        r2 = api("PATCH", f"/drive/v1/permissions/{doc_id}/public", None,
                 {"link_share_entity": "tenant_editable"}, params={"type": "docx"}, expect_ok=False)
        print(f"    共享设置：{'tenant_editable' if r2.get('code') == 0 else str(r2.get('msg'))[:60]}")
    print_links()


def cmd_tasks():
    state = load_state()
    app_token = state["bitable"]["app_token"]
    table_id = state["bitable"]["table_id"]

    # 清空旧记录后重建
    r = api("GET", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records", get_token(),
            params={"page_size": 500})
    ids = [rec["record_id"] for rec in r["data"].get("items", [])]
    if ids:
        api("POST", f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
            get_token(), {"records": ids})
    add_records(app_token, table_id, TASK_RECORDS)
    print(f"已重建 {len(TASK_RECORDS)} 条任务记录")


# ---------- 用户身份发布（当前采用的路径） ----------
#
# 为什么不走 setup/resync：应用身份（tenant）建的文档，用户身份没有编辑权，
# 实测报 4030004 No permission。发布必须「谁建谁改」，全程 --as user。
# 另一个实测结论：飞书画板不支持 Mermaid 的 block/end，含它的序列图整张解析失败，
# 因此 spec_to_mermaid.py 用 Note over 表达分段。

PUBLISH = None
"""同步范围由 `tools/feishu_publish_all.py` 的团队阅读白名单决定。

`publish` / `plan` 委托给该文件。新增技术文档不会自动发布；只有项目负责人确认
适合团队阅读后才加入 `CURATED_SOURCES`。要看会同步什么，先跑：

    python tools/feishu_sync.py plan
"""

# 知识库空间：发布后把文档挂进对应分区（node 挂载见 wiki_move 映射）。
WIKI_SPACE_ID = "7688008700736310482"
WIKI_SECTIONS = {
    "00 索引与跟踪": "Pdk6wtGsOicHZJk5aE2cmQU3n4e",
    "01 PRD 与评审": "ZuSdwInBTiOb0KkAYDqcFY0pnRd",
    "02 架构": "MQhrwQ1h4i9eO6kFraOcuhzsnLd",
    "03 规则与模板": "LCTIwkKCLiYbAOkqpJLc4XaznWh",
}
# 发布标题 -> 所属分区
WIKI_MOVE = {
    "00 项目文档索引": "00 索引与跟踪",
    "01 项目跟踪": "00 索引与跟踪",
    "PRD 01 智能转账": "01 PRD 与评审",
    "PRD 02 账单分析": "01 PRD 与评审",
    "PRD 06 跨场景联动": "01 PRD 与评审",
    "PRD 安全底座": "01 PRD 与评审",
    "PRD Mock Bank": "01 PRD 与评审",
    "PRD 预审会安排": "01 PRD 与评审",
    "安全回填表": "01 PRD 与评审",
    "03 系统架构（2026-09-19）": "02 架构",
    "04 系统架构总览图": "02 架构",
    "05 模拟转账交互图": "02 架构",
    "02 参赛规则与提交要求": "03 规则与模板",
    "06 源码 README 模板": "03 规则与模板",
}

# 图与正文分离发布；正文里插入指向图的链接，链接在第一轮发布拿到 doc_id 后回填。
FIGURE_LINKS = {
    "03 系统架构（2026-09-19）": [
        ("### 1. 系统总览", "04 系统架构总览图", "七部分组成、主链路与确认回环"),
        ("### 11. 强行中断后的任务恢复", "05 模拟转账交互图", "暂停、确认与沿原任务续办"),
    ],
}


def _run_cli(cmd):
    """执行 lark-cli 并解析 JSON 输出。"""
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    exe = shutil.which("lark-cli")
    if exe and exe.lower().endswith((".cmd", ".bat")):
        proc = subprocess.run(subprocess.list2cmdline(cmd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, shell=True)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, shell=False)
    out = (proc.stdout or "").strip()
    if not out.startswith("{"):
        return {"ok": False, "raw": out[:400], "stderr": (proc.stderr or "")[:400]}
    return json.loads(out)


def _doc_id_from(res):
    """从 lark-cli 响应里取文档 id。

    建文档返回 document.document_id；改文档（+update overwrite）只返回
    revision_id 和 url，因此必须从 url 兜底解析，否则更新会被误判为失败。
    """
    doc = (res.get("data") or {}).get("document") or {}
    did = doc.get("document_id") or doc.get("block_id")
    if did:
        return did
    url = doc.get("url") or ""
    m = re.search(r"/(?:docx|docs|wiki)/([A-Za-z0-9]+)", url)
    return m.group(1) if m else None


def _render_doc(local, title, links=None):
    """把本地 md 渲染成可推送文本；.mmd 包成画板，正文按需插入图的链接。"""
    src = (ROOT / local).read_text(encoding="utf-8")
    if local.endswith(".mmd"):
        # 必须包成 ```mermaid 代码块，否则下面的白板替换匹配不到，图会变成纯文本。
        body = f"# {title}\n\n```mermaid\n{src.strip()}\n```\n"
    else:
        body = src
    for anchor, fig_title, why in (links or []):
        fid = (links_state.get(fig_title) or {}).get("doc_id")
        if not fid or anchor not in body or fig_title in body:
            continue
        note = f"> 配图：[{fig_title}](https://feishu.cn/docx/{fid}) —— {why}\n"
        body = body.replace(anchor, anchor + "\n\n" + note, 1)
    return re.sub(r"```mermaid\n(.*?)```",
                  lambda m: '<whiteboard type="mermaid">\n' + m.group(1).strip() + "\n</whiteboard>",
                  body, flags=re.S)


links_state = {}


def cmd_publish():
    """把团队阅读白名单同步到飞书。用法：python tools/feishu_sync.py publish

    同步范围、标题与分区规则见 `tools/feishu_publish_all.py`。想看会同步什么，
    先跑 `plan`。
    """
    import feishu_publish_all as all_sync
    return all_sync.cmd_sync()


def cmd_plan():
    """列出会同步哪些文档、标题与目标分区，不碰飞书。"""
    import feishu_publish_all as all_sync
    return all_sync.cmd_plan()


def cmd_mount():
    """把已发布的文档挂进知识库对应分区（幂等）。"""
    import feishu_publish_all as all_sync
    return all_sync.cmd_mount()


def cmd_delete_old():
    """删除已废弃的飞书文档（本地源已不存在的旧页）。"""
    for token in OLD_DOCS:
        res = _run_cli(["lark-cli", "drive", "+delete", "--file-token", token,
                        "--type", "docx", "--as", "user", "--yes", "--json"])
        print(f"  {token}: {'已删除' if res.get('ok') else str(res.get('error'))[:120]}")


def cmd_relink():
    """只重推一份带配图链接的正文（改过图或链接后单独补跑用）。

    用法：python tools/feishu_sync.py relink "03 系统架构（2026-09-19）"
    必须先 publish 过，否则状态里没有 doc_id。
    """
    global links_state
    state = load_state()
    links_state = state.get("docs", {})
    title = sys.argv[2] if len(sys.argv) > 2 else "03 系统架构（2026-09-19）"
    meta = links_state.get(title)
    if not meta:
        print(f"状态里没有《{title}》，先跑 publish")
        return 1
    local = meta["local"]
    text = _render_doc(local, title, FIGURE_LINKS.get(title))
    push_dir = ROOT / "_feishu_push"
    push_dir.mkdir(exist_ok=True)
    tmp = push_dir / (re.sub(r"[^\w.-]", "_", title) + ".md")
    tmp.write_text(text, encoding="utf-8")
    rel = str(tmp.relative_to(ROOT)).replace("\\", "/")
    res = _run_cli(["lark-cli", "docs", "+update", "--doc", meta["doc_id"],
                    "--command", "overwrite", "--doc-format", "markdown",
                    "--content", "@./" + rel, "--as", "user", "--json"])
    n = text.count("配图")
    print(f"{'更新' if res.get('ok') else '失败'} {title}（配图链接 {n} 处）")
    if not res.get("ok"):
        print(f"  {str(res.get('error') or res)[:200]}")
    return 0


OLD_DOCS = [
    # 本地源已删除的废弃页：03 产品全景（源 business-architecture.md）、
    # 04 技术架构（源 technical-architecture.md）。
    "IeAodL4P8ocR3IxgMTScxjHXnTe",
    "GOuldWR6Poa3ZgxMF2JcTDNen5c",
]


def print_links():
    state = load_state()
    print("\n===== 访问链接 =====")
    print(f"文档文件夹：https://feishu.cn/drive/folder/{state.get('folder', '')}")
    for title, meta in state.get("docs", {}).items():
        print(f"{title}：https://feishu.cn/docx/{meta['doc_id']}")
    if state.get("bitable"):
        print(f"项目任务看板：https://feishu.cn/base/{state['bitable']['app_token']}")


def cmd_move():
    """python tools/feishu_sync.py move <目标文件夹token>

    把已建的全部资源移入指定文件夹。目标文件夹需先由用户在飞书云空间创建，
    并把「流程管理」应用加为可管理协作者，否则应用没有写入权限。

    注意：移动不改变所有者——应用创建的文档所有者是应用侧身份，无法经 API 转移
    （transfer_owner 要求调用方为所有者，实测返回 1063002 Permission denied）。
    """
    if len(sys.argv) < 3:
        print("用法：python tools/feishu_sync.py move <目标文件夹token>")
        print("文件夹 token 取自文件夹链接：https://xxx.feishu.cn/drive/folder/<token>")
        return
    folder = sys.argv[2]
    state = load_state()
    token = get_token()
    targets = [("docx", m["doc_id"], t) for t, m in state.get("docs", {}).items()]
    if state.get("bitable"):
        targets.append(("bitable", state["bitable"]["app_token"], "项目任务看板"))

    for t, tk, label in targets:
        r = api("POST", f"/drive/v1/files/{tk}/move", token,
                {"type": t, "folder_token": folder}, expect_ok=False)
        print(f"{label}：{'已移动' if r.get('code') == 0 else '失败 -> ' + str(r.get('msg'))}")


def cmd_owner():
    """查看全部资源的真实所有者 id。"""
    state = load_state()
    docs = [{"doc_token": m["doc_id"], "doc_type": "docx"} for m in state.get("docs", {}).values()]
    if state.get("bitable"):
        docs.append({"doc_token": state["bitable"]["app_token"], "doc_type": "bitable"})
    r = api("POST", "/drive/v1/metas/batch_query", get_token(), {"request_docs": docs})
    for m in r["data"]["metas"]:
        print(f"{m['title'][:24]:26} owner={m.get('owner_id')}")
    print(f"\n应用自身 app_id: {load_env()['FEISHU_APP_ID']}")
    print("说明：owner 为 ou_ 开头的应用侧身份，应用不是所有者，故无法经 API 转移所有权。")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"check": cmd_check, "setup": cmd_setup, "resync": cmd_resync,
     "tasks": cmd_tasks, "transfer": cmd_transfer, "publish": cmd_publish,
     "plan": cmd_plan, "mount": cmd_mount,
     "delete_old": cmd_delete_old, "relink": cmd_relink,
     "move": cmd_move, "owner": cmd_owner, "relocate": cmd_relocate}[cmd]()
