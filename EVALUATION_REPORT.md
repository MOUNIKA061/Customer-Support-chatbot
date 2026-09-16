# Hiver Support Agent Evaluation Report

## Problem framing

The project is a prototype customer-support agent for AmazonHelp-style messages. Given a customer message, it identifies one primary support intent, retrieves similar historical conversations, decides whether a human should handle the case, and drafts a customer-facing response subject to deterministic safety checks.

The central evaluation problem is not only classification. A support agent must avoid unsafe operational claims, decide when the available context is insufficient, and be useful without pretending to access accounts, orders, payments, or current policy.

## What good means

For this prototype, a good outcome has four properties:

1. The selected intent matches the customer's main problem.
2. Escalation is requested when account access, payment verification, safety, severe fulfilment, or an unresolved case requires human action.
3. The reply is grounded in available evidence and avoids fabricated policies, actions, links, and account access.
4. The behavior is measurable on a fixed human-labelled dataset and explainable through inspectable rules.

## What was and was not built

Built:

- Ten-way primary-intent classification.
- TF-IDF retrieval over historical Amazon customer/support pairs.
- Deterministic escalation logic with explicit escalation reasons.
- LLM-based response drafting with a deterministic validator and safe fallback.
- A 200-example manually labelled golden set and scripts for baseline and full-agent evaluation.
- An LLM-as-judge script that can score reply quality criteria.

Not built:

- Live order, account, payment, or ticketing integrations.
- A current-policy knowledge base or verified operational workflow.
- A trained production classifier, dense-vector retrieval system, or multilingual model evaluation suite.
- Human-versus-LLM judge agreement data; `human_judge.csv` does not exist.

## System architecture

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

The full evaluator records the customer text, gold and predicted intent, gold and predicted escalation, escalation reason, generated reply, and retrieved cases. The evaluator also includes a majority baseline and a keyword baseline.

## Dataset and golden-set methodology

The project works from AmazonHelp conversations derived from the TWCS source data. The working retrieval implementation uses `amazon_sample_200.csv`, while the golden set contains 200 manually annotated customer messages.

Each golden-set row has one primary intent and a separate escalation decision. The annotation guide instructs annotators to select the customer's main issue rather than assign multiple intents. Escalation is separately reserved for cases requiring account/order access, payment verification, backend action, sensitive handling, insufficient evidence, repeated unresolved issues, or specialist support.

The earlier complete 50-row benchmark is imbalanced. Its distribution was:

| Intent | Rows |
|---|---:|
| delivery_issue | 16 |
| other | 11 |
| order_issue | 5 |
| product_issue | 4 |
| technical_issue | 4 |
| refund_issue | 3 |
| account_membership_issue | 2 |
| payment_billing_issue | 2 |
| return_issue | 2 |
| pricing_promotion_issue | 1 |

Delivery and `other` therefore account for 27 of 50 examples. Metrics from this sample should be interpreted with that imbalance in mind.

## Baselines

The evaluation includes two intent baselines on the same selected golden-set rows:

- **Majority baseline:** predicts the most common intent and escalation value.
- **Keyword baseline:** uses the repository's weighted keyword classifier.

For the earlier complete 50-example benchmark, the majority baseline achieved intent accuracy of 0.320 and escalation accuracy of 0.720. The keyword baseline achieved intent accuracy of 0.680. These comparisons provide context for the full agent rather than measuring response quality.

## Quantitative evaluation

### Earlier complete 50-example benchmark

| Metric | Result |
|---|---:|
| AI agent intent accuracy | 0.760 |
| AI agent intent macro F1 | 0.607 |
| AI agent intent weighted F1 | 0.759 |
| AI agent escalation accuracy | 0.520 |
| AI agent escalation precision | 1.000 |
| AI agent escalation recall | 0.333 |
| AI agent escalation F1 | 0.500 |

The complete benchmark shows that intent accuracy exceeded both the majority and keyword intent baselines, while escalation behavior was highly conservative: no false positives were observed, but recall was low.

The escalation confusion counts were:

| Gold escalation | Predicted no | Predicted yes |
|---|---:|---:|
| No | 14 | 0 |
| Yes | 24 | 12 |

### Post-fix continuation: directional evidence only

After targeted rule fixes, 23 examples were successfully evaluated before the planned 50-example rerun was interrupted by Groq provider exhaustion.

| Metric | Result |
|---|---:|
| Intent accuracy | 1.000 |
| Intent macro F1 | 1.000 |
| Intent weighted F1 | 1.000 |
| Escalation accuracy | 0.913 |
| Escalation precision | 1.000 |
| Escalation recall | 0.867 |
| Escalation F1 | 0.929 |

These 23 rows are partial, directional evidence only. They are not a replacement for the complete 50-example benchmark and should not be generalized to all 200 golden examples. `final_agent_eval_50.csv` contains only one row and is not presented as a benchmark.

### LLM-as-judge sanity test

`judge.py` supports Groq. A five-example Groq judge sanity test reported the following averages:

