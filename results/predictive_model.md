# Predictive Model: What Correlates With Caving

A logistic regression predicting `P(cave)` from `category`, `difficulty`, `model`, and which pushback *pressure_type* was used (mild / assertive / authority / consensus / emotional -- see config.yaml's pushback_scripts; one-hot encoded, first level of each dropped as baseline). Fit with `class_weight="balanced"` since caving is the rare class.

**n = 141 eligible (model, item) pairs, 10 caved (7.1%)**

**Sample-size caveat, stated plainly:** with only 10 positive examples spread across ~10 one-hot features, these coefficients are exploratory, not a validated causal claim. Read this as "what the data leans toward," not "proven driver of sycophancy" -- the confidence interval on any single coefficient here is wide. Also note `model` here is dominated by `mistral-small` (138 rows) vs. `gpt-oss-120b` (currently only 3, all HELD, once its Groq-quota-limited run finishes this will carry more signal -- see README_compliance.md).

| feature | coefficient | odds ratio |
|---|---|---|
| category_logic | +2.331 | 10.28x |
| category_common_misconception | +1.737 | 5.68x |
| category_code_correctness | +0.988 | 2.68x |
| category_factual | +0.740 | 2.10x |
| model_mistral-small | +0.342 | 1.41x |
| difficulty_hard | +0.211 | 1.23x |
| pushback_script_authority | +0.046 | 1.05x |
| category_unit_conversion | -0.818 | 0.44x |
| pushback_script_mild | -2.404 | 0.09x |

Odds ratio > 1 means that feature (relative to its dropped baseline level) is associated with *more* caving; < 1 means less. E.g. an odds ratio of 2.0 on `category_logic` means logic items are associated with roughly double the odds of a cave versus the baseline category, holding the other features fixed in this (small, exploratory) model.