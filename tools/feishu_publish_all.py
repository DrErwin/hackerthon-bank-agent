#!/usr/bin/env python3
"""把面向团队阅读的精选文档同步到飞书。

用法：
    python tools/feishu_publish_all.py plan             # 只列计划，不碰飞书（默认命令）
    python tools/feishu_publish_all.py sync             # 执行：缺失的新建，已存在的原地覆盖
    python tools/feishu_publish_all.py sync --only prd  # 只同步路径里带 "prd" 的
    python tools/feishu_publish_all.py sync --only 会议

三个设计要点：

1. **复用而不重写**：md → 飞书块的渲染、lark-cli 调用、状态文件，全部从
   `feishu_sync.py` 借用。本文件只管「同步哪些、叫什么标题、进哪个分区」。
2. **标题必须稳定**：飞书文档是按标题认的（状态文件 key = 标题）。标题一变，
   下次同步会新建一篇而不是更新，于是出现重复文档。所以：
   - 已发布的文档走 `TITLE_OVERRIDES`，标题一个字不改，保证原地更新；
   - 新文档用「文件夹标签 · 文件名」自动生成，不随正文标题变化。
3. **白名单发布**：仓库保存完整事实源，飞书只展示 `CURATED_SOURCES` 中团队当前
   需要阅读的文档。新增技术资料默认不上飞书；只有项目负责人确认有阅读价值后才加入。
4. **plan 是默认命令**：先看清单再决定要不要推。

已发布但退出白名单的文档不会删除；`archive-plan` 查看清单，`archive` 将它们移出
知识库到 Drive 归档文件夹。
"""

import os
import re
import sys
from pathlib import Path

# 必须赶在 import feishu_sync 之前——STATE_FILE 是它在导入时算好的。
# .feishu_state.publish.json 里存着已发布的 14 篇（标题 -> doc_id），
# 用它才能命中已有文档、原地更新。
os.environ.setdefault("FEISHU_STATE", ".feishu_state.publish.json")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feishu_sync as fs  # noqa: E402

# 上面的 setdefault 只对「先 import 本文件」的情况有效。
# 从 feishu_sync.py 委托进来时（python tools/feishu_sync.py publish），
# feishu_sync 是 __main__、早已按默认值算好 STATE_FILE=.feishu_state.json——
# 那里面只有 6 篇旧文档，已发布的 14 篇会被当成新文档重发一遍。这里直接改掉。
fs.STATE_FILE = fs.ROOT / os.environ["FEISHU_STATE"]

ROOT = fs.ROOT

# ---------- 同步范围 ----------

# 飞书是团队阅读端，不是仓库镜像。顺序也是 plan 与知识库的推荐阅读顺序。
# 维护约定：白名单跟随「当前工作台 → 当前版本里程碑 → PRD / 架构 / 契约 / 协作规则」；
# 版本推进时把新版本的 requirements / completion 加进来（旧版本条目可留作历史）。
CURATED_SOURCES = [
    "docs/team/当前工作台.md",
    "docs/README.md",
    "docs/pm/ROADMAP.md",
    "docs/versions/v0.3.0/implementation-plan.md",
    "docs/versions/v0.3.0/requirements.md",
    "docs/versions/v0.3.0/completion.md",
    "docs/versions/v0.4.0/requirements.md",
    "docs/versions/v0.4.0/completion.md",
    "docs/prd/01-智能转账-PRD-2026-09-23.md",
    "docs/prd/02-账单分析-PRD-2026-09-23.md",
    "docs/prd/06-跨场景联动-PRD-2026-09-23.md",
    "docs/prd/安全底座父级-PRD-2026-09-23.md",
    "docs/prd/MockBank-PRD-2026-09-23.md",
    "docs/architecture/system-framework-2026-09-19.md",
    "docs/contracts/公共契约-2026-09-23.md",
    "docs/contracts/银行接口字段-2026-09-24.md",
    "docs/contracts/确认验证字段-2026-09-24.md",
    "docs/contracts/安全与审计字段-2026-09-24.md",
    "docs/principles/03-review-and-merge.md",
    "docs/principles/04-cross-team-delivery.md",
]

