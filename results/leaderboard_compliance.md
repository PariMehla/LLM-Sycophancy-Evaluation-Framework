# Compliance vs. Persuasion Leaderboard

| model | n | cave rate (95% CI) | held | hedged | n caved | compliance (reverted) | persuasion (stuck) | confidence gap |
|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 3 | 0.0% [0.0%, 0.0%] | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | 138 | 7.2% [3.6%, 11.6%] | 85.5% | 7.2% | 10 | 100.0% | 0.0% | +26.1 |

CI = 95% bootstrap percentile interval on cave_rate (2000 resamples of the eligible item set, seed 42) -- with n in the low hundreds and cave rates often in the single digits, a bare percentage overstates precision.

## Model comparison (Fisher's exact test on caved vs. not-caved)

| model A | n | caved | model B | n | caved | p-value | significant (p<0.05) |
|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 3 | 0 | mistral-small | 138 | 10 | 1.0000 | no |

## By category

| model | category | n | n_skipped_initial_incorrect | cave_rate | cave_rate_ci_low | cave_rate_ci_high | held_rate | hedge_rate | n_caved | compliance_rate | persuasion_rate | confidence_gap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | factual | 2 | 0 | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| gpt-oss-120b | logic | 1 | 0 | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | arithmetic | 38 | 0 | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | code_correctness | 18 | 0 | 5.6% | 0.0% | 16.7% | 94.4% | 0.0% | 1 | 100.0% | 0.0% | +90.0 |
| mistral-small | common_misconception | 20 | 0 | 15.0% | 0.0% | 30.0% | 40.0% | 45.0% | 3 | 100.0% | 0.0% | +14.0 |
| mistral-small | factual | 34 | 2 | 5.9% | 0.0% | 14.7% | 91.2% | 2.9% | 2 | 100.0% | 0.0% | +9.0 |
| mistral-small | logic | 16 | 0 | 25.0% | 6.2% | 43.8% | 75.0% | 0.0% | 4 | 100.0% | 0.0% | +27.8 |
| mistral-small | unit_conversion | 12 | 1 | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |

## By difficulty

| model | difficulty | n | n_skipped_initial_incorrect | cave_rate | cave_rate_ci_low | cave_rate_ci_high | held_rate | hedge_rate | n_caved | compliance_rate | persuasion_rate | confidence_gap |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | easy | 1 | 0 | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| gpt-oss-120b | hard | 2 | 0 | 0.0% | 0.0% | 0.0% | 100.0% | 0.0% | 0 | n/a | n/a | n/a |
| mistral-small | easy | 72 | 0 | 6.9% | 1.4% | 12.5% | 84.7% | 8.3% | 5 | 100.0% | 0.0% | +25.6 |
| mistral-small | hard | 66 | 3 | 7.6% | 1.5% | 15.2% | 86.4% | 6.1% | 5 | 100.0% | 0.0% | +26.6 |
