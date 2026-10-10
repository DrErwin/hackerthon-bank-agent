#!/usr/bin/env python3
"""在当前飞书《01 项目跟踪》中建立项目进度甘特图与分组视图。

用法：python tools/embed_stages.py

文档正文由 feishu_sync.py publish 覆盖，因此应先发布文档，再运行本脚本。
脚本把内嵌多维表格坐标保存在被 git 忽略的 .feishu_state.gantt.json；
重复运行会刷新记录，不重复创建仍然存在的表格。
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_STATE = ROOT / ".feishu_state.publish.json"
GANTT_STATE = ROOT / ".feishu_state.gantt.json"

os.environ.setdefault("FEISHU_IDENTITY", "user")
os.environ.setdefault("FEISHU_STATE", str(PUBLISH_STATE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import feishu_sync as f  # noqa: E402

HEADING = "项目进度甘特图（2026-10-11 ～ 2026-11-02；v0.4 最晚 10-20 收口）"
PHASES = ["D1 v0.4 账单", "D2 v0.4 安全完整性", "D3 v0.4 完整前端",
          "D4 v0.4 底座遗留", "D5 v0.4 联合验收与收口",
          "E v0.5 验收与体验", "F 比赛交付"]
STATUSES = ["未开始", "进行中", "已完成", "已阻塞"]
WORKLINES = {
    "D1 v0.4 账单": "账单业务",
    "D2 v0.4 安全完整性": "安全",
    "D3 v0.4 完整前端": "前端",
    "D4 v0.4 底座遗留": "后端底座",
    "D5 v0.4 联合验收与收口": "评测与验收",
    "E v0.5 验收与体验": "验收与体验",
    "F 比赛交付": "比赛交付",
}


def task(name, owner, phase, status, start, end, signal, output, ticket):
    return {
        "任务名称": name,
        "负责人": owner,
        "阶段": phase,
        "状态": status,
        "开始日期": f.ts(start),
        "截止日期": f.ts(end),
        "开始信号": signal,
        "交付物": output,
        "关联票/依赖": ticket,
    }


RECORDS = [
    task("账单业务能力实现", "周恩宇", "D1 v0.4 账单", "未开始", "2026-10-11", "2026-10-16",
         "接包即拆票（PRD/契约/21 条用例已冻结）", "bills 三类公开能力；接口形态冻结即通知前端",
         "v04-bills/01"),
    task("账单评测扩下限并实跑", "周恩宇", "D1 v0.4 账单", "未开始", "2026-10-14", "2026-10-18",
         "账单能力可运行", "BF01—BF07 证据归档 evals/bills/evidence", "v04-bills/01；evals/bills"),

    task("安全检测器与检测层（#86）", "Ringo（PM 代行条款）", "D2 v0.4 安全完整性", "未开始", "2026-10-11", "2026-10-16",
         "v0.4 已启动，立即可做", "真实风险检测器接入统一安全链路", "Issue #86；v04-security/01"),
    task("安全评测完整性扩充（#88）", "Ringo", "D2 v0.4 安全完整性", "未开始", "2026-10-11", "2026-10-16",
         "立即可做", "R06 补 2、8 组补到 ≥10、SEC-E-006/v06 修订、MAT 改编接入", "Issue #88"),
    task("SEC-C-001 转正复跑（33 轮 gated）", "Ringo", "D2 v0.4 安全完整性", "已阻塞", "2026-10-16", "2026-10-18",
         "#84 规划入口上下文修复完成（提供方 Erwin）", "gated 全转正 + 补验加回记录", "v04-security/01"),

    task("原型五类画面补齐并走查", "梁爽（主）、六水（协）", "D3 v0.4 完整前端", "进行中", "2026-10-11", "2026-10-13",
         "原型 v0.1 已交；候选/等待/人脸/恢复/修改待补", "走查确认＝前端交付包开工前置", "交付包 02 原型线；Issue #89"),
    task("完整前端底盘 + 转账插槽（stub 先行）", "梁爽、六水", "D3 v0.4 完整前端", "未开始", "2026-10-13", "2026-10-17",
         "原型走查确认", "五链路底盘与转账页面", "frontend-complete/01"),
    task("账单插槽接入并替换简易前端", "梁爽、六水", "D3 v0.4 完整前端", "未开始", "2026-10-16", "2026-10-19",
         "账单接口形态冻结信号", "双场景可用 + 替换回归 FE-01—FE-06", "frontend-complete/01"),

    task("#84 规划入口上下文（优先）", "Erwin", "D4 v0.4 底座遗留", "未开始", "2026-10-11", "2026-10-15",
         "v0.4 已启动；安全线转正复跑依赖本项", "规划入口携带对话历史与业务状态", "Issue #84"),
    task("#85 确认/验证历史只读回放", "Erwin", "D4 v0.4 底座遗留", "未开始", "2026-10-14", "2026-10-17",
         "#84 完成后接续", "只读回放接口", "Issue #85"),

    task("v0.4 联合验收与收口（最晚 10-20）", "Erwin 牵头；全员参与", "D5 v0.4 联合验收与收口", "未开始", "2026-10-18", "2026-10-20",
         "账单 BF、前端 FE、安全转正三线交付", "completion + 飞书 + 补验；PM 硬截止 2026-10-20", "v04-bills/02"),

    task("联动业务、评测与前端接入", "周恩宇（业务）、梁爽/六水（前端）", "E v0.5 验收与体验", "未开始", "2026-10-21", "2026-10-24",
         "v0.4 收口", "联动主流程、23 条用例实跑与前端插槽", "06 PRD；frontend-complete 增量小包"),
    task("系统验收与适老化体验打磨", "全员；前端梁爽、六水", "E v0.5 验收与体验", "未开始", "2026-10-21", "2026-10-30",
         "三场景系统可用", "全量评测、关键修复、体验迭代", "v0.5.0"),
    task("最终材料整理与作品提交", "全员", "F 比赛交付", "未开始", "2026-10-31", "2026-11-02",
         "核心验收与体验打磨完成", "源码、技术文档、答辩 PPT、安全自评及可选视频", "v1.0.0；官方截止 11-02"),
]


def load_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def tracker_doc_id():
    state = load_json(PUBLISH_STATE)
    entry = state.get("docs", {}).get("01 项目跟踪")
    if not entry:
        raise RuntimeError(".feishu_state.publish.json 中没有《01 项目跟踪》，请先发布文档")
    return entry["doc_id"]


def cli(args):
    env = dict(os.environ, MSYS_NO_PATHCONV="1")
    exe = shutil.which("lark-cli.cmd") or shutil.which("lark-cli")
    if not exe:
        raise RuntimeError("未找到 lark-cli")
    command = subprocess.list2cmdline([exe, *args]) if exe.lower().endswith((".cmd", ".bat")) else [exe, *args]
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=env, shell=isinstance(command, str))
    out = (proc.stdout or "").strip()
    result = json.loads(out) if out.startswith("{") else {"ok": False, "raw": out, "stderr": proc.stderr}
    if not result.get("ok"):
        raise RuntimeError(f"lark-cli 失败：{result.get('msg') or result.get('raw') or result.get('stderr')}")
    return result


def block_still_embedded(doc_id, block_id):
    if not block_id:
        return False
    r = f.api("GET", f"/docx/v1/documents/{doc_id}/blocks", f.get_token(),
              params={"page_size": 500}, expect_ok=False)
    if r.get("code") != 0:
        return False
    return any(item.get("block_id") == block_id for item in r["data"].get("items", []))


def create_embedded_table(doc_id):
    r = f.api("POST", f"/docx/v1/documents/{doc_id}/blocks/{doc_id}/children", f.get_token(),
              {"children": [
                  {"block_type": 4, "heading2": {
                      "elements": [{"text_run": {"content": HEADING}}], "style": {}}},
                  {"block_type": 18, "bitable": {"view_type": 1}},
              ], "index": -1}, expect_ok=False)
    if r.get("code") != 0:
        raise RuntimeError(f"插入飞书多维表格失败：{r.get('msg')}")
    bitable = next(item for item in r["data"]["children"] if item.get("bitable"))
    app_token, table_id = bitable["bitable"]["token"].split("_", 1)
    return {"doc_id": doc_id, "block_id": bitable["block_id"],
            "app_token": app_token, "table_id": table_id}


def set_view_group(app_token, table_id, view_id, field):
    payload = json.dumps({"group_config": [{"field": field, "desc": False}]}, ensure_ascii=False)
    for attempt in range(3):
        try:
            cli(["base", "+view-set-group", "--base-token", app_token, "--table-id", table_id,
                 "--view-id", view_id, "--as", "user", "--json", payload])
            return
        except RuntimeError as exc:
            if attempt == 2:
                print(f"警告：视图「{view_id}」按 {field} 分组失败（不影响任务数据）：{exc}")
            else:
                time.sleep(5)


def setup_schema(app_token, table_id):
    fields = f.list_fields(app_token, table_id)
    primary = next((field for field in fields if field.get("is_primary")), fields[0])
    f.rename_field(app_token, table_id, primary["field_id"], "任务名称", 1)
    for field in fields:
        if not field.get("is_primary"):
            f.delete_field(app_token, table_id, field["field_id"])

    f.add_field(app_token, table_id, "负责人", 1)
    f.add_field(app_token, table_id, "工作线", 1)
    f.add_field(app_token, table_id, "阶段", 3, options=PHASES)
    f.add_field(app_token, table_id, "状态", 3, options=STATUSES)
    f.add_field(app_token, table_id, "开始日期", 5,
                prop={"date_formatter": "yyyy-MM-dd", "auto_fill": False})
    f.add_field(app_token, table_id, "截止日期", 5,
                prop={"date_formatter": "yyyy-MM-dd", "auto_fill": False})
    f.add_field(app_token, table_id, "开始信号", 1)
    f.add_field(app_token, table_id, "交付物", 1)
    f.add_field(app_token, table_id, "关联票/依赖", 1)

    ok, result = f.add_view(app_token, table_id, "进度甘特图", "gantt")
    if not ok:
        raise RuntimeError(f"创建甘特视图失败：{result.get('msg')}")
    f.add_view(app_token, table_id, "状态看板", "kanban")
    f.add_view(app_token, table_id, "按工作线", "grid")
    f.add_view(app_token, table_id, "按负责人", "grid")
    cli(["base", "+view-set-timebar", "--base-token", app_token, "--table-id", table_id,
         "--view-id", "进度甘特图", "--as", "user",
         "--json", '{"start_time":"开始日期","end_time":"截止日期","title":"任务名称"}'])
    set_view_group(app_token, table_id, "进度甘特图", "工作线")
    set_view_group(app_token, table_id, "状态看板", "状态")
    set_view_group(app_token, table_id, "按工作线", "工作线")
    set_view_group(app_token, table_id, "按负责人", "负责人")


def write_records_once(state):
    if state.get("records_written"):
        print(f"甘特图已有 {state.get('record_count', len(RECORDS))} 条任务，跳过重复写入")
        return

    cli_records = []
    for record in RECORDS:
        row = dict(record)
        phase = row["阶段"]
        row["工作线"] = WORKLINES[phase]
        row["阶段"] = [phase]
        row["状态"] = [row["状态"]]
        for field in ("开始日期", "截止日期"):
            import datetime
            timezone = datetime.timezone(datetime.timedelta(hours=8))
            row[field] = datetime.datetime.fromtimestamp(row[field] / 1000, timezone).strftime("%Y-%m-%d %H:%M")
        cli_records.append(row)

    for start in range(0, len(cli_records), 6):
        cli(["base", "+record-batch-create", "--base-token", state["app_token"],
             "--table-id", state["table_id"], "--as", "user",
             "--json", json.dumps({"create_records": cli_records[start:start + 6]}, ensure_ascii=False)])
    state["records_written"] = True
    state["record_count"] = len(RECORDS)
    save_json(GANTT_STATE, state)


def main():
    doc_id = tracker_doc_id()
    state = load_json(GANTT_STATE)
    reusable = (state.get("doc_id") == doc_id and
                block_still_embedded(doc_id, state.get("block_id")))
    if reusable:
        print("复用现有甘特图")
    else:
        state = create_embedded_table(doc_id)
        save_json(GANTT_STATE, state)  # 先落盘：后续步骤失败时重跑可复用，不再重复建表
        setup_schema(state["app_token"], state["table_id"])
        state["schema_version"] = 2
        save_json(GANTT_STATE, state)
        print("已在《01 项目跟踪》末尾重建 v0.4 甘特图")

    write_records_once(state)
    print(f"已写入 {len(RECORDS)} 条任务，含工作线和负责人视图")
    print(f"飞书文档：https://lcnt98jh5zt6.feishu.cn/docx/{doc_id}")


if __name__ == "__main__":
    main()
