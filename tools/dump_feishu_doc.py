#!/usr/bin/env python3
"""查看飞书文档的块结构，核对同步结果。

用法：
    python tools/dump_feishu_doc.py <doc_id>              # 列出全部块
    python tools/dump_feishu_doc.py <doc_id> <关键字>      # 只列出含关键字的块
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feishu_sync as fs  # noqa: E402

TYPE_NAMES = {
    1: "page", 2: "text", 3: "h1", 4: "h2", 5: "h3", 6: "h4", 7: "h5", 8: "h6",
    12: "bullet", 13: "ordered", 14: "code", 15: "quote", 22: "divider",
    27: "image", 31: "table", 32: "table_cell", 43: "whiteboard",
}


def summarize(block):
    t = block.get("block_type")
    name = TYPE_NAMES.get(t, f"type{t}")
    payload = block.get(name) or block.get("text") or {}
    text = ""
    if isinstance(payload, dict):
        text = "".join(e.get("text_run", {}).get("content", "")
                       for e in payload.get("elements") or [])
    return name, text


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    doc_id = sys.argv[1]
    needle = sys.argv[2] if len(sys.argv) > 2 else None

    r = fs.api("GET", f"/docx/v1/documents/{doc_id}/blocks", fs.get_token(),
               params={"page_size": 500})
    items = r["data"]["items"]
    by_id = {b["block_id"]: b for b in items}
    root = by_id.get(doc_id)

    order, boards = [], []

    def walk(bid, depth=0):
        b = by_id.get(bid)
        if not b:
            return
        name, text = summarize(b)
        if name == "whiteboard":
            boards.append((b["block_id"], (b.get("board") or {}).get("token")))
        if needle is None or needle in text:
            order.append((depth, name, text[:60]))
        for c in b.get("children", []) or []:
            walk(c, depth + 1)

    if root:
        for c in root.get("children", []) or []:
            walk(c)

    print(f"共 {len(items)} 个块；画板 {len(boards)} 个"
          + (f"；命中「{needle}」{len(order)} 处" if needle else ""))
    print("注意：page_size 上限 500，超出时以下是前 500 块。\n")
    for depth, name, text in order:
        mark = "  <== 画板" if name == "whiteboard" else ""
        print(f"{'  ' * depth}{name:10} {text}{mark}")
    if boards:
        print("\n画板 token（board.token 才是画板 id）：")
        for bid, tok in boards:
            print(f"  block={bid} board={tok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
