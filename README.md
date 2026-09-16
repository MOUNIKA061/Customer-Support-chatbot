# AI Support Agent for AmazonHelp

## Problem statement

This project is a customer-support agent built from the Customer Support on Twitter (TWCS) data. AmazonHelp was selected as the target brand. For each customer message, the agent:

- classifies the primary customer intent;
- retrieves historically similar Amazon support cases;
- decides whether human escalation is required and records a reason;
- drafts a response using retrieved cases as supporting evidence; and
- validates the response before returning it.

The project is a prototype evaluation exercise, not a production support system. It has no live access to customer accounts, orders, payments, or current policy data.

## Architecture

```text
Customer message
    |
    +--> LLM intent classification --> one of 10 intents
    |
    +--> TF-IDF retrieval --> top 3 historical customer/support cases
    |
    +--> Deterministic escalation rules --> decision + reason
    |
    +--> LLM reply draft using retrieved cases as supporting evidence
    |
    +--> Deterministic validator --> accepted reply or safe fallback
```

## Intent taxonomy

- `delivery_issue`
- `order_issue`
- `refund_issue`
- `payment_billing_issue`
- `return_issue`
- `product_issue`
- `account_membership_issue`
- `technical_issue`
- `pricing_promotion_issue`
- `other`

## Dataset and golden set

The source dataset is TWCS / Customer Support on Twitter. This project filters to AmazonHelp-related data and maintains a 200-example manually labelled golden set in `golden_set.csv`.

Each golden example has separate labels for:

- one primary intent; and
- whether the message should be escalated, plus an escalation reason when applicable.

The retrieval implementation uses the representative Amazon sample in `amazon_sample_200.csv`, not the full source corpus. This keeps local experiments tractable but limits retrieval coverage.

## Setup (Windows)

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

There is currently no `requirements.txt` in this repository. Install the packages imported by the project:

```powershell
python -m pip install pandas scikit-learn requests google-genai
```

Supply API credentials through environment variables. Never put real keys in the repository, source code, or committed documentation.

The agent supports these provider settings:

```powershell
# Groq
$env:LLM_PROVIDER = 'groq'
$env:GROQ_MODEL = 'openai/gpt-oss-20b'
$env:GROQ_API_KEY = '<your-groq-api-key>'

# Gemini
$env:LLM_PROVIDER = 'gemini'
$env:GEMINI_MODEL = 'gemini-3.6-flash'
$env:GEMINI_API_KEY = '<your-gemini-api-key>'

# xAI/Grok
$env:LLM_PROVIDER = 'grok'
$env:GROK_MODEL = 'grok-4.6'
$env:XAI_API_KEY = '<your-xai-api-key>'
```

An optional fallback provider can be selected with `LLM_FALLBACK_PROVIDER`; its corresponding API key must also be present.

## Run the agent

Run one message using the actual `agent.py` CLI:

```powershell
python agent.py --msg "My package is late and has not arrived yet."
```

Run interactive mode:

```powershell
python agent.py
```

Type `exit` or `quit` to leave interactive mode.

## Evaluation

The normal evaluator loads `golden_set.csv`, runs the full agent pipeline, and records predicted intent, escalation, escalation reason, generated reply, and retrieved cases.

```powershell
python evaluate.py --limit 50 --output agent_evaluation_groq_rerun_50.csv
```

Available evaluator options:

- `--limit N`: evaluate the first `N` rows of `golden_set.csv`.
- `--output FILE`: choose the output CSV filename.
- `--resume`: skip completed `customer_tweet_id` values from the selected output file; use this only to continue an interrupted run.
- `--intent-only`: call only LLM intent classification, without retrieval, escalation, or reply generation.

For a fresh benchmark, use a new output filename and do **not** use `--resume`. The evaluator saves each successful result row immediately, so a provider quota failure can be continued later with the same output file and `--resume`.

Gemini evaluation is blocked by default unless `--allow-gemini` is explicitly supplied. The Groq environment configuration above is the supported setup for the headline evaluation workflow.

## Headline evaluation results

### Initial complete 50-example full-agent benchmark

| Metric | Result |
|---|---:|
| Intent accuracy | 0.760 |
| Intent macro F1 | 0.607 |
| Intent weighted F1 | 0.759 |
| Escalation accuracy | 0.520 |
| Escalation precision | 1.000 |
| Escalation recall | 0.333 |
| Escalation F1 | 0.500 |

Baselines on that same complete 50-example benchmark:

