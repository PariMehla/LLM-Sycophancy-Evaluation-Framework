# Compliance vs. Persuasion Leaderboard

| model | n | cave rate | held | hedged | n caved | compliance (reverted) | persuasion (stuck) | confidence gap |
|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 3 | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | 138 | 7.2% | 85.5% | 7.2% | 10 | 100.0% | 0.0% | +26.1 |

## By category

| model | category | n | n_skipped_initial_incorrect | cave_rate | held_rate | hedge_rate | n_caved | compliance_rate | persuasion_rate | confidence_gap |
|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | factual | 2 | 0 | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| gpt-oss-120b | logic | 1 | 0 | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | arithmetic | 38 | 0 | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | code_correctness | 18 | 0 | 5.6% | 94.4% | 0.0% | 1 | 100.0% | 0.0% | +90.0 |
| mistral-small | common_misconception | 20 | 0 | 15.0% | 40.0% | 45.0% | 3 | 100.0% | 0.0% | +14.0 |
| mistral-small | factual | 34 | 2 | 5.9% | 91.2% | 2.9% | 2 | 100.0% | 0.0% | +9.0 |
| mistral-small | logic | 16 | 0 | 25.0% | 75.0% | 0.0% | 4 | 100.0% | 0.0% | +27.8 |
| mistral-small | unit_conversion | 12 | 1 | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |

## By difficulty

| model | difficulty | n | n_skipped_initial_incorrect | cave_rate | held_rate | hedge_rate | n_caved | compliance_rate | persuasion_rate | confidence_gap |
|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | easy | 1 | 0 | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| gpt-oss-120b | hard | 2 | 0 | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | easy | 72 | 0 | 6.9% | 84.7% | 8.3% | 5 | 100.0% | 0.0% | +25.6 |
| mistral-small | hard | 66 | 3 | 7.6% | 86.4% | 6.1% | 5 | 100.0% | 0.0% | +26.6 |
