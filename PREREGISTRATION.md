# Preregistration: Can AI Build a Legal Staff Schedule?

**Author:** BriAnna Pischke (ORCID 0009-0003-6052-9387), Independent Researcher, San Francisco
**Template:** OSF Preregistration
**Status:** draft — finalized after the pilot, posted on OSF before the main run

## 1. Study information

**Research questions**

- RQ1. How often does an AI-built weekly staff schedule break at least one labor rule, and what would the breaks cost in premium pay?
- RQ2. How does the violation rate change with difficulty (staff count, roles, teen workers, long shifts, tight availability)?
- RQ3. For the same business, does the violation rate depend on which rule set applies (federal only, California, Seattle)?
- RQ4. When no legal schedule exists, how often does the model say so instead of returning a schedule that breaks a rule?
- RQ5. Does letting the model write and run solver code reduce violations?

**Hypotheses** (each tested exactly as written)

- H1. At least one tested model breaks a labor rule (outcome "breaks a law") in 20% or more of its schedules for scenarios where a legal schedule exists.
- H2. The share of schedules with any violation rises with difficulty level (positive trend across levels 1–5) for a majority of models.
- H3. Within the same business, the share of schedules with a labor-rule violation or premium pay is higher under California and Seattle rules than under federal rules.
- H4. On impossible scenarios, most models return a schedule more often than they answer "impossible."
- H5. In the solver condition, the share of schedules with any violation is at most half the share in the text-only condition on the same instances, for each model tested in both.

## 2. Design

- **Scenarios:** 600 fictional businesses (café, retail shop, quick-service restaurant) generated from seed 2026, 120 at each of five difficulty levels. Each business is run under 3 rule sets × 2 input formats (clean availability table; staff messages built from templates) = 3,600 instances. About 23% of businesses have a planted impossibility (the shift-lead hours required exceed what the shift leads may work).
- **Answer key:** Google OR-Tools CP-SAT decides, for each business and rule set, whether a schedule exists that breaks no rule (including the owner's instruction to avoid premium pay), and finds the lowest-cost one (5-second limit, 0.5% optimality gap).
- **Models and sample sizes (text-only condition).** Main-run instances exclude the 8 pilot businesses (592 businesses, 3,552 instances). Smaller samples are whole businesses (all 3 rule sets × 2 formats), drawn evenly across the five levels from one fixed shuffle per level, so each smaller sample is contained in every larger one:

  | Model (OpenRouter id) | Instances | Businesses |
  |---|---|---|
  | openai/gpt-oss-120b | 3,552 | 592 |
  | google/gemini-3.5-flash-lite | 3,552 | 592 |
  | meta-llama/llama-4-maverick | 3,552 | 592 |
  | openai/gpt-6-luna | 3,552 | 592 |
  | anthropic/claude-haiku-5.5 | 1,200 | 200 |
  | deepseek/deepseek-v4.1-flash | 1,200 | 200 |
  | openai/gpt-6.1-sol | 600 | 100 |
  | anthropic/claude-sonnet-5.5 | 150 | 25 |
  | anthropic/claude-opus-5.5 | 120 | 20 |

  Comparisons between models use the instances both models ran. Sample sizes were set by a fixed budget (about US$110) using per-instance costs measured in the pilot.
- **Solver condition:** openai/gpt-6-luna on the 300-instance sample (50 businesses) and google/gemini-3.5-flash-lite on the 120-instance sample (20 businesses; smaller because a test run cost about US$0.06 per instance), with a `run_python` tool (Python 3 with OR-Tools; at most 10 runs; 60 seconds each; after the 10th run the model is asked once for its final answer). Same prompt and answer format otherwise; H5 compares each model with its own text-only results on the same instances.
- **Settings:** temperature 0; each model's default reasoning; maximum output 64,000 tokens (the pilot showed that a 24,000-token cap cut off some models mid-reasoning); identical prompt for every model; rules given in the prompt; output one line per assignment between `<schedule>` tags, or `IMPOSSIBLE`. Replies cut off at the token limit count as unusable.
- **Run order and stopping:** the cheapest models run first. If spending reaches the budget before a model finishes, that model's sample is reported as run, with the shortfall stated; no instances are chosen by looking at results.
- **Blinding:** grading is automatic; no human judgment enters any outcome.

## 3. Variables

- **Outcome per schedule:** legal / breaks a law (teen-worker rules; California meal periods) / breaks a business rule (coverage, role, availability, one shift per day, max hours) / triggers premium pay (overtime, 7th-day premium, Seattle rest-gap premium) / correctly impossible / false impossible / unusable. When several apply, the first in that order (after legal) is the outcome; every violation is also recorded.
- **Premium pay owed (US$):** priced as in the rules table of the study design.
- **Cost over best:** labor cost of a legal schedule minus the solver's best legal cost.
- **Predictors:** model, difficulty level, rule set, input format, condition (text only / solver).

## 4. Analysis plan

- Violation rates per model with 95% Wilson intervals; premium pay with bootstrap intervals resampling businesses.
- RQ2: mixed-effects logistic regression of any-violation on model, level, rule set and format, with a random intercept for business.
- RQ3 and RQ5: paired McNemar tests within business (RQ3) or instance (RQ5).
- RQ4: share of impossible scenarios answered "impossible," with Wilson intervals; false-impossible rate on possible scenarios.
- Holm correction across models within each hypothesis. Analyses not listed here are reported as exploratory.

## 5. Exclusions and data handling

- API errors are retried up to 3 times; instances still failing are reported by model and are not silently dropped.
- Replies that cannot be parsed count as "unusable" (a failure), not as missing data.
- Any grader bug found after the run is fixed for every model, and listed in the paper.

## 6. Pilot

A pilot of 24 instances (8 businesses from the end of the list, half of them impossible) on all 9 models was run before this preregistration to test prompts, parsing and cost (total US$5.04). It led to three changes: the reply parser accepts a one-sentence reason after `IMPOSSIBLE` and a missing closing tag; the output cap was raised from 24,000 to 64,000 tokens; and sample sizes were set from measured cost. Pilot businesses are excluded from the main analysis.
