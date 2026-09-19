#!/usr/bin/env python3
"""把 archify 图源 spec（JSON）转成 Mermaid，供飞书画板嵌入。

为什么需要它：飞书文档用原生画板块承载图，而 archify 产物是内联 SVG，
不含 Mermaid 源码。本脚本按固定映射从 spec 重建语义拓扑。

用法：
    python tools/spec_to_mermaid.py <spec.json> [输出.mmd]
    python tools/spec_to_mermaid.py --check <spec.json>   # 只校验能否转换

支持 diagram_type：architecture、sequence。其余类型直接报错，不猜。

注意：Mermaid 由飞书自动排版，spec 里手工调的坐标不会保留，出图外观与
archify HTML 不一致。这是刻意的取舍——飞书里要可编辑的原生画板。
"""

import json
import re
import sys
from pathlib import Path

# archify 的组件类型 -> Mermaid 形状。Mermaid 没有对应的语义分类，
# 只能近似表达；改这里会同时改变所有图的呈现。
SHAPES = {
    "frontend":  ("[", "]"),
    "backend":   ("[", "]"),
    "database":  ("[(", ")]"),
    "security":  ("{{", "}}"),
    "messagebus":("[[", "]]"),
    "cloud":     ("([", "])"),
    "external":  ("(", ")"),
}

# 语法关键字与标点会破坏 Mermaid 解析，统一清掉。
_UNSAFE = re.compile(r'["\[\]{}()|<>`;]')


def _sid(node_id):
    """节点 id 转成 Mermaid 合法标识符。"""
    s = re.sub(r"[^0-9A-Za-z_]", "_", str(node_id))
    return s if s and not s[0].isdigit() else "n_" + s


def _text(value):
    """把任意标签压成单行安全文本。"""
    if value is None:
        return ""
    s = _UNSAFE.sub("", str(value).replace("\n", " ")).strip()
    return re.sub(r"\s+", " ", s)


def _short_boundary_label(label):
    """边界标签形如「模块化后端 · 安全与权限控制贯穿各边界」，取分隔符前的短名。"""
    return _text(str(label).split("·")[0].strip())


def _node_def(cid, comp):
    """生成一行节点定义，带 sublabel 时用 <br/> 换行。"""
    left, right = SHAPES.get(comp.get("type", "backend"), SHAPES["backend"])
    label = _text(comp.get("label", cid))
    sub = _text(comp.get("sublabel", ""))
    body = f"{label}<br/>{sub}" if sub else label
    return f"    {_sid(cid)}{left}\"{body}\"{right}"


def architecture_to_mermaid(spec):
    comps = spec.get("components", [])
    conns = spec.get("connections", [])
    bounds = spec.get("boundaries", [])
    if not comps:
        raise ValueError("spec 没有 components，无法转换")

    by_id = {c["id"]: c for c in comps}
    lines = ["flowchart TB"]

    wrapped = set()
    for b in bounds:
        members = [m for m in b.get("wraps", []) if m in by_id]
        if not members:
            continue
        wrapped.update(members)
        lines.append(f'    subgraph {_sid(b.get("id") or b["label"])}["{_short_boundary_label(b["label"])}"]')
        for m in members:
            lines.append(_node_def(m, by_id[m]))
        lines.append("    end")

    # 未被边界包裹的节点单独成组，避免它们被 Mermaid 塞进上一个 subgraph。
    loose = [c for c in comps if c["id"] not in wrapped]
    if loose and wrapped:
        lines.append('    subgraph external["外部"]')
        for c in loose:
            lines.append(_node_def(c["id"], c))
        lines.append("    end")
    else:
        for c in loose:
            lines.append(_node_def(c["id"], c))

    for c in conns:
        f, t = _sid(c["from"]), _sid(c["to"])
        label = _text(c.get("label", ""))
        arrow = "-->" if c.get("variant") not in ("dashed",) else "-.->"
        lines.append(f"    {f} {arrow}|{label}| {t}" if label else f"    {f} {arrow} {t}")

    return "\n".join(lines) + "\n"


def sequence_to_mermaid(spec):
    parts = spec.get("participants", [])
    msgs = sorted(spec.get("messages", []), key=lambda x: x.get("y", 0))
    segs = sorted(spec.get("segments", []), key=lambda s: s.get("from", 0))
    if not parts:
        raise ValueError("spec 没有 participants，无法转换")

    lines = ["sequenceDiagram", "    autonumber"]
    for p in parts:
        lines.append(f"    participant {_sid(p['id'])} as {_text(p.get('label', p['id']))}")

    # 分段用 Note over 表达。不用 Mermaid 的 block/end——实测飞书画板不支持该语法，
    # 含 block 的序列图会整张解析失败、连画板块都不会创建。
    def seg_of(y):
        for idx, seg in enumerate(segs):
            start = seg.get("from", 0)
            end = segs[idx + 1].get("from", float("inf")) if idx + 1 < len(segs) else float("inf")
            if start <= y < end:
                return _text(seg.get("label", ""))
        return None

    first, last = _sid(parts[0]["id"]), _sid(parts[-1]["id"])
    current = None
    for m in msgs:
        seg = seg_of(m.get("y", 0))
        if seg and seg != current:
            current = seg
            lines.append(f"    Note over {first},{last}: {seg}")
        f, t = _sid(m["from"]), _sid(m["to"])
        label = _text(m.get("label", ""))
        arrow = "-->>" if m.get("variant") == "return" else "->>"
        lines.append(f"    {f}{arrow}{t}: {label}")

    return "\n".join(lines) + "\n"


def convert(spec):
    dtype = spec.get("diagram_type") or spec.get("meta", {}).get("diagram_type")
    if dtype == "architecture":
        return architecture_to_mermaid(spec)
    if dtype == "sequence":
        return sequence_to_mermaid(spec)
    raise ValueError(f"不支持的 diagram_type: {dtype}（当前只支持 architecture / sequence）")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    src = Path(args[0])
    spec = json.loads(src.read_text(encoding="utf-8"))
    mmd = convert(spec)

    if "--check" in sys.argv:
        n = len([l for l in mmd.splitlines() if l.strip()])
        print(f"{src.name}: 可转换，输出 {n} 行 Mermaid")
        return 0

    out = Path(args[1]) if len(args) > 1 else src.with_suffix(".mmd")
    out.write_text(mmd, encoding="utf-8")
    print(f"已写出 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
