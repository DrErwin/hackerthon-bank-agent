#!/usr/bin/env python3
"""在飞书文档内嵌一个多维表格，填入项目任务 + 甘特视图。

用法：FEISHU_IDENTITY=user python tools/embed_tracker.py
依赖 feishu_sync.py 的 CLI 传输层。
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feishu_sync as f  # noqa: E402

DOC_ID = "CQ8AdPiEbodvrHxjaEjczPN9nHg"  # 01 项目跟踪

# 字段（primary 字段「Multiline」将被改名，其余默认字段删除后新增这些）
FIELDS = [
    {"name": "负责人", "type": "text"},
    {"name": "阶段", "type": "select", "multiple": False, "options": [
        {"name": "PRD"}, {"name": "契约+评测"}, {"name": "转账端到端"},
        {"name": "场景+安全"}, {"name": "验收"}, {"name": "缓冲期"}]},
    {"name": "状态", "type": "select", "multiple": False, "options": [
        {"name": "未开始"}, {"name": "进行中"}, {"name": "已完成"}]},
    {"name": "开始日期", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
    {"name": "截止日期", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
]

RECORDS = [
    # 阶段一 PRD
    ("五份 PRD 初稿交齐", "待定", "PRD", "进行中", "2026-09-16", "2026-09-18"),
    ("整合总 PRD + 评审", "Erwin", "PRD", "未开始", "2026-09-19", "2026-09-20"),
    # 阶段二 契约+评测
    ("契约（packages/contracts）", "Erwin", "契约+评测", "未开始", "2026-09-21", "2026-09-25"),
    ("架构细化", "Erwin", "契约+评测", "未开始", "2026-09-21", "2026-09-25"),
    ("评测集框架", "待定", "契约+评测", "未开始", "2026-09-21", "2026-09-25"),
    ("UX PRD", "待定", "契约+评测", "未开始", "2026-09-21", "2026-09-25"),
    ("任务评测集用例", "待定", "契约+评测", "未开始", "2026-09-23", "2026-09-25"),
    ("契约冻结（里程碑）", "Erwin", "契约+评测", "未开始", "2026-09-25", "2026-09-25"),
    # 阶段三 转账端到端
    ("基座子模块并行", "Erwin", "转账端到端", "未开始", "2026-09-26", "2026-09-28"),
    ("端到端收口", "Erwin", "转账端到端", "未开始", "2026-09-29", "2026-09-30"),
    ("转账评测集跑通", "待定", "转账端到端", "未开始", "2026-09-30", "2026-09-30"),
    # 阶段四 场景+安全
    ("账单分析", "待定", "场景+安全", "未开始", "2026-10-01", "2026-10-07"),
    ("跨场景联动", "待定", "场景+安全", "未开始", "2026-10-01", "2026-10-07"),
    ("安全层完整 + 安全评测集", "待定", "场景+安全", "未开始", "2026-10-01", "2026-10-07"),
    # 阶段五 验收
    ("跑评测集 + 打磨", "待定", "验收", "未开始", "2026-10-08", "2026-10-12"),
    # 缓冲期
    ("扩展场景", "待定", "缓冲期", "未开始", "2026-10-13", "2026-10-25"),
    ("交付物", "待定", "缓冲期", "未开始", "2026-10-20", "2026-11-01"),
    ("官方答疑", "Erwin", "缓冲期", "未开始", "2026-10-28", "2026-10-28"),
    ("报名截止", "Erwin", "缓冲期", "未开始", "2026-11-01", "2026-11-01"),
    ("提交截止", "Erwin", "缓冲期", "未开始", "2026-11-02", "2026-11-02"),
]


def cli(args):
    """以用户身份调 lark-cli，返回解析后的 JSON（Windows .cmd 需 shell）。"""
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    exe = shutil.which("lark-cli")
    if exe and exe.lower().endswith((".cmd", ".bat")):
        proc = subprocess.run(subprocess.list2cmdline(args), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", env=env, shell=True)
    else:
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env, shell=False)
    out = (proc.stdout or "").strip()
    if out.startswith("{"):
        return json.loads(out)
    return {"ok": False, "raw": out[:200], "stderr": (proc.stderr or "")[:200]}


def main():
    # 支持复用已有内嵌表（EMBED_APP / EMBED_TID），避免重复插入
    app = os.environ.get("EMBED_APP")
    tid = os.environ.get("EMBED_TID")
    if app and tid:
        print(f"复用已有内嵌表: app={app} tid={tid}")
    else:
        # 1. 插入内嵌多维表格块（user 身份）
        r = f.api("POST", f"/docx/v1/documents/{DOC_ID}/blocks/{DOC_ID}/children", None,
                  {"children": [{"block_type": 18, "bitable": {"view_type": 1}}], "index": -1},
                  expect_ok=False)
        if r.get("code") != 0:
            print("插入多维表格块失败:", r); return
        token = r["data"]["children"][0]["bitable"]["token"]
        app, tid = token.split("_", 1)
        print(f"内嵌多维表格: app={app} tid={tid}")

    # 2. 改名 primary 字段 + 删默认多余字段（用固定字段名，容错）
    r = cli(["lark-cli", "base", "+field-update", "--base-token", app, "--table-id", tid,
             "--field-id", "Multiline", "--as", "user",
             "--json", '{"name":"任务名称","type":"text","style":{"type":"plain"}}', "--yes"])
    print("改名 primary:", "OK" if r.get("ok") else r.get("msg", r.get("raw")))
    for name in ["Multiline 1", "Single option"]:
        r2 = cli(["lark-cli", "base", "+field-delete", "--base-token", app, "--table-id", tid,
                  "--field-id", name, "--as", "user", "--yes"])
        print(f"删默认字段 {name}:", "OK" if r2.get("ok") else r2.get("msg", r2.get("raw")))

    # 3. 加字段
    r = cli(["lark-cli", "base", "+field-create", "--base-token", app, "--table-id", tid,
             "--as", "user", "--json", json.dumps(FIELDS, ensure_ascii=False)])
    print("加字段:", "OK" if r.get("ok") else r.get("msg", r.get("raw")))

    # 4. 加记录
    records = [{"任务名称": rec[0], "负责人": rec[1], "阶段": [rec[2]], "状态": [rec[3]],
                "开始日期": rec[4] + " 00:00", "截止日期": rec[5] + " 00:00"} for rec in RECORDS]
    r = cli(["lark-cli", "base", "+record-batch-create", "--base-token", app, "--table-id", tid,
             "--as", "user", "--json", json.dumps({"create_records": records}, ensure_ascii=False)])
    print("加记录:", "OK" if r.get("ok") else r.get("msg", r.get("raw")))

    # 5. 建甘特视图 + 绑时间轴
    r = cli(["lark-cli", "base", "+view-create", "--base-token", app, "--table-id", tid,
             "--as", "user", "--json", '{"name":"进度甘特图","type":"gantt"}'])
    print("建甘特视图:", "OK" if r.get("ok") else r.get("msg", r.get("raw")))

    print(f"\n完成。文档链接: https://lcnt98jh5zt6.feishu.cn/docx/{DOC_ID}")


if __name__ == "__main__":
    main()
