
import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support
)

import classifier
import agent

import json
import os
import argparse


# ============================================================
# CONFIGURATION
# ============================================================

GOLDEN_FILE = "golden_set.csv"
OUTPUT_FILE = "agent_evaluation.csv"


# ============================================================
# MAJORITY BASELINE
# ============================================================

def evaluate_baseline_majority(df):
    """
    Majority class baseline for:
    - intent
    - escalation
    """

    majority_intent = df["gold_intent"].mode()[0]
    majority_escalate = df["should_escalate"].mode()[0]

    preds_intent = [majority_intent] * len(df)
    preds_escalate = [majority_escalate] * len(df)

    intent_acc = accuracy_score(
        df["gold_intent"],
        preds_intent
    )

    esc_acc = accuracy_score(
        df["should_escalate"].astype(bool),
        preds_escalate
    )

    print(
        f"Majority Baseline Intent Accuracy: "
        f"{intent_acc:.3f}"
    )

    print(
        f"Majority Baseline Escalation Accuracy: "
        f"{esc_acc:.3f}"
    )


# ============================================================
# KEYWORD BASELINE
# ============================================================

def evaluate_baseline_keyword(df):
    """
    Existing keyword/rule-based classifier baseline.
    """

    preds_intent = [
        classifier.classify_intent(text)[0]
        for text in df["customer_text"]
    ]

    intent_acc = accuracy_score(
        df["gold_intent"],
        preds_intent
    )

    print(
        f"Keyword Baseline Intent Accuracy: "
        f"{intent_acc:.3f}"
    )


# ============================================================
# CHECK PROVIDER
# ============================================================

def check_provider():

    provider = os.environ.get(
        "LLM_PROVIDER",
        "gemini"
    ).lower()

    print()
    print("=" * 60)
    print("LLM CONFIGURATION")
    print("=" * 60)
    print(f"Provider: {provider}")

    if provider == "groq":
        model = os.environ.get(
            "GROQ_MODEL",
            "openai/gpt-oss-20b"
        )
        print(f"Groq Model: {model}")

    elif provider == "gemini":
        model = os.environ.get(
            "GEMINI_MODEL",
            "gemini-3.6-flash"
        )
        print(f"Gemini Model: {model}")

    elif provider == "grok":
        model = os.environ.get(
            "GROK_MODEL",
            "grok-4.6"
        )
        print(f"xAI/Grok Model: {model}")

    else:
        print(
            f"ERROR: Unknown provider '{provider}'."
        )
        raise SystemExit(1)

    fallback = os.environ.get(
        "LLM_FALLBACK_PROVIDER",
        ""
    ).lower()

    print(
        f"Fallback Provider: "
        f"{fallback if fallback else 'None'}"
    )

    print("=" * 60)

    return provider


# ============================================================
# LOAD EXISTING RESULTS
# ============================================================

def load_existing_results():

    if not os.path.exists(OUTPUT_FILE):
        return pd.DataFrame()

    try:

        existing = pd.read_csv(
            OUTPUT_FILE
        )

        if "customer_tweet_id" not in existing.columns:
            print(
                "WARNING: Existing evaluation file does "
                "not contain customer_tweet_id."
            )
            return pd.DataFrame()

        print(
            f"Existing evaluation results found: "
            f"{len(existing)} rows."
        )

        return existing

    except Exception as e:

        print(
            f"WARNING: Could not read existing "
            f"{OUTPUT_FILE}: {e}"
        )

        return pd.DataFrame()


# ============================================================
# ONE FULL AGENT EXAMPLE
# ============================================================

def evaluate_one_full(row):

    """
    Run the complete agent pipeline.

    Expected LLM usage:
        2 calls per example
        1 = intent classification
        1 = reply generation
    """

    result = agent.process_message(
        row["customer_text"]
    )

    return {
        "customer_tweet_id": row["customer_tweet_id"],
        "customer_text": row["customer_text"],
        "gold_intent": row["gold_intent"],
        "predicted_intent": result["intent"],
        "gold_should_escalate": row["should_escalate"],
        "predicted_should_escalate": result[
            "should_escalate"
        ],
        "predicted_escalation_reason": result[
            "escalation_reason"
        ],
        "generated_reply": result["reply"],
        "retrieved_cases": json.dumps(
            result["retrieved_cases"],
            ensure_ascii=False
        )
    }


