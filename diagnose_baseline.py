import sys
import json
import os

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

import agent
import retrieval

queries = [
    "How can I check my order status?",
    "Where can I find my tracking information?",
    "What should I do if my order is delayed?",
    "My item arrived damaged. What should I do?"
]

print("BASELINE DIAGNOSIS RESULTS")
print("Provider:", os.environ.get("LLM_PROVIDER", "default"))
print()

for q in queries:
    print("=" * 80)
    print("QUERY:", q)

    # 1. Direct retrieval inspection
    ret_cases = retrieval.retrieve_similar_cases(q, top_k=3)
    print("\n--- TOP RETRIEVED CASES (retrieval.py) ---")
    for idx, c in enumerate(ret_cases, 1):
        sim = c.get("similarity", 0.0)
        cust = c.get("customer_text", "").replace("\n", " ")[:120]
        amz = c.get("amazon_text", "").replace("\n", " ")[:120]
        print(f"Case {idx} [similarity: {sim:.4f}]")
        print(f"  Customer: {cust}")
        print(f"  Amazon:   {amz}")

    # 2. Full agent pipeline execution
    print("\n--- FULL AGENT PIPELINE (agent.py) ---")
    res = agent.process_message(q)
    print("Detected Intent:    ", res.get("intent"))
    print("Should Escalate:    ", res.get("should_escalate"))
    print("Escalation Reason:  ", res.get("escalation_reason"))
    print("User-Facing Reply:  ")
    print(res.get("reply"))
    print()