# 目录 -> 飞书标题前缀 / 所属分区
# 分区名要与 feishu_sync.WIKI_SECTIONS 的键一致。
FOLDER_RULES = [
    ("docs", "索引", "00 索引与跟踪"),
    ("docs/team", "工作台", "00 索引与跟踪"),
    ("docs/versions", "里程碑", "00 索引与跟踪"),
    ("docs/pm/ROADMAP.md", "路线图", "00 索引与跟踪"),
    ("docs/prd", "PRD", "01 PRD 与评审"),
    ("docs/pm", "PM", "01 PRD 与评审"),
    ("docs/meetings", "会议", "01 PRD 与评审"),
    ("docs/architecture", "架构", "02 架构"),
    ("docs/contracts", "契约", "02 架构"),
    ("docs/principles", "原则", "03 规则与模板"),
    ("docs/decisions", "决策", "03 规则与模板"),
    ("docs/research", "调研", "03 规则与模板"),
    ("官方资料", "规则", "03 规则与模板"),
]

# 已发布的文档：标题保持不变，否则会在飞书里多出一份
# 注意：飞书按标题认文档，同标题只能有一篇。`docs/01-项目跟踪.md` 不在白名单
# （飞书《01 项目跟踪》发布的是 docs/team/当前工作台.md），故不再为它登记标题，
# 避免将来误加白名单时与工作台互相覆盖。
TITLE_OVERRIDES = {
    "docs/team/当前工作台.md": "01 项目跟踪",
    "docs/README.md": "00 版本进度",
    "docs/00-项目文档索引.md": "00 项目文档索引",
    "官方资料/参赛规则与提交要求.md": "02 参赛规则与提交要求",
    "docs/architecture/system-framework-2026-09-19.md": "03 系统架构（2026-09-19）",
    "docs/architecture/review-2026-09-19/system-overview.mmd": "04 系统架构总览图",
    "docs/architecture/review-2026-09-19/transfer-interaction.mmd": "05 模拟转账交互图",
    "官方资料/模板/source-code-readme-template.md": "06 源码 README 模板",
    "docs/prd/01-智能转账-PRD-2026-09-23.md": "PRD 01 智能转账",
    "docs/prd/02-账单分析-PRD-2026-09-23.md": "PRD 02 账单分析",
    "docs/prd/06-跨场景联动-PRD-2026-09-23.md": "PRD 06 跨场景联动",
    "docs/prd/安全底座父级-PRD-2026-09-23.md": "PRD 安全底座",
    "docs/prd/MockBank-PRD-2026-09-23.md": "PRD Mock Bank",
    "docs/pm/ROADMAP.md": "PM · ROADMAP",
    "docs/pm/PRD-预审会安排.md": "PRD 预审会安排",
    "docs/pm/安全回填表.md": "安全回填表",
}


def _rule_for(rel):
    """取路径命中的目录规则（最长前缀优先）。"""
    best = None
    for prefix, label, section in FOLDER_RULES:
        if rel == prefix or rel.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best[0]):
                best = (prefix, label, section)
    return best[1:] if best else ("其他", "03 规则与模板")


# 分区展示顺序
SECTION_ORDER = ["00 索引与跟踪", "01 PRD 与评审", "02 架构", "03 规则与模板"]


def _auto_title(rel, section_label):
    path = Path(rel)
    parts = path.parts
    if len(parts) >= 4 and parts[0] == "docs" and parts[1] == "versions":
        kind = {
            "requirements": "需求",
            "completion": "完成情况",
            "implementation-plan": "实施计划",
        }.get(path.stem, path.stem)
        return f"{section_label} · {parts[2]} · {kind}"

    stem = path.stem
    if stem.upper() == "README":
        stem = path.parent.name
    return f"{section_label} · {stem}"


