#!/usr/bin/env python3
"""把项目任务按阶段拆成独立多维表格 + 一个总览表，嵌入《01 项目跟踪》。

用法：FEISHU_IDENTITY=user python tools/embed_stages.py
"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feishu_sync as f  # noqa: E402

DOC = "CQ8AdPiEbodvrHxjaEjczPN9nHg"
OLD_TABLE_BLOCK = "doxcnf0cXSF265bTVHhMqi1N9Ae"

# 六个阶段（标题, 任务列表: 名称/负责人/状态/开始/截止）
STAGES = [
    ("阶段一 · PRD（09-16 ~ 09-20）", [
        ("五份 PRD 初稿交齐", "待定", "进行中", "2026-09-16", "2026-09-18"),
        ("整合总 PRD + 评审", "Erwin", "未开始", "2026-09-19", "2026-09-20"),
    ]),
    ("阶段二 · 契约 + 评测（09-21 ~ 09-25）", [
        ("契约（packages/contracts）", "Erwin", "未开始", "2026-09-21", "2026-09-25"),
        ("架构细化", "Erwin", "未开始", "2026-09-21", "2026-09-25"),
        ("评测集框架", "待定", "未开始", "2026-09-21", "2026-09-25"),
        ("UX PRD", "待定", "未开始", "2026-09-21", "2026-09-25"),
        ("任务评测集用例", "待定", "未开始", "2026-09-23", "2026-09-25"),
        ("契约冻结（里程碑）", "Erwin", "未开始", "2026-09-25", "2026-09-25"),
    ]),
    ("阶段三 · 转账端到端（09-26 ~ 09-30）", [
        ("基座子模块并行", "Erwin", "未开始", "2026-09-26", "2026-09-28"),
        ("端到端收口", "Erwin", "未开始", "2026-09-29", "2026-09-30"),
        ("转账评测集跑通", "待定", "未开始", "2026-09-30", "2026-09-30"),
    ]),
    ("阶段四 · 场景 + 安全（10-01 ~ 10-07）", [
        ("账单分析", "待定", "未开始", "2026-10-01", "2026-10-07"),
        ("跨场景联动", "待定", "未开始", "2026-10-01", "2026-10-07"),
        ("安全层完整 + 安全评测集", "待定", "未开始", "2026-10-01", "2026-10-07"),
    ]),
    ("阶段五 · 验收 + 打磨（10-08 ~ 10-12）", [
        ("跑评测集 + 打磨", "待定", "未开始", "2026-10-08", "2026-10-12"),
    ]),
    ("阶段六 · 缓冲期（10-13 ~ 11-02）", [
        ("扩展场景", "待定", "未开始", "2026-10-13", "2026-10-25"),
        ("交付物", "待定", "未开始", "2026-10-20", "2026-11-01"),
        ("官方答疑", "Erwin", "未开始", "2026-10-28", "2026-10-28"),
        ("报名截止", "Erwin", "未开始", "2026-11-01", "2026-11-01"),
        ("提交截止", "Erwin", "未开始", "2026-11-02", "2026-11-02"),
    ]),
]

STAGE_FIELDS = [
    {"name": "负责人", "type": "text"},
    {"name": "状态", "type": "select", "multiple": False,
     "options": [{"name": "未开始"}, {"name": "进行中"}, {"name": "已完成"}]},
    {"name": "开始日期", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
    {"name": "截止日期", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
]

OVERVIEW_FIELDS = [
    {"name": "负责人", "type": "text"},
    {"name": "阶段", "type": "select", "multiple": False,
     "options": [{"name": "PRD"}, {"name": "契约+评测"}, {"name": "转账端到端"},
                 {"name": "场景+安全"}, {"name": "验收"}, {"name": "缓冲期"}]},
    {"name": "状态", "type": "select", "multiple": False,
     "options": [{"name": "未开始"}, {"name": "进行中"}, {"name": "已完成"}]},
    {"name": "开始日期", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
    {"name": "截止日期", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
]

STATUS_OPTIONS = [{"name": "未开始"}, {"name": "进行中"}, {"name": "已完成"}]


def cli(args):
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    exe = shutil.which("lark-cli")
    p = subprocess.run(subprocess.list2cmdline(args) if exe.lower().endswith((".cmd", ".bat")) else args,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, shell=(exe.lower().endswith((".cmd", ".bat"))))
    out = (p.stdout or "").strip()
    return json.loads(out) if out.startswith("{") else {"ok": False, "raw": out[:200]}


def setup_table(app, tid, fields, records, has_stage=False):
    """改 primary、删默认字段、加字段、加记录、建甘特视图并修正 timebar。"""
    # 改名 primary + 删默认字段
    cli(["lark-cli", "base", "+field-update", "--base-token", app, "--table-id", tid,
         "--field-id", "Multiline", "--as", "user",
         "--json", '{"name":"任务名称","type":"text","style":{"type":"plain"}}', "--yes"])
    for name in ["Multiline 1", "Single option"]:
        cli(["lark-cli", "base", "+field-delete", "--base-token", app, "--table-id", tid,
             "--field-id", name, "--as", "user", "--yes"])
    # 加字段
    r = cli(["lark-cli", "base", "+field-create", "--base-token", app, "--table-id", tid,
             "--as", "user", "--json", json.dumps(fields, ensure_ascii=False)])
    # 加记录
    recs = []
    for rec in records:
        row = {"任务名称": rec[0], "负责人": rec[1], "状态": [rec[2]],
               "开始日期": rec[3] + " 00:00", "截止日期": rec[4] + " 00:00"}
        if has_stage:
            row["阶段"] = [rec[5]] if len(rec) > 5 else []
        recs.append(row)
    cli(["lark-cli", "base", "+record-batch-create", "--base-token", app, "--table-id", tid,
         "--as", "user", "--json", json.dumps({"create_records": recs}, ensure_ascii=False)])
    # 建甘特视图 + 修正 timebar
    cli(["lark-cli", "base", "+view-create", "--base-token", app, "--table-id", tid,
         "--as", "user", "--json", '{"name":"进度甘特图","type":"gantt"}'])
    cli(["lark-cli", "base", "+view-set-timebar", "--base-token", app, "--table-id", tid,
         "--view-id", "进度甘特图", "--as", "user",
         "--json", '{"start_time":"开始日期","end_time":"截止日期","title":"任务名称"}'])


def insert_heading_and_table(doc, index, heading):
    """在指定 index 插入一个 H3 标题 + 一个空多维表格块，返回 (新index, app, tid)。"""
    r = f.api("POST", f"/docx/v1/documents/{doc}/blocks/{doc}/children", None,
              {"children": [
                  {"block_type": 5, "heading3": {
                      "elements": [{"text_run": {"content": heading}}], "style": {}}},
                  {"block_type": 18, "bitable": {"view_type": 1}},
              ], "index": index}, expect_ok=False)
    if r.get("code") != 0:
        print(f"插入失败 index={index}: {r}")
        return None, None, None
    children = r["data"]["children"]
    token = next(c["bitable"]["token"] for c in children if c.get("bitable"))
    app, tid = token.split("_", 1)
    return index + 2, app, tid


def main():
    # 1. 删旧的大表
    r = cli(["lark-cli", "docs", "+update", "--doc", DOC, "--command", "block_delete",
             "--block-id", OLD_TABLE_BLOCK, "--as", "user"])
    print("删旧表:", "OK" if r.get("ok") else r.get("raw"))

    # 2. 找「任务时间线」说明文本的 index（在它之后插入）
    blocks = f.api("GET", f"/docx/v1/documents/{DOC}/blocks", None,
                   params={"page_size": 500}, expect_ok=False)["data"]["items"]
    root = next(b for b in blocks if b["block_id"] == DOC)
    # 说明文本块 Y3CIdPMYNoOyz6xxo7PceO9Ln2f 在顶层 children 里的 index
    anchor = "Y3CIdPMYNoOyz6xxo7PceO9Ln2f"
    try:
        insert_at = root["children"].index(anchor) + 1
    except ValueError:
        insert_at = 2
    print("插入起点 index:", insert_at)

    # 3. 逐阶段插入表
    idx = insert_at
    overview_records = []  # 汇总（含阶段字段）
    stage_names = ["PRD", "契约+评测", "转账端到端", "场景+安全", "验收", "缓冲期"]
    for i, (heading, tasks) in enumerate(STAGES):
        stage_name = stage_names[i]
        idx, app, tid = insert_heading_and_table(DOC, idx, heading)
        if not app:
            break
        setup_table(app, tid, STAGE_FIELDS, tasks)
        print(f"{heading}: 已建（{len(tasks)} 条）")
        for t in tasks:
            overview_records.append(t + (stage_name,))

    # 4. 建总览表
    idx, app, tid = insert_heading_and_table(DOC, idx, "项目总览（全部任务 · 甘特视图）")
    if app:
        setup_table(app, tid, OVERVIEW_FIELDS, overview_records, has_stage=True)
        print(f"项目总览: 已建（{len(overview_records)} 条）")

    print(f"\n完成。文档: https://lcnt98jh5zt6.feishu.cn/docx/{DOC}")


if __name__ == "__main__":
    main()