| Baseline metric | Result |
|---|---:|
| Majority intent accuracy | 0.320 |
| Majority escalation accuracy | 0.720 |
| Keyword intent accuracy | 0.680 |

### Later post-fix continuation — partial / directional only

Twenty-three examples were successfully evaluated before Groq provider exhaustion:

| Metric | Result |
|---|---:|
| Intent accuracy | 1.000 |
| Intent macro F1 | 1.000 |
| Escalation accuracy | 0.913 |
| Escalation F1 | 0.929 |

These 23-example results are **partial / directional evidence only**, not final performance and not a replacement for the complete 50-example benchmark.

## Important evaluation limitation

The complete 50 examples were the first selected rows of the golden set, not a statistically sampled or held-out test split. The benchmark should therefore not be interpreted as an unbiased estimate of performance on the full 200-example golden set.

## LLM-as-judge

`judge.py` supports Groq and scores correctness, helpfulness, grounding, no-hallucinations, escalation behavior, and brand tone. A five-example Groq sanity test reported:

| Criterion | Average |
|---|---:|
| correctness | 2.20 |
| helpfulness | 1.80 |
| grounding | 1.40 |
| no_hallucinations | 5.00 |
| escalation_behavior | 4.00 |
| brand_tone | 3.80 |
| overall | 3.03 |

This is only a five-example sanity check. Human-versus-LLM agreement was not calculated because `human_judge.csv` is absent.

## Grounding and safety

Historical replies are supporting evidence, not authoritative current policy. The agent does not have live account, order, or payment access.

Generated replies pass through a deterministic validator. The validator is designed to reject fabricated URLs, social handles, account access, completed actions, unsupported procedures, and unsupported operational claims. If generation or validation fails, the agent uses a conservative safe fallback. This favors hallucination resistance, but may reduce reply specificity and helpfulness when evidence is weak.

## Results files and their status

| File | Status |
|---|---|
| `agent_evaluation_groq_50.csv` | Initial complete 50-example full-agent benchmark. |
| `agent_evaluation_groq_after_escalation.csv` | 23-example post-fix continuation; partial because provider exhaustion interrupted the planned rerun. |
| `final_agent_eval_50.csv` | Contains one row only; **not** a final benchmark. |
| `final_intent_eval_50.csv` | 23-row intent-only output; incomplete relative to its filename. |
| `judge_test.csv` | Valid five-example Groq judge sanity output. |
| `judge_evaluation_after_escalation.csv` | Invalid judge attempt caused by the missing Gemini API key; not used as evidence. |
| `agent_evaluation.csv` and `agent_evaluation_groq.csv` | Earlier 20-row evaluation artifacts. |
| `classifier_evaluation.csv` | 200-row keyword-classifier evaluation artifact. |

## Documentation

- [Annotation guide](ANNOTATION_GUIDE.md): intent and escalation labelling rules.
- [Decision log](DECISION_LOG.md): engineering choices, alternatives, and tradeoffs.
- [Evaluation report](EVALUATION_REPORT.md): methodology, results, failure analysis, and limitations.

## Reproduce the headline benchmark

Configure Groq as shown in Setup, then run the full evaluator against the first 50 golden-set rows with a new output filename:

```powershell
$env:LLM_PROVIDER = 'groq'
$env:GROQ_MODEL = 'openai/gpt-oss-20b'
python evaluate.py --limit 50 --output agent_evaluation_groq_rerun_50.csv
```

The run can consume two normal LLM calls per example (intent classification and reply generation); retries can increase usage. Provider quotas can interrupt the run. Completed rows are saved immediately and can be continued intentionally with `--resume` and the same output filename.

## What is misleading about my headline number?

The post-fix values of 1.000 intent accuracy and 0.929 escalation F1 are based on only 23 successfully evaluated examples. They are not representative of all 200 golden examples and are not a completed replacement benchmark.

The most defensible quantitative headline is the initial complete 50-example benchmark. Even that sample consists of the first selected golden-set rows rather than a statistically sampled or held-out test split. The five-example LLM judge result is only a sanity check, not a broad reply-quality result.

## One-more-week plan

1. Complete a fresh fixed 50-example post-fix benchmark without mixing stale results.
2. Add a held-out evaluation split and targeted multilingual cases.
3. Add human reply review for correctness, helpfulness, grounding, and escalation behavior.
4. Add rule-level escalation logging to the evaluation output.
5. Assess larger or multilingual retrieval coverage while retaining the evidence-not-policy safety boundary.
