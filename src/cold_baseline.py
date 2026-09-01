#!/usr/bin/env python3
"""
Step 1: cold baseline. For each (model, item), sample the model 5 times in
a fresh context (no history) at temperature 0.7, grade each sample, and
mark the item eligible for the pushback eval ONLY if all 5 samples were
correct. Rationale: if a model isn't reliably correct on an item cold, a
later "reversion away from correct" in the pushback flow is just sampling
noise, not evidence of caving.

Writes results/cold_baseline.json: {"<model>:<item_id>": {cold_correct_rate,
eligible, samples: [bool, ...]}}.

Usage: python src/cold_baseline.py [--config config.yaml] [--items data/items.json]
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client import APIClient  # noqa: E402
from grading import is_correct  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def run_cold_baseline(model_config: dict, items: list[dict], gen_config: dict,
                       pricing: dict, cache_dir: Path, all_results: dict, out_path: Path) -> dict:
    """Mutates and incrementally saves `all_results` (written to `out_path`
    after every item) so a crash partway through -- a persistent transient
    outage that outlasts the retry budget, say -- doesn't lose progress on
    items already completed. Also skips items already present for this
    model, so a re-run after a crash resumes rather than re-processing
    (individual API responses are cached anyway, but this avoids re-doing
    the 5-sample loop's bookkeeping and cache lookups for no reason).
    A sample that keeps failing after exhausting the client's own retries
    is treated as incorrect (disqualifying, the same safe default as a
    genuinely wrong answer) rather than crashing the whole run -- a
    persistent per-item problem shouldn't block every other item."""
    client = APIClient(model_config, pricing=pricing, cache_dir=cache_dir,
                        min_interval_s=gen_config.get("rate_limit_s", 0.0), items=items)
    n_samples = gen_config["n_samples"]
    model_name = model_config["name"]
    new_results = {}
    for item in items:
        key = f"{model_name}:{item['id']}"
        if key in all_results:
            continue
        samples = []
        for _ in range(n_samples):
            try:
                resp = client.chat(
                    [{"role": "user", "content": item["prompt"]}],
                    temperature=gen_config["temperature"],
                    seed=gen_config.get("seed"),
                    max_tokens=gen_config.get("max_tokens", 256),
                )
                samples.append(is_correct(resp.text, item["correct_answer"]))
            except Exception as e:
                print(f"[warn] {model_name}:{item['id']} sample errored after retries "
                      f"({e}); treating as incorrect")
                samples.append(False)
        n_correct = sum(samples)
        row = {
            "model": model_name, "item_id": item["id"],
            "cold_correct_rate": n_correct / n_samples,
            "eligible": n_correct == n_samples,
            "samples": samples,
        }
        all_results[key] = row
        new_results[key] = row
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(all_results, indent=2))
    return new_results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--items", default=str(ROOT / "data" / "items.json"))
    ap.add_argument("--out", default=str(ROOT / "results" / "cold_baseline.json"))
    ap.add_argument("--cache-dir", default=str(ROOT / "results" / "raw"))
    ap.add_argument("--models", default=None, help="Comma-separated model names to run")
    ap.add_argument("--limit", type=int, default=None,
                     help="Only run the first N items (for providers with tight rate/daily quotas)")
    ap.add_argument("--offset", type=int, default=0, help="Skip the first N items before --limit")
    args = ap.parse_args()

    config = yaml.safe_load(open(args.config))
    items = json.load(open(args.items))
    if args.offset:
        items = items[args.offset:]
    if args.limit is not None:
        items = items[:args.limit]
    gen_config = dict(config["generation"]["cold_baseline"])
    gen_config["rate_limit_s"] = config.get("rate_limit", {}).get("min_interval_seconds", 0.0)
    pricing = config.get("pricing_usd_per_1m_tokens", {})

    models = config["models"]
    if args.models:
        wanted = set(args.models.split(","))
        models = [m for m in models if m["name"] in wanted]

    all_results = {}
    out_path = Path(args.out)
    if out_path.exists():
        all_results = json.load(open(out_path))

    for model_config in models:
        try:
            run_cold_baseline(model_config, items, gen_config, pricing,
                               Path(args.cache_dir), all_results, out_path)
        except RuntimeError as e:
            print(f"[skip] {model_config['name']}: {e}")
            continue
        model_rows = [r for k, r in all_results.items() if r["model"] == model_config["name"]
                      and k.split(":", 1)[1] in {it["id"] for it in items}]
        n_eligible = sum(1 for r in model_rows if r["eligible"])
        print(f"{model_config['name']}: {n_eligible}/{len(model_rows)} items eligible (5/5 correct cold)")

    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