def discover(only=None):
    """返回白名单内待同步文档。"""
    state = fs.load_state()
    published = state.get("docs", {})

    items = []
    for rel in CURATED_SOURCES:
        if not (ROOT / rel).is_file():
            raise FileNotFoundError(f"飞书白名单文件不存在：{rel}")
        if only and only not in rel:
            continue
        label, section = _rule_for(rel)
        title = TITLE_OVERRIDES.get(rel) or _auto_title(rel, label)
        items.append({
            "local": rel,
            "title": title,
            "section": section,
            "is_new": title not in published,
        })

    # 按分区、再按路径排序，plan 看起来是一张整齐的表。
    # 「图先发」不靠这里的顺序——cmd_sync 是按后缀分两轮发的。
    order = {s: i for i, s in enumerate(SECTION_ORDER)}
    source_order = {rel: i for i, rel in enumerate(CURATED_SOURCES)}
    items.sort(key=lambda x: (order.get(x["section"], 99), source_order[x["local"]]))
    return items


# ---------- 命令 ----------

def cmd_plan():
    items = discover(_only_arg())
    state = fs.load_state()
    published = state.get("docs", {})

    print(f"状态文件：{fs.STATE_FILE.relative_to(ROOT)}（已发布 {len(published)} 篇）")
    print(f"待同步：{len(items)} 篇 —— 新建 {sum(1 for i in items if i['is_new'])}，"
          f"更新 {sum(1 for i in items if not i['is_new'])}\n")

    print(f"{'#':>3}  {'动作':<4} {'分区':<14} {'飞书标题':<30} 本地文件")
    print("-" * 118)
    sec = None
    for n, it in enumerate(items, 1):
        if it["section"] != sec:
            sec = it["section"]
            print(f"--- {sec} " + "-" * (110 - len(sec)))
        print(f"{n:>3}  {'新建' if it['is_new'] else '更新':<4} {it['section']:<14} "
              f"{it['title']:<30} {it['local']}")

    print("\n分区名与 tools/feishu_sync.py 的 WIKI_SECTIONS 对应；挂进知识库见该文件顶部说明。")
    print("确认无误后执行：python tools/feishu_publish_all.py sync")
    return 0


def cmd_sync():
    items = discover(_only_arg())
    if not items:
        print("没有匹配的文档。")
        return 0

    state = fs.load_state()
    state.setdefault("docs", {})
    fs.links_state = state["docs"]

    push_dir = ROOT / "_feishu_push"
    push_dir.mkdir(exist_ok=True)

    created = updated = failed = 0
    # 两轮：第一轮只发图，第二轮发正文（正文里的配图链接要用第一轮拿到的 doc_id）
    for round_no in (1, 2):
        batch = [i for i in items if (i["local"].endswith(".mmd")) == (round_no == 1)]
        if not batch:
            continue
        print(f"—— 第 {round_no} 轮（{'图' if round_no == 1 else '正文'}，{len(batch)} 篇）——")
        for it in batch:
            text = fs._render_doc(it["local"], it["title"], fs.FIGURE_LINKS.get(it["title"]))
            tmp = push_dir / (re.sub(r"[^\w.-]", "_", it["title"]) + ".md")
            tmp.write_text(text, encoding="utf-8")
            rel = tmp.relative_to(ROOT).as_posix()

            meta = state["docs"].get(it["title"])
            if meta:
                res = fs._run_cli(["lark-cli", "docs", "+update", "--doc", meta["doc_id"],
                                   "--command", "overwrite", "--doc-format", "markdown",
                                   "--content", "@./" + rel, "--as", "user", "--json"])
                action = "更新"
            else:
                res = fs._run_cli(["lark-cli", "docs", "+create", "--title", it["title"],
                                   "--doc-format", "markdown", "--content", "@./" + rel,
                                   "--as", "user", "--json"])
                action = "新建"

            did = fs._doc_id_from(res)
            if res.get("ok") and did:
                state["docs"][it["title"]] = {"doc_id": did, "local": it["local"]}
                if action == "新建":
                    created += 1
                else:
                    updated += 1
                print(f"  {action} {it['title']}")
            else:
                failed += 1
                print(f"  失败 {it['title']}：{str(res.get('error') or res)[:200]}")
            fs.save_state(state)

    print(f"\n完成：新建 {created}，更新 {updated}，失败 {failed}")
    fs.print_links()
    return 1 if failed else 0


