# Predictive Model: What Correlates With Caving

A logistic regression predicting `P(cave)` from `category`, `difficulty`, `model`, and which of the 4 canned pushback scripts was used (one-hot encoded, first level of each dropped as baseline). Fit with `class_weight="balanced"` since caving is the rare class.

**n = 141 eligible (model, item) pairs, 10 caved (7.1%)**

**Sample-size caveat, stated plainly:** with only 10 positive examples spread across ~10 one-hot features, these coefficients are exploratory, not a validated causal claim. Read this as "what the data leans toward," not "proven driver of sycophancy" -- the confidence interval on any single coefficient here is wide. Also note `model` here is dominated by `mistral-small` (138 rows) vs. `gpt-oss-120b` (currently only 3, all HELD, once its Groq-quota-limited run finishes this will carry more signal -- see README_compliance.md).

| feature | coefficient | odds ratio |
|---|---|---|
| category_logic | +2.350 | 10.49x |
| category_common_misconception | +1.752 | 5.77x |
| category_code_correctness | +0.945 | 2.57x |
| category_factual | +0.762 | 2.14x |
| model_mistral-small | +0.355 | 1.43x |
| difficulty_hard | +0.214 | 1.24x |
| pushback_script_assertive_reconsider | +0.178 | 1.19x |
| pushback_script_false_authority | +0.107 | 1.11x |
| category_unit_conversion | -0.836 | 0.43x |
| pushback_script_mild_unsure | -2.355 | 0.09x |

Odds ratio > 1 means that feature (relative to its dropped baseline level) is associated with *more* caving; < 1 means less. E.g. an odds ratio of 2.0 on `category_logic` means logic items are associated with roughly double the odds of a cave versus the baseline category, holding the other features fixed in this (small, exploratory) model.