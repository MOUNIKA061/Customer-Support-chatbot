# Hiver Support Agent — Decision Log

This log records the material engineering choices behind the prototype. It is based on the repository implementation, annotation guide, and saved evaluation artifacts.

## 1. Use AmazonHelp as the target brand

**Decision:** Build the prototype around AmazonHelp customer-support conversations.

**Why we chose it:** The repository contains an Amazon-focused subset of the TWCS data and paired customer/support messages. A single brand gives the task a coherent support domain, including delivery, refunds, accounts, and devices.

**Alternatives considered:** A multi-brand model over the wider TWCS dataset, or an abstract brand-agnostic taxonomy.

**Tradeoff / limitation:** The resulting taxonomy and rules are Amazon-oriented. They may not transfer unchanged to another brand with different policies, terminology, or support workflows.

## 2. Build a 200-example manually labelled golden set

**Decision:** Maintain a 200-row gold dataset with one intent, an escalation decision, a reason, and optional notes.

**Why we chose it:** The annotation guide separates the primary customer problem from whether a human must act. This creates a fixed reference set for both intent and escalation evaluation.

**Alternatives considered:** Evaluate only by manually inspecting model outputs, or infer labels from historical support replies.

**Tradeoff / limitation:** Two hundred examples are useful for repeatable checks but are small relative to the source corpus; rare scenarios and language variants remain underrepresented.

## 3. Use ten mutually exclusive intents

**Decision:** Use delivery, order, refund, payment/billing, return, product, account/membership, technical, pricing/promotion, and other.

**Why we chose it:** These categories cover the recurring Amazon-support issues defined in the annotation guide while forcing the agent to select one primary customer need.

**Alternatives considered:** Multi-label classification, a larger fine-grained taxonomy, or one generic support bucket.

**Tradeoff / limitation:** Real messages can contain multiple valid problems. A single-label decision necessarily loses some secondary context and creates boundary cases such as delivery versus order or refund versus payment.

## 4. Use TF-IDF retrieval

**Decision:** Retrieve historical customer-support conversations using TF-IDF vectors and cosine similarity.

**Why we chose it:** The approach is local, transparent, inexpensive, and easy to inspect. It provides concrete historical examples without requiring a separate embedding service.

**Alternatives considered:** Dense embeddings, a hosted vector database, or no retrieval.

**Tradeoff / limitation:** Lexical similarity can miss paraphrases, multilingual equivalents, and context-dependent relationships. Similarity is useful evidence, not a policy source.

## 5. Retrieve the top three cases

**Decision:** Return the three most similar customer/support pairs for each message.

**Why we chose it:** Three cases provide more than one precedent while keeping the prompt and later analysis manageable.

**Alternatives considered:** One nearest neighbor, a larger top-k value, or similarity-threshold filtering only.

**Tradeoff / limitation:** Three results can still be irrelevant or redundant. More results would increase context size and may introduce conflicting or stale historical advice.

## 6. Use an LLM for intent classification

**Decision:** Classify the primary intent with the configured LLM in the full agent pipeline.

**Why we chose it:** Natural-language classification handles broader phrasing than the keyword baseline and returns one taxonomy-constrained label.

**Alternatives considered:** Use the keyword classifier as the production classifier, train a conventional supervised model, or use retrieval-only classification.

**Tradeoff / limitation:** LLM classification consumes quota and can be inconsistent on ambiguous or multilingual messages. The keyword classifier remains valuable as a local baseline and diagnostic tool.

## 7. Use deterministic escalation rules

**Decision:** Keep escalation outside the LLM and implement it as explicit rules in `decide_escalation()`.

**Why we chose it:** Escalation affects operational safety. Explicit rules make the decision inspectable and allow targeted handling for account access, payment verification, repeated unresolved cases, safety issues, and severe fulfilment.

**Alternatives considered:** Ask the LLM to predict escalation, or always escalate uncertain cases.

**Tradeoff / limitation:** Rules require maintenance and can miss wording variants. Conservative rules initially produced false negatives in the 50-example benchmark.

## 8. Treat historical replies as evidence, not current policy

**Decision:** Supply retrieved replies as supporting context but explicitly prohibit treating them as authoritative current policy.

**Why we chose it:** Historical social-support replies may include old procedures, URLs, handles, or account-specific details. The agent should not present those as verified current instructions.

**Alternatives considered:** Copy the nearest historical reply, or treat retrieved content as an authoritative knowledge base.

**Tradeoff / limitation:** This constraint reduces the specificity of replies and can make them less helpful when the evidence is weak.

## 9. Add a grounding validator

**Decision:** Validate generated replies deterministically after generation.

**Why we chose it:** The validator rejects URLs, social handles, account-access claims, performed actions, future promises, historical identifiers, unsupported procedures, and risky promotion claims.

**Alternatives considered:** Prompt-only safety instructions, or no post-generation validation.

**Tradeoff / limitation:** Pattern checks are not a complete semantic verifier. They may reject a useful response or miss a harmful phrasing not represented by a rule.

## 10. Use a safe fallback after validation failure

**Decision:** Return a conservative fallback response when the LLM output fails validation or reply generation fails.

**Why we chose it:** A safe, bounded response is preferable to exposing an unsupported claim, fabricated action, or copied historical identifier.

**Alternatives considered:** Retry generation indefinitely, return the rejected response, or return no reply.

**Tradeoff / limitation:** The fallback is deliberately generic. It improves hallucination resistance but may be less helpful or less tailored than a grounded response.

## 11. Use a representative subsample instead of the full source corpus

**Decision:** Build the working support-pair data and retrieval index from a small Amazon sample rather than process the full roughly three-million-tweet source dataset during iteration.

**Why we chose it:** The repository's workflow includes sampling and an `amazon_sample_200.csv` retrieval corpus, which keeps experiments and inspections tractable.

**Alternatives considered:** Process the full TWCS corpus, or use a much larger Amazon-only dataset at every iteration.

**Tradeoff / limitation:** A small retrieval corpus limits coverage and can make similar-case evidence sparse or unrepresentative.

## 12. Evaluate with majority and keyword baselines against a fixed golden set

**Decision:** Report majority-class and keyword baselines alongside the AI agent on the same labelled data.

**Why we chose it:** The baselines establish whether the full agent provides value beyond simple class-frequency and lexical approaches. A fixed golden set makes runs comparable over time.

**Alternatives considered:** Report only LLM results, compare against informal examples, or change examples between runs.

**Tradeoff / limitation:** Baselines do not measure reply quality, and a fixed 200-example set can be overused during iteration. Results should be interpreted as prototype evaluation evidence rather than a deployment claim.
