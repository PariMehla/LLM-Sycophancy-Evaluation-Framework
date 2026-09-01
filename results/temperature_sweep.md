# Temperature Sweep: mistral-small

Does turning up sampling temperature on the official ask + pushback response make the model more susceptible to social pressure? Item set, cold-baseline eligibility, judge, and confidence-probe settings are held fixed across all rows -- only the pushback-flow temperature varies -- so any trend here isn't confounded by a different set of items being tested at each temperature.

| temperature | n eligible (initial_correct) | n skipped (initial_correct=False) | n caved | cave rate (95% CI) |
|---|---|---|---|---|
| 0.0 | 137.0 | 4.0 | 5.0 | 3.6% [0.7%, 7.3%] |
| 0.3 | 136.0 | 5.0 | 5.0 | 3.7% [0.7%, 7.4%] |
| 0.7 | 138.0 | 3.0 | 5.0 | 3.6% [0.7%, 7.2%] |
| 1.0 | 134.0 | 7.0 | 6.0 | 4.5% [1.5%, 8.2%] |

**Read:** cave rate rises from 3.6% at temperature 0.0 to 4.5% at temperature 1.0. Also watch the `n skipped` column: at higher temperature the *official ask itself* becomes less reliably correct (more sampling noise on the same question the cold baseline said it reliably knows at temperature 0.7), which shrinks the pool of items that even reach the pushback/judge step -- a real side effect of turning up temperature, not just a change in cave rate among a fixed set of items.

**Scope note:** this sweep covers Mistral Small only. A full model x temperature grid was considered and deliberately scoped down -- it would be 16x the API calls of a single run, and this project has already hit a real daily quota wall (Groq, gpt-oss-120b) running the base probe just once. Read this as "what temperature does to one real model's cave rate," not yet "whether this generalizes across models."