# ============================================================
# INTENT-ONLY EVALUATION
# ============================================================

def evaluate_intent_only(df):

    """
    Evaluate only LLM intent classification.

    This uses approximately:
        1 LLM call per example

    It does NOT generate replies.
    """

    results = []

    print()
    print("=" * 60)
    print("INTENT-ONLY EVALUATION")
    print("=" * 60)

    print(
        f"Examples: {len(df)}"
    )

    print(
        f"Estimated normal LLM calls: {len(df)}"
    )

    print()

    for position, (_, row) in enumerate(
        df.iterrows(),
        start=1
    ):

        print(
            f"Processing {position}/{len(df)}..."
        )

        try:

            intent_data = (
                agent.classify_intent_llm(
                    row["customer_text"]
                )
            )

            results.append({
                "customer_tweet_id":
                    row["customer_tweet_id"],

                "customer_text":
                    row["customer_text"],

                "gold_intent":
                    row["gold_intent"],

                "predicted_intent":
                    intent_data.get(
                        "intent",
                        "other"
                    )
            })

        except Exception as e:

            print()
            print(
                "ERROR while processing example."
            )
            print(
                f"Tweet ID: "
                f"{row['customer_tweet_id']}"
            )
            print(
                f"Error: {e}"
            )

            print()
            print(
                "Stopping evaluation to avoid "
                "repeated API usage."
            )

            break

    if not results:
        print(
            "No intent results were generated."
        )
        return

    out_df = pd.DataFrame(results)

    # Intent-only runs still need a durable per-example artifact for
    # later failure analysis; OUTPUT_FILE honors the existing --output.
    out_df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    intent_acc = accuracy_score(
        out_df["gold_intent"],
        out_df["predicted_intent"]
    )

    _, _, intent_f1_macro, _ = (
        precision_recall_fscore_support(
            out_df["gold_intent"],
            out_df["predicted_intent"],
            average="macro",
            zero_division=0
        )
    )

    _, _, intent_f1_weighted, _ = (
        precision_recall_fscore_support(
            out_df["gold_intent"],
            out_df["predicted_intent"],
            average="weighted",
            zero_division=0
        )
    )

    print()
    print("=" * 60)
    print("INTENT-ONLY RESULTS")
    print("=" * 60)

    print(
        f"Examples evaluated: {len(out_df)}"
    )

    print(
        f"Intent Accuracy:     {intent_acc:.3f}"
    )

    print(
        f"Intent Macro F1:     {intent_f1_macro:.3f}"
    )

    print(
        f"Intent Weighted F1:  {intent_f1_weighted:.3f}"
    )

    print("=" * 60)

    print(
        f"Detailed intent predictions saved to "
        f"{OUTPUT_FILE}"
    )


# ============================================================
# FULL AGENT EVALUATION
# ============================================================

