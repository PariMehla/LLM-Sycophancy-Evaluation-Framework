# Compliance vs. Persuasion Probe

An extension to the sycophancy-under-pushback harness (see the main
[README.md](README.md) for that original project) that adds a cold
baseline, an LLM-judge verdict, and post-cave probes distinguishing two
very different things a "caved" response can mean:

- **Compliance**: the model caved in the pressured conversation, but the
  wrong belief didn't stick — a brand-new, pressure-free conversation
  reverts to the correct answer. Social friction, not real persuasion.
- **Persuasion**: the model caved, and the wrong answer survives into a
  fresh context too — something closer to an actual (mistaken) belief
  update, not just momentary deference.

## Pipeline

```
1. Cold baseline    (src/cold_baseline.py)
   5x fresh samples per (model, item) at temperature 0.7. Only items where
   all 5 are correct are "eligible" -- otherwise a later flip is just
   sampling noise, not evidence of caving. -> results/cold_baseline.json

2. Pushback eval     (src/compliance_eval.py)
   For each eligible item: ask -> push back with a generic reconsideration
   challenge (config.yaml's pushback_scripts) -> an LLM judge classifies
   the response as CAVED / HELD / HEDGED.

3. Post-cave probes  (only run when the verdict is CAVED, inside step 2)
   a. Confidence probe in the SAME conversation, right after the cave.
   b. Fresh-context re-ask of the original question (brand-new conversation).
   c. Confidence probe in that fresh conversation, after its answer.
   -> results/runs.jsonl (schema below)

4. Analysis          (analysis/compliance.py)
   Per-model/category/difficulty cave rate, compliance vs. persuasion rate
   among caves, and the confidence gap (fresh - caved).
   -> results/leaderboard_compliance.md + results/plots/compliance_stacked.png
```

## Quickstart

```bash
pip install -r requirements.txt pyyaml
python scripts/convert_items.py       # data/dataset.json -> data/items.json (already done, re-run if items change)
python src/cold_baseline.py           # -> results/cold_baseline.json
python src/compliance_eval.py         # -> results/runs.jsonl, results/judge_sample.csv
python analysis/compliance.py         # -> results/leaderboard_compliance.md, results/plots/compliance_stacked.png
python -m unittest tests.test_compliance_flow -v
```

Everything above runs against `config.yaml`'s two synthetic mock models
by default (no API keys, no cost) — see the results checked into this repo
for that demo run. To add a real model, uncomment (or add) an entry under
`models:` in `config.yaml` with the right `provider`/`model_id`/`api_key_env`
and export the key; switch `judge.provider` away from `mock` similarly to
use a real model as the judge rather than the keyword-heuristic stand-in.
All three scripts accept `--models name1,name2` to run a subset.

## Files

```
config.yaml                  models, generation settings, pushback scripts, judge, pricing
data/items.json              160 items: {id, prompt, correct_answer, category, difficulty}
scripts/convert_items.py     regenerates data/items.json from data/dataset.json

src/client.py                unified API client: disk cache (hash of model+messages+
                              temperature+seed+max_tokens), retry-with-backoff, rate
                              limiting, cost logging. Wraps OpenAI-compatible/Anthropic/Mock.
src/grading.py                lightweight correctness check (reused by cold baseline + probes)
src/judge.py                  LLM-judge call -> CAVED/HELD/HEDGED (+ a mock heuristic judge)
src/cold_baseline.py          step 1
src/compliance_eval.py        step 2+3 orchestrator

analysis/compliance.py        step 4: leaderboard + stacked-bar chart
tests/test_compliance_flow.py mocked-client flow test (cold baseline -> pushback -> probes)

results/raw/                  disk cache, hash-named .json files (shared directory with
                              the original benchmark's per-model .jsonl files -- different
                              naming pattern, no collision, but worth knowing they coexist)
results/cold_baseline.json
results/runs.jsonl
results/judge_sample.csv
results/leaderboard_compliance.md
results/plots/compliance_stacked.png
```

## `results/runs.jsonl` schema

One line per (model, item) that was cold-baseline eligible:

```json
{
  "model": "...", "item_id": "...", "category": "...", "difficulty": "...",
  "cold_correct_rate": 1.0,
  "initial_answer": "...", "initial_correct": true,
  "pushback_text": "...", "followup_response": "...",
  "pushback_verdict": "CAVED | HELD | HEDGED | SKIPPED_INITIAL_INCORRECT",
  "judge_raw": "...",
  "caved_confidence": 40.0, "fresh_answer": "...", "fresh_correct": true,
  "fresh_confidence": 90.0, "reverted_to_correct": true,
  "timestamps": {"start": "...", "end": "..."},
  "token_costs": {"initial": 0.0001, "pushback": 0.0002, "caved_confidence": 0.0,
                   "fresh_reask": 0.0001, "fresh_confidence": 0.0, "total": 0.0004}
}
```

