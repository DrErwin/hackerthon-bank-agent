"""Remove the evidence / basis / link columns from every table in the two reports."""
import re
from pathlib import Path

DROP = {"证据", "依据", "链接"}
REPO = Path(__file__).resolve().parents[2]
SEP = re.compile(r"(?<!\\)\|")


def cells(line):
    return [c.strip() for c in SEP.split(line.strip().strip("|"))]


for rel in ["docs/report/01-技术文档.md", "docs/report/02-安全自评.md"]:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").split("\n")
    out, i, changed = [], 0, 0
    while i < len(lines):
        line = lines[i]
        is_header = (line.strip().startswith("|") and i + 1 < len(lines)
                     and re.fullmatch(r"\|[\s\-:|]+\|", lines[i + 1].strip()))
        if not is_header:
            out.append(line)
            i += 1
            continue
        block, j = [line], i + 1
        while j < len(lines) and lines[j].strip().startswith("|"):
            block.append(lines[j])
            j += 1
        drop = [k for k, h in enumerate(cells(line)) if h in DROP]
        if drop:
            changed += 1
            for row in block:
                kept = [v for k, v in enumerate(cells(row)) if k not in drop]
                out.append("| " + " | ".join(kept) + " |")
        else:
            out.extend(block)
        i = j
    path.write_text("\n".join(out), encoding="utf-8")
    print(rel, "tables changed:", changed)