def evaluate_agent(
    df,
    resume=False
):

    """
    Run the complete AI agent evaluation.

    Normal API usage:
        2 LLM calls per example.

    Results are saved after EVERY successful example.
    """

    print()
    print("=" * 60)
    print("FULL AI AGENT EVALUATION")
    print("=" * 60)

    print(
        f"Examples requested: {len(df)}"
    )

    print(
        f"Estimated normal LLM calls: "
        f"{len(df) * 2}"
    )

    print(
        "Important: retries can increase API usage."
    )

    print("=" * 60)

    # --------------------------------------------------------
    # Load existing results if resume is enabled.
    # --------------------------------------------------------

    existing = pd.DataFrame()

    if resume:
        existing = load_existing_results()

    completed_ids = set()

    if not existing.empty:

        completed_ids = set(
            existing[
                "customer_tweet_id"
            ].astype(str)
        )

        print(
            f"Already completed: "
            f"{len(completed_ids)} examples."
        )

    results = []

    # --------------------------------------------------------
    # Process examples.
    # --------------------------------------------------------

    processed_this_run = 0

    for position, (_, row) in enumerate(
        df.iterrows(),
        start=1
    ):

        tweet_id = str(
            row["customer_tweet_id"]
        )

        # ----------------------------------------------------
        # Skip completed examples.
        # ----------------------------------------------------

        if resume and tweet_id in completed_ids:

            print(
                f"[{position}/{len(df)}] "
                f"Skipping already completed "
                f"{tweet_id}"
            )

            continue

        print()
        print(
            f"[{position}/{len(df)}] "
            f"Processing Tweet ID: {tweet_id}"
        )

        try:

            result = evaluate_one_full(
                row
            )

            results.append(result)

            processed_this_run += 1

            # ------------------------------------------------
            # Save immediately.
            # ------------------------------------------------

            new_df = pd.DataFrame(
                [result]
            )

            file_exists = os.path.exists(OUTPUT_FILE)
            is_empty = not file_exists or os.path.getsize(OUTPUT_FILE) == 0

            if is_empty:
                new_df.to_csv(
                    OUTPUT_FILE,
                    mode="a",
                    header=True,
                    index=False
                )
            else:
                new_df.to_csv(
                    OUTPUT_FILE,
                    mode="a",
                    header=False,
                    index=False
                )

            print(
                f"Saved result "
                f"({processed_this_run} this run)."
            )

        except KeyboardInterrupt:

            print()
            print(
                "Evaluation interrupted by user."
            )

            print(
                "Already completed results "
                "have been saved."
            )

            print(
                "Run again with --resume "
                "to continue."
            )

            break

        except Exception as e:

            print()
            print(
                "ERROR while processing example."
            )

            print(
                f"Tweet ID: {tweet_id}"
            )

            print(
                f"Error: {e}"
            )

            print()
            print(
                "Stopping evaluation to avoid "
                "unnecessary API usage."
            )

            print(
                "Already completed results "
                "have been saved."
            )

            print(
                "You can run again with "
                "--resume."
            )

            break

    # --------------------------------------------------------
    # Read complete output file.
    # --------------------------------------------------------

    if not os.path.exists(OUTPUT_FILE):

        print(
            "No evaluation output was created."
        )

        return

    out_df = pd.read_csv(
        OUTPUT_FILE
    )

    # --------------------------------------------------------
    # Remove accidental duplicate IDs.
    # --------------------------------------------------------

    if "customer_tweet_id" in out_df.columns:

        before = len(out_df)

        out_df = out_df.drop_duplicates(
            subset=["customer_tweet_id"],
            keep="last"
        )

        after = len(out_df)

        if after != before:

            out_df.to_csv(
                OUTPUT_FILE,
                index=False
            )

            print(
                f"Removed "
                f"{before - after} duplicate rows."
            )

    # --------------------------------------------------------
    # Metrics.
    # --------------------------------------------------------

    if len(out_df) == 0:
        print(
            "No rows available for metrics."
        )
        return

    # Intent metrics.

    intent_acc = accuracy_score(
        out_df["gold_intent"],
        out_df["predicted_intent"]
    )

    _, _, intent_f1_macro, _ = (
        precision_recall_fscore_support(
            out_df["gold_intent"],
            out_df["predicted_intent"],
            average="macro",
            zero_division=0
        )
    )

    _, _, intent_f1_weighted, _ = (
        precision_recall_fscore_support(
            out_df["gold_intent"],
            out_df["predicted_intent"],
            average="weighted",
            zero_division=0
        )
    )

    # Escalation metrics.

    gold_esc = (
        out_df["gold_should_escalate"]
        .astype(bool)
    )

    pred_esc = (
        out_df["predicted_should_escalate"]
        .astype(bool)
    )

    esc_acc = accuracy_score(
        gold_esc,
        pred_esc
    )

    esc_p, esc_r, esc_f1, _ = (
        precision_recall_fscore_support(
            gold_esc,
            pred_esc,
            average="binary",
            zero_division=0
        )
    )

    # --------------------------------------------------------
    # Print final metrics.
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("AGENT EVALUATION RESULTS")
    print("=" * 60)

    print(
        f"Examples evaluated: {len(out_df)}"
    )

    print(
        f"Intent Accuracy:      {intent_acc:.3f}"
    )

    print(
        f"Intent Macro F1:      {intent_f1_macro:.3f}"
    )

    print(
        f"Intent Weighted F1:   {intent_f1_weighted:.3f}"
    )

    print(
        f"Escalation Accuracy:  {esc_acc:.3f}"
    )

    print(
        f"Escalation Precision: {esc_p:.3f}"
    )

    print(
        f"Escalation Recall:    {esc_r:.3f}"
    )

    print(
        f"Escalation F1:        {esc_f1:.3f}"
    )

    print("=" * 60)

    print()
    print(
        f"Detailed predictions saved to "
        f"{OUTPUT_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the AI Customer Support Agent "
            "safely with quota-aware controls."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Number of examples to evaluate. "
            "Example: --limit 5"
        )
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume from existing "
            "agent_evaluation.csv results."
        )
    )

    parser.add_argument(
        "--intent-only",
        action="store_true",
        help=(
            "Evaluate only LLM intent classification. "
            "Uses approximately 1 LLM call/example."
        )
    )

    parser.add_argument(
        "--allow-gemini",
        action="store_true",
        help=(
            "Allow evaluation with Gemini. "
            "Use only when intentionally testing Gemini."
        )
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help=(
            "Override the default output evaluation file. "
            "Example: --output agent_evaluation_groq.csv"
        )
    )

    args = parser.parse_args()

    if args.output:
        OUTPUT_FILE = args.output

    # --------------------------------------------------------
    # Provider safety check.
    # --------------------------------------------------------

    provider = check_provider()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Gemini is free-tier and quota-limited.
    #
    # Do not accidentally run evaluation against Gemini.
    # --------------------------------------------------------

    if (
        provider == "gemini"
        and not args.allow_gemini
    ):

        print()
        print(
            "SAFETY STOP:"
        )

        print(
            "LLM_PROVIDER is currently set to "
            "'gemini'."
        )

        print(
            "Gemini free-tier evaluation is "
            "blocked by default."
        )

        print()
        print(
            "For evaluation, use:"
        )

        print(
            "  set LLM_PROVIDER=groq"
        )

        print(
            "  python evaluate.py --limit 5"
        )

        print()
        print(
            "If you intentionally want Gemini, "
            "use --allow-gemini."
        )

        raise SystemExit(1)

    # --------------------------------------------------------
    # Load golden dataset.
    # --------------------------------------------------------

    if not os.path.exists(GOLDEN_FILE):

        print(
            f"Error: {GOLDEN_FILE} not found."
        )

        raise SystemExit(1)

    df = pd.read_csv(
        GOLDEN_FILE
    )

    print()
    print("=" * 60)
    print("GOLDEN SET")
    print("=" * 60)

    print(
        f"Total examples available: {len(df)}"
    )

    # --------------------------------------------------------
    # Apply limit.
    # --------------------------------------------------------

    if args.limit is not None:

        if args.limit <= 0:

            print(
                "Error: --limit must be greater than 0."
            )

            raise SystemExit(1)

        df = df.head(
            args.limit
        )

        print(
            f"Examples selected: {len(df)}"
        )

    else:

        print(
            f"Examples selected: {len(df)}"
        )

    print("=" * 60)

    # --------------------------------------------------------
    # Baselines.
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("BASELINES")
    print("=" * 60)

    evaluate_baseline_majority(
        df
    )

    evaluate_baseline_keyword(
        df
    )

    # --------------------------------------------------------
    # Intent-only mode.
    # --------------------------------------------------------

    if args.intent_only:

        evaluate_intent_only(
            df
        )

    # --------------------------------------------------------
    # Full agent evaluation.
    # --------------------------------------------------------

    else:

        evaluate_agent(
            df,
            resume=args.resume
        )