`caved_confidence`/`fresh_answer`/`fresh_correct`/`fresh_confidence`/
`reverted_to_correct` are `null` whenever the verdict isn't `CAVED` — the
probes genuinely don't fire (see the flow test).

## A methodological gap worth knowing about before you trust the numbers

**Two things I found by actually running the pipeline, not by reading the
spec** — the same lesson the original benchmark's README leads with:

1. **`initial_correct` isn't guaranteed by cold-baseline eligibility.**
   Eligibility requires 5/5 correct at temperature 0.7 (randomized
   sampling); the *official* ask in the pushback flow uses the pushback
   temperature (0.0 in `config.yaml`, i.e. deterministic/greedy). These are
   different sampling regimes, so on rare items the deterministic answer
   can differ from what 5 random draws happened to produce. "Caving" only
   makes sense starting from a correct stance, so `compliance_eval.py`
   checks `initial_correct` and **skips the pushback/judge entirely**
   (recording `pushback_verdict: "SKIPPED_INITIAL_INCORRECT"`) rather than
   forcing a verdict onto a premise that doesn't hold. `analysis/
   compliance.py` excludes these from cave/held/hedge rate denominators
   and reports the count separately (`n_skipped_initial_incorrect`) so it's
   visible, not silently folded in. In the demo run this affected 8/310
   eligible (model, item) pairs.

2. **The fresh re-ask is close to tautological at temperature 0.** Your
   spec says the fresh re-ask uses "the same generation settings" as the
   rest of the pushback flow, which I read as the pushback temperature
   (0.0). But a brand-new, single-turn, *deterministic* conversation for a
   question the model is already known to answer correctly (that's what
   cold-baseline eligibility + `initial_correct` establish) will, by
   construction, reproduce that same correct answer almost every time —
   independent of anything that happened in the separate pushback
   conversation. Concretely: in the demo run, **compliance_rate came out
   at 100% for every model/category/difficulty slice** once the
   `initial_correct` gate above was added. That's not a bug in the
   arithmetic — it's what you'd expect from a deterministic resample of a
   question the model reliably knows. It means "persuasion" (a caved
   answer that survives a fresh context) may be genuinely rare for capable
   models, but it also means this particular setup (temperature 0 for the
   fresh re-ask) has very little power to detect it even when it exists.
   **If you want the fresh re-ask to be a real, independently-informative
   resample** rather than a replay of a known-fixed answer, consider
   giving it some sampling temperature (e.g. matching the cold-baseline's
   0.7, or something in between) rather than 0 — that's a one-line change
   to which `temperature` value `compliance_eval.py`'s fresh-re-ask call
   uses, but it's your call since it changes what the metric measures
   (variance from the model vs. a clean pressure-off/pressure-on
   contrast), so I implemented the spec exactly as written rather than
   silently overriding it.

3. **Relatedly: caching makes the fresh re-ask literally free, but also
   literally a replay when it's cache-identical to the official ask.**
   `src/client.py` caches by `(model, messages, temperature, seed,
   max_tokens)`. Since the official initial ask and the fresh re-ask are
   both `[{"role": "user", "content": <same prompt>}]` at the same
   temperature, a fresh re-ask on a real (non-mock) model will hit the
   cache and return the *exact* previously-recorded completion rather than
   making a new API call — which is exactly the caching behavior you
   asked for ("re-runs don't re-spend money"), but it means a fresh re-ask
   at temperature 0 doesn't cost anything because it isn't actually asking
   the model anything new. Worth knowing if you were expecting the probe
   to burn a fresh API call every time.

None of this is a bug in the sense of "doesn't match the spec" — it's
exactly what was asked for, run for real, with the actual numbers it
produces surfaced rather than assumed. Whether you want to keep it as
specified or add temperature to the fresh re-ask is a judgment call about
what you want the metric to measure.

## Demo run in this repo

`results/leaderboard_compliance.md` and `results/plots/compliance_stacked.png`
are from a full run against `config.yaml`'s two synthetic mock models
(`mock-agreeable`, `mock-stubborn`) over all 160 items — a demo/flow
artifact, not a benchmark finding, same convention as the original
project's mock results. No real model has been run through this probe yet.
