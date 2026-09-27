"""Check that local links in current project Markdown point to existing files."""

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", ".scratch", ".github", "_archive", "_feishu_push", "node_modules"}
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def main() -> int:
    errors = []
    for document in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in document.relative_to(ROOT).parts):
            continue
        in_fence = False
        for number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for match in LINK.finditer(line):
                target = match.group(1).split(" ", 1)[0].strip("<>")
                if not target or target.startswith("#"):
                    continue
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    continue
                path = document.parent / unquote(parsed.path)
                if not path.exists():
                    errors.append(f"{document.relative_to(ROOT)}:{number}: {target}")
    for error in errors:
        print(error)
    if errors:
        print(f"Broken local links: {len(errors)}")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
