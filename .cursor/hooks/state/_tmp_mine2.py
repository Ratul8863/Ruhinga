import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
main = Path(
    r"C:\Users\UseR\.cursor\projects\f-Ratul-Ruhinga-Rohingya-Forest-Impact-Research\agent-transcripts\1ca6bbc8-e196-4f4a-9617-e3d9a4640289\1ca6bbc8-e196-4f4a-9617-e3d9a4640289.jsonl"
)
patterns = [
    r"evidence family",
    r"one evidence",
    r"double.?count",
    r"supplementary",
    r"overlapping",
    r"2023a",
    r"spatial domain",
    r"scenario projection",
    r"author-uploaded",
    r"not a causal",
    r"ESV as",
    r"primary forest",
]

def extract_text(obj):
    content = obj.get("content")
    if content is None:
        content = obj.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    return ""

with open(main, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if i < 360:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        text = extract_text(obj)
        if not text:
            continue
        for pat in patterns:
            for m in re.finditer(
                r".{0,100}" + pat + r".{0,160}", text, re.I | re.S
            ):
                s = re.sub(r"\s+", " ", m.group(0))
                print(f"L{i} [{pat}]: {s[:300]}")
                print()