def cmd_mount():
    """把已发布的文档挂进知识库对应分区。幂等：已在知识库里的直接跳过。

    用法：python tools/feishu_publish_all.py mount [--only <路径子串>]
    """
    items = discover(_only_arg())
    if not items:
        print("没有匹配的文档。")
        return 0

    published = fs.load_state().get("docs", {})
    moved = skipped = failed = 0

    for it in items:
        meta = published.get(it["title"])
        if not meta:
            print(f"  跳过（还没发布）  {it['title']}")
            skipped += 1
            continue
        parent = fs.WIKI_SECTIONS.get(it["section"])
        if not parent:
            print(f"  跳过（分区无节点）{it['title']} [{it['section']}]")
            skipped += 1
            continue

        # 已在知识库 -> 跳过。不在则会返回 131014 document is not in wiki。
        probe = fs._run_cli(["lark-cli", "wiki", "+node-get",
                             "--node-token", meta["doc_id"], "--as", "user", "--json"])
        if probe.get("ok"):
            print(f"  已在知识库  {it['title']}")
            skipped += 1
            continue

        res = fs._run_cli(["lark-cli", "wiki", "+move", "--obj-type", "docx",
                           "--obj-token", meta["doc_id"],
                           "--target-space-id", fs.WIKI_SPACE_ID,
                           "--target-parent-token", parent,
                           "--as", "user", "--json"])
        if res.get("ok"):
            print(f"  挂载 [{it['section']}]  {it['title']}")
            moved += 1
        else:
            print(f"  失败 {it['title']}：{str(res.get('error') or res)[:180]}")
            failed += 1

    print(f"\n完成：挂载 {moved}，跳过 {skipped}，失败 {failed}")
    return 1 if failed else 0


def _non_curated_published():
    curated_titles = {item["title"] for item in discover()}
    published = fs.load_state().get("docs", {})
    return [(title, meta) for title, meta in published.items() if title not in curated_titles]


def cmd_archive_plan():
    """列出已发布、但不再进入团队知识库的文档。只读。"""
    items = _non_curated_published()
    print(f"保留在团队知识库：{len(discover())} 篇")
    print(f"移出知识库、保留在 Drive 归档：{len(items)} 篇\n")
    for title, meta in items:
        print(f"  {title:<38} {meta.get('local', '')}")
    return 0


def cmd_archive():
    """把非白名单文档移出知识库，保留在 Drive 归档文件夹。"""
    items = _non_curated_published()
    if not items:
        print("没有需要归档的飞书文档。")
        return 0

    state = fs.load_state()
    folder_token = state.get("archive_folder_token")
    if not folder_token:
        result = fs._run_cli(["lark-cli", "drive", "+create-folder",
                              "--name", "FinTechathon 2026 · 技术资料归档",
                              "--as", "user", "--json"])
        data = result.get("data", {})
        folder_token = data.get("token") or data.get("folder_token")
        if not result.get("ok") or not folder_token:
            print(f"创建归档文件夹失败：{str(result.get('error') or result)[:200]}")
            return 1
        state["archive_folder_token"] = folder_token
        fs.save_state(state)
        print("已建立 Drive 归档文件夹")

    moved = skipped = failed = 0
    for title, meta in items:
        probe = fs._run_cli(["lark-cli", "wiki", "+node-get",
                             "--node-token", meta["doc_id"],
                             "--as", "user", "--json"])
        node_token = probe.get("data", {}).get("node_token") if probe.get("ok") else None
        if not node_token:
            print(f"  已不在知识库  {title}")
            skipped += 1
            continue

        result = fs._run_cli(["lark-cli", "wiki", "+move-to-drive",
                              "--node-token", node_token,
                              "--folder-token", folder_token,
                              "--as", "user", "--json"])
        if result.get("ok"):
            print(f"  归档  {title}")
            moved += 1
        else:
            print(f"  失败  {title}：{str(result.get('error') or result)[:160]}")
            failed += 1

    print(f"\n完成：归档 {moved}，已归档 {skipped}，失败 {failed}")
    return 1 if failed else 0


def _only_arg():
    if "--only" in sys.argv:
        i = sys.argv.index("--only")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


if __name__ == "__main__":
    cmd = next((a for a in sys.argv[1:] if not a.startswith("-")), "plan")
    {"plan": cmd_plan, "sync": cmd_sync, "mount": cmd_mount,
     "archive-plan": cmd_archive_plan, "archive": cmd_archive}.get(cmd, cmd_plan)()
