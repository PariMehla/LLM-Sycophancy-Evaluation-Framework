#!/usr/bin/env python3
"""
Convert data/dataset.json (the original sycophancy benchmark's schema,
which bakes a specific pushback + fabricated wrong answer into each item)
into the simpler schema the compliance-vs-persuasion probe expects:

    {id, prompt, correct_answer, category, difficulty}

The compliance probe doesn't need a pre-scripted wrong answer: pushback is
a generic reconsideration challenge (config.yaml's pushback_scripts), and
an LLM judge -- not string matching against a known wrong value -- decides
whether the model's follow-up response caved, held, or hedged. So
`answer_aliases`, `incorrect_answer_claimed`, and `pushback_strength` are
intentionally dropped; `pushback` is dropped since it's superseded by
config.yaml's scripts.

Run: python scripts/convert_items.py
Output: data/items.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "dataset.json"
OUT = ROOT / "data" / "items.json"

items = json.load(open(SRC))
converted = [
    {
        "id": it["id"],
        "prompt": it["question"],
        "correct_answer": it["correct_answer"],
        "category": it["category"],
        "difficulty": it.get("difficulty", "n/a"),
    }
    for it in items
]

with open(OUT, "w") as f:
    json.dump(converted, f, indent=2)

print(f"Wrote {len(converted)} items to {OUT}")
