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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_STATE = ROOT / ".feishu_state.publish.json"
GANTT_STATE = ROOT / ".feishu_state.gantt.json"

os.environ.setdefault("FEISHU_IDENTITY", "user")
os.environ.setdefault("FEISHU_STATE", str(PUBLISH_STATE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import feishu_sync as f  # noqa: E402

HEADING = "项目进度甘特图（2026-09-27 ～ 2026-11-02）"
PHASES = ["A 启动与设计", "B 基建与开发准备", "C 普通转账纵向链路",
          "D 场景扩展与前端全量", "E 验收与体验打磨", "F 比赛交付"]
STATUSES = ["未开始", "进行中", "已完成", "已阻塞"]


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
    task("Erwin 纵向后端拆票", "Erwin", "A 启动与设计", "已完成", "2026-09-27", "2026-09-27",
         "v0.3 分工确认", "12 张单目录实施票", "v03-erwin 01—12"),
    task("最小前端拆票", "梁爽、六水", "A 启动与设计", "未开始", "2026-09-27", "2026-09-28",
         "冻结接口可用", "frontend 实施票", "交付包 02"),
    task("安全评测拆票", "Ringo", "A 启动与设计", "未开始", "2026-09-27", "2026-09-28",
         "安全规格已冻结", "security 评测票与审查清单", "交付包 03"),
    task("转账评测拆票", "梁爽", "A 启动与设计", "未开始", "2026-09-27", "2026-09-28",
         "转账 PRD 已冻结", "transfer 评测票与审查清单", "交付包 03"),
    task("后续业务评测拆票", "六水、周恩宇", "A 启动与设计", "未开始", "2026-09-27", "2026-09-28",
         "账单与联动 PRD 已冻结", "bills / cross 评测票", "交付包 04"),

    task("01 后端工程骨架", "Erwin", "B 基建与开发准备", "未开始", "2026-09-27", "2026-09-28",
         "立即开始", "统一安装、测试与启动骨架", "Erwin 01"),
    task("02 公共契约代码", "Erwin", "B 基建与开发准备", "未开始", "2026-09-28", "2026-09-29",
         "01 完成", "v0.3 公共 Pydantic 模型", "Erwin 02"),
    task("03 运行存储", "Erwin", "B 基建与开发准备", "未开始", "2026-09-29", "2026-09-30",
         "02 完成", "任务、Checkpoint、操作与银行存储", "Erwin 03"),
    task("前端 UI/UX 规范、原型与迭代", "梁爽（主）、六水（协）", "A 启动与设计", "未开始", "2026-09-29", "2026-10-05",
         "契约与业务范围已冻结", "适老化规范、三场景主要流程原型及走查迭代", "前端工作线"),
    task("前端骨架 + 普通转账完整链路", "梁爽、六水", "C 普通转账纵向链路", "未开始", "2026-10-06", "2026-10-10",
         "UI/UX 原型形成可开工版本", "骨架与普通转账页面链路一起完成并可演示", "前端工作线；契约 stub / API 10"),
    task("安全评测草稿", "Ringo", "B 基建与开发准备", "未开始", "2026-09-28", "2026-09-30",
         "安全评测票已拆", "放行、拒绝、越权、注入与隐私用例", "evals/security"),
    task("转账评测草稿", "梁爽", "B 基建与开发准备", "未开始", "2026-09-28", "2026-09-30",
         "转账评测票已拆", "T01—T18、AF01—AF10 用例", "evals/transfer"),
    task("账单与跨场景评测准备", "六水、周恩宇", "B 基建与开发准备", "未开始", "2026-09-28", "2026-10-02",
         "后续业务评测票已拆", "v0.4 代表性用例", "evals/bills、evals/cross"),
    task("11 模拟银行评测草稿", "Erwin", "B 基建与开发准备", "未开始", "2026-09-27", "2026-10-02",
         "立即开始", "普通转账银行评测", "Erwin 11"),

    task("04 模拟银行与接入层", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-01", "2026-10-02",
         "02、03 完成", "真实银行接缝、防重复与结果查询", "Erwin 04"),
    task("05 审计与回放", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-01", "2026-10-02",
         "02、03 完成", "追加事件、时间线与证据包", "Erwin 05"),
    task("06 记忆与上下文", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-02", "2026-10-03",
         "02、03 完成", "称呼记忆与用户隔离", "Erwin 06"),
    task("07 最小安全门", "Erwin；Ringo 审查", "C 普通转账纵向链路", "未开始", "2026-10-01", "2026-10-03",
         "02 完成", "确认、验证、权限与最终放行", "Erwin 07"),
    task("08 普通转账参考子图", "Erwin；梁爽审查", "C 普通转账纵向链路", "未开始", "2026-10-03", "2026-10-05",
         "02、07 完成", "14 步 LangGraph 转账子图", "Erwin 08；联调依赖 04"),
    task("模拟银行评测实跑", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-03", "2026-10-05",
         "04 完成", "真实 gateway 与模拟银行评测结果", "Erwin 11"),

    task("09 主 Harness 集成", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-05", "2026-10-06",
         "03、05—08 完成", "路由、恢复与完整事件链", "Erwin 09；联调依赖 04"),
    task("10 API 与事件流", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-06", "2026-10-07",
         "09 完成", "任务、确认、验证、恢复与 SSE API", "Erwin 10"),
    task("前端真实接口联调", "梁爽、六水", "C 普通转账纵向链路", "未开始", "2026-10-10", "2026-10-12",
         "10 完成", "页面真实纵向闭环", "交付包 02"),
    task("安全实跑与审查", "Ringo", "C 普通转账纵向链路", "未开始", "2026-10-04", "2026-10-08",
         "07 完成", "安全评测结果与审查结论", "evals/security；审查 Erwin 07"),
    task("转账实跑与审查", "梁爽", "C 普通转账纵向链路", "未开始", "2026-10-05", "2026-10-08",
         "08 完成", "业务评测结果与审查结论", "evals/transfer；审查 Erwin 08"),
    task("端到端评测预跑", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-07", "2026-10-08",
         "10 与专业评测可运行", "AF01—AF14 预跑结果", "交付包 05"),

    task("AF01—AF14 联合验收", "Erwin 牵头；全员参与", "C 普通转账纵向链路", "未开始", "2026-10-08", "2026-10-10",
         "前端与三类评测就绪", "可重复验收证据", "Erwin 12"),
    task("验收问题修复缓冲", "按归属目录负责人", "C 普通转账纵向链路", "未开始", "2026-10-10", "2026-10-11",
         "联合验收发现问题", "修复票与回归结果", "每票仍限单一目录"),
    task("v0.3 收口与 v0.4 判断", "Erwin", "C 普通转账纵向链路", "未开始", "2026-10-12", "2026-10-12",
         "AF01—AF14 有最终结论", "completion.md 与下一阶段决定", "Erwin 12"),

    task("账单业务实现与前端接入", "六水", "D 场景扩展与前端全量", "未开始", "2026-10-13", "2026-10-20",
         "v0.3 收口；账单契约已冻结", "账单主流程与前端页面可用", "modules/bills；frontend"),
    task("跨场景业务实现与前端接入", "周恩宇", "D 场景扩展与前端全量", "未开始", "2026-10-13", "2026-10-20",
         "v0.3 收口；跨场景契约已冻结", "联动主流程与前端页面可用", "modules/cross；frontend"),
    task("安全底座扩展与评测收口", "Ringo", "D 场景扩展与前端全量", "未开始", "2026-10-13", "2026-10-20",
         "v0.3 收口；最小安全门已验收", "完整安全能力与评测结论", "backend/app/security；evals/security"),
    task("前端补齐账单与跨场景页面", "梁爽、六水", "D 场景扩展与前端全量", "未开始", "2026-10-11", "2026-10-17",
         "三场景流程原型已走查", "账单与跨场景主要页面和操作流程", "frontend；冻结契约 / stub"),
    task("三场景前端整合并达到可用", "梁爽、六水", "D 场景扩展与前端全量", "未开始", "2026-10-18", "2026-10-20",
         "三场景主要页面已完成", "转账、账单、跨场景前端可演示、可使用", "frontend"),
    task("整体验收与适老化体验打磨", "全员；梁爽、六水负责前端", "E 验收与体验打磨", "未开始", "2026-10-21", "2026-10-30",
         "三场景系统和前端达到可用", "全量验收、关键问题修复、体验迭代", "v0.5.0"),
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
    cli(["base", "+view-set-group", "--base-token", app_token, "--table-id", table_id,
         "--view-id", "进度甘特图", "--as", "user",
         "--json", '{"group_config":[{"field":"工作线","desc":false}]}'])
    cli(["base", "+view-set-group", "--base-token", app_token, "--table-id", table_id,
         "--view-id", "状态看板", "--as", "user",
         "--json", '{"group_config":[{"field":"状态","desc":false}]}'])
    cli(["base", "+view-set-group", "--base-token", app_token, "--table-id", table_id,
         "--view-id", "按工作线", "--as", "user",
         "--json", '{"group_config":[{"field":"工作线","desc":false}]}'])
    cli(["base", "+view-set-group", "--base-token", app_token, "--table-id", table_id,
         "--view-id", "按负责人", "--as", "user",
         "--json", '{"group_config":[{"field":"负责人","desc":false}]}'])


def write_records_once(state):
    if state.get("records_written"):
        print(f"甘特图已有 {state.get('record_count', len(RECORDS))} 条任务，跳过重复写入")
        return

    cli_records = []
    for record in RECORDS:
        row = dict(record)
        name = row["任务名称"]
        if "前端" in name:
            line = "前端"
        elif "账单" in name and "评测" not in name:
            line = "账单业务"
        elif "跨场景" in name and "评测" not in name:
            line = "跨场景业务"
        elif "安全" in name or "安全" in row["负责人"]:
            line = "安全"
        elif any(word in name for word in ("评测", "审查", "验收", "修复缓冲")):
            line = "评测与验收"
        elif any(word in name for word in ("官方", "报名", "作品提交", "最终材料")):
            line = "比赛交付"
        else:
            line = "后端底座与转账"
        row["工作线"] = line
        row["阶段"] = [row["阶段"]]
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
        print("复用现有 v0.3 甘特图")
    else:
        state = create_embedded_table(doc_id)
        setup_schema(state["app_token"], state["table_id"])
        state["schema_version"] = 2
        save_json(GANTT_STATE, state)
        print("已在《01 项目跟踪》末尾建立 v0.3 甘特图")

    write_records_once(state)
    print(f"已写入 {len(RECORDS)} 条任务，含工作线和负责人视图")
    print(f"飞书文档：https://lcnt98jh5zt6.feishu.cn/docx/{doc_id}")


if __name__ == "__main__":
    main()
