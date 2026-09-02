# Compliance vs. Persuasion Leaderboard

| model | n | cave rate | held | hedged | n caved | compliance (reverted) | persuasion (stuck) | confidence gap |
|---|---|---|---|---|---|---|---|---|
| mock-agreeable | 154 | 47.4% | 45.5% | 7.1% | 73 | 100.0% | 0.0% | +34.3 |
| mock-stubborn | 148 | 8.1% | 82.4% | 9.5% | 12 | 100.0% | 0.0% | +34.2 |

## By category

| model | category | n | n_skipped_initial_incorrect | cave_rate | held_rate | hedge_rate | n_caved | compliance_rate | persuasion_rate | confidence_gap |
|---|---|---|---|---|---|---|---|---|---|---|
| mock-agreeable | arithmetic | 36 | 3 | 38.9% | 52.8% | 8.3% | 14 | 100.0% | 0.0% | +33.1 |
| mock-agreeable | code_correctness | 20 | 0 | 60.0% | 40.0% | 0.0% | 12 | 100.0% | 0.0% | +33.3 |
| mock-agreeable | common_misconception | 20 | 0 | 30.0% | 60.0% | 10.0% | 6 | 100.0% | 0.0% | +36.0 |
| mock-agreeable | factual | 40 | 0 | 65.0% | 35.0% | 0.0% | 26 | 100.0% | 0.0% | +36.8 |
| mock-agreeable | logic | 18 | 2 | 33.3% | 44.4% | 22.2% | 6 | 100.0% | 0.0% | +27.3 |
| mock-agreeable | unit_conversion | 20 | 0 | 45.0% | 45.0% | 10.0% | 9 | 100.0% | 0.0% | +34.1 |
| mock-stubborn | arithmetic | 38 | 1 | 7.9% | 89.5% | 2.6% | 3 | 100.0% | 0.0% | +38.3 |
| mock-stubborn | code_correctness | 18 | 0 | 0.0% | 88.9% | 11.1% | 0 | n/a | n/a | n/a |
| mock-stubborn | common_misconception | 20 | 0 | 10.0% | 80.0% | 10.0% | 2 | 100.0% | 0.0% | +29.0 |
| mock-stubborn | factual | 36 | 0 | 11.1% | 72.2% | 16.7% | 4 | 100.0% | 0.0% | +33.0 |
| mock-stubborn | logic | 20 | 0 | 10.0% | 80.0% | 10.0% | 2 | 100.0% | 0.0% | +35.0 |
| mock-stubborn | unit_conversion | 16 | 2 | 6.2% | 87.5% | 6.2% | 1 | 100.0% | 0.0% | +35.0 |

## By difficulty

| model | difficulty | n | n_skipped_initial_incorrect | cave_rate | held_rate | hedge_rate | n_caved | compliance_rate | persuasion_rate | confidence_gap |
|---|---|---|---|---|---|---|---|---|---|---|
| mock-agreeable | easy | 76 | 3 | 44.7% | 47.4% | 7.9% | 34 | 100.0% | 0.0% | +34.8 |
| mock-agreeable | hard | 78 | 2 | 50.0% | 43.6% | 6.4% | 39 | 100.0% | 0.0% | +33.9 |
| mock-stubborn | easy | 79 | 1 | 11.4% | 79.7% | 8.9% | 9 | 100.0% | 0.0% | +34.6 |
| mock-stubborn | hard | 69 | 2 | 4.3% | 85.5% | 10.1% | 3 | 100.0% | 0.0% | +33.0 |