| Criterion | Average |
|---|---:|
| Correctness | 2.20 |
| Helpfulness | 1.80 |
| Grounding | 1.40 |
| No hallucinations | 5.00 |
| Escalation behavior | 4.00 |
| Brand tone | 3.80 |
| Overall average | 3.03 |

This is a five-example sanity check, not a reliable quality benchmark. No human-versus-LLM agreement was calculated because `human_judge.csv` is absent.

## Failure analysis with real examples

The earlier complete 50-row benchmark had 12 intent failures and 24 escalation failures. The escalation failures were all false negatives.

### 1. Escalation under-detection

Examples included a vague message, **“Amazon shipping.”**, and a Spanish refund-processing cycle where additional information was repeatedly requested. Both were gold escalations but initially predicted as non-escalations. These cases motivated targeted insufficient-evidence and repeated-unresolved rules. They were addressed locally after the partial continuation, but not validated in a completed post-fix 50-example API benchmark.

### 2. Overlapping intent categories

Tweet `820663` was labelled `account_membership_issue` but predicted `payment_billing_issue`: a closed account and gift-card transfer mention both account and payment concepts. Tweet `1252203` was labelled `payment_billing_issue` but predicted `refund_issue`: cashback, recharge, and Amazon Pay overlap with refund language.

### 3. Multilingual and context-dependent cases

Tweet `109807` is a Spanish repeated refund-processing complaint. Its meaning depends on a sequence of emails, processing failures, requests for more information, and a repeating cycle. Lexical rules and context-limited prompts are less robust on this kind of multilingual, multi-step description.

### 4. Product/order/delivery boundary ambiguity

Tweet `2718032` described paying for 22 VR headsets but receiving only one; gold was `product_issue`, while the prediction was `delivery_issue`. Tweet `1189739` concerned a cancelled pickup and was gold `return_issue` but predicted `delivery_issue`. Tweet `2220064` combined a missing delivery with a potential cancellation, producing a delivery/order boundary error.

### 5. Safe fallback can reduce helpfulness

The validator and fallback are designed to avoid fabricated actions and unsupported procedures. In the five-example judge sanity test, the no-hallucinations criterion received an average score of 5.00. This small sample is consistent with the conservative validator design, but is not sufficient to establish broad hallucination performance. Lower helpfulness (1.80) and grounding (1.40) indicate the cost: safe replies can be generic when evidence is insufficient.

## Grounding and safety behavior

Retrieved historical conversations are explicitly supporting evidence rather than authoritative current policy. The response prompt prohibits copying historical URLs, handles, identifiers, or implying access to customer data. The deterministic validator rejects URLs, social handles, fabricated account/order access, claims of completed actions, future promises, unsupported operational claims, historical identifiers, and unsupported promotion claims.

When validation fails or a reply cannot be generated, the agent returns a conservative fallback. This protects against misleading operational claims but does not provide live resolution; the system has no backend tools for orders, accounts, payments, or support tickets.

## What is misleading about my headline number?

The 1.000 intent accuracy and 0.929 escalation F1 from the post-fix continuation are easy to overread. They come from only 23 successfully evaluated examples after targeted fixes, not from a completed rerun of the 50-example benchmark or the 200-example golden set. The planned 50-example rerun stopped because the Groq provider was exhausted.

The most defensible quantitative headline is the initial complete 50-example benchmark: intent accuracy 0.760, intent macro F1 0.607, and escalation F1 0.500 on 50 examples. It also has an imbalanced label mix, with 27 of 50 messages in delivery or `other`. The five-example LLM judge result is likewise a sanity check, not a substitute for human evaluation or a broad reply-quality conclusion.

## One-more-week improvement plan

1. Complete a fresh, fixed 50-example post-fix run to measure the targeted changes without mixing stale results.
2. Add a held-out evaluation split so rules are not assessed only on examples used to discover failures.
3. Add targeted multilingual test cases and normalize text encoding before rule matching.
4. Create a compact human reply-review sheet and collect scores for correctness, helpfulness, grounding, and escalation behavior.
5. Add rule-level logging to the evaluation output so each escalation can be traced to the matching deterministic condition.
6. Review the retrieval corpus size and assess whether larger or multilingual retrieval improves grounding without treating historical replies as policy.

## Evaluation limitations

- The golden set has 200 examples, while the complete full-agent benchmark covered 50 examples.
- The evaluated 50 examples were the first selected rows of the golden set rather than a statistically sampled or held-out test split, so the benchmark should not be interpreted as an unbiased estimate of performance on the full golden set.
- The complete 50-row sample is imbalanced, especially toward delivery and `other`.
- The post-fix result is partial and interrupted, not a completed benchmark.
- The retrieval index is a small TF-IDF corpus, so it has limited semantic and multilingual coverage.
- The agent has no live account, payment, order, or policy tools; it cannot verify customer-specific facts.
- LLM judge evidence is limited to five examples and has no human agreement measurement.
- Rule-based escalation is explainable but sensitive to wording and incomplete for the long tail of support cases.
