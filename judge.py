import pandas as pd
import json
import os
import argparse
import time
import requests
from google import genai

# Initialize Gemini only when a key is available. The runtime check in
# run_judge keeps missing credentials from producing zero-score results.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
client = None

if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
    try:
        client = genai.Client()
    except Exception:
        client = None

MODEL_ID = "gemini-3.6-flash"

def evaluate_reply_llm(customer_msg, generated_reply, retrieved_history):
    """
    Uses LLM as a judge to evaluate a generated reply on a 1-5 scale across 6 criteria.
    """
    if LLM_PROVIDER == "gemini" and not client:
        return {"error": "API client not initialized"}
        
    prompt = f"""
You are an expert customer support manager evaluating an AI agent's reply.
Rate the generated reply on a scale of 1 to 5 for each of the following criteria (5 is best, 1 is worst).

CRITERIA:
1. Correctness: Does it correctly address the customer's intent?
2. Helpfulness: Is the resolution actually helpful to the customer?
3. Grounding: Is it grounded in the retrieved historical evidence?
4. No Hallucinations: Does it avoid inventing policies, unsupported claims, or claiming to have accessed account info?
5. Appropriate escalation behavior: If it requires escalation, does it gracefully direct the user to support instead of just saying "I can't help"?
6. Brand Tone: Is the tone appropriate for Amazon support?

Customer Message:
{customer_msg}

Retrieved Historical Evidence:
{retrieved_history}

Generated Reply to Evaluate:
{generated_reply}

Return ONLY a JSON object with this exact structure:
{{
    "correctness": <int>,
    "helpfulness": <int>,
    "grounding": <int>,
    "no_hallucinations": <int>,
    "escalation_behavior": <int>,
    "brand_tone": <int>,
    "explanation": "<short 1-2 sentence explanation of the scores>"
}}
"""
    for attempt in range(5):
        try:
            if LLM_PROVIDER == "groq":
                response = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=60,
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"Groq API Error {response.status_code}: {response.text}"
                    )

                data = json.loads(response.json()["choices"][0]["message"]["content"])

            else:
                if not client:
                    return {"error": "API client not initialized"}

                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
                data = json.loads(response.text)
            # Ensure it has all keys
            for key in ["correctness", "helpfulness", "grounding", "no_hallucinations", "escalation_behavior", "brand_tone"]:
                if key not in data:
                    data[key] = 1
            data['total_score'] = sum([data[k] for k in ["correctness", "helpfulness", "grounding", "no_hallucinations", "escalation_behavior", "brand_tone"]])
            data['average_score'] = data['total_score'] / 6.0
            return data
        except Exception as e:
            if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e) or '503' in str(e):
                print(f"Rate limited or unavailable. Retrying in 15 seconds... (Attempt {attempt+1}/5)")
                time.sleep(15)
            else:
                print(f"Error calling judge LLM: {e}")
                return {}
    return {}

def run_judge(input_file="agent_evaluation.csv", output_file="judge_evaluation.csv", sample_size=None):
    if LLM_PROVIDER == "groq" and not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY is not set. Cannot run LLM judge.")
        raise SystemExit(1)

    if LLM_PROVIDER == "gemini" and not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is not set. Cannot run LLM judge.")
        raise SystemExit(1)

    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found. Run evaluate.py first.")
        return
        
    df = pd.read_csv(input_file)
    if sample_size:
        df = df.head(sample_size)
        
    results = []
    print(f"Judging {len(df)} examples...")
    
    for i, row in df.iterrows():
        judge_res = evaluate_reply_llm(row['customer_text'], row['generated_reply'], row.get('retrieved_cases', '[]'))
        
        result_row = row.to_dict()
        result_row.update({
            "judge_correctness": judge_res.get("correctness", 0),
            "judge_helpfulness": judge_res.get("helpfulness", 0),
            "judge_grounding": judge_res.get("grounding", 0),
            "judge_no_hallucinations": judge_res.get("no_hallucinations", 0),
            "judge_escalation_behavior": judge_res.get("escalation_behavior", 0),
            "judge_brand_tone": judge_res.get("brand_tone", 0),
            "judge_total_score": judge_res.get("total_score", 0),
            "judge_average_score": judge_res.get("average_score", 0),
            "judge_explanation": judge_res.get("explanation", "")
        })
        results.append(result_row)
        
        if (i+1) % 5 == 0:
            print(f"Judged {i+1}/{len(df)}")
            
    out_df = pd.DataFrame(results)
    out_df.to_csv(output_file, index=False)
    print(f"\nSaved judge results to {output_file}")
    
    # Print average scores
    print("\n" + "="*50)
    print("AVERAGE JUDGE SCORES")
    print("="*50)
    for key in ["judge_correctness", "judge_helpfulness", "judge_grounding", "judge_no_hallucinations", "judge_escalation_behavior", "judge_brand_tone", "judge_average_score"]:
        print(f"{key}: {out_df[key].mean():.2f}")

def calculate_human_agreement(judge_file="judge_evaluation.csv", human_file="human_judge.csv"):
    if not os.path.exists(judge_file) or not os.path.exists(human_file):
        print("Missing judge_evaluation.csv or human_judge.csv for agreement calculation.")
        return
        
    judge_df = pd.read_csv(judge_file)
    human_df = pd.read_csv(human_file)
    
    merged = pd.merge(judge_df, human_df, on="customer_tweet_id")
    if len(merged) == 0:
        print("No matching tweet IDs between LLM judge and human judge.")
        return
        
    print(f"\nCalculating agreement on {len(merged)} examples...")
    
    # We use Pearson correlation for ordinal/numeric scores
    metrics = [
        ("judge_helpfulness", "human_helpfulness_score"),
        ("judge_correctness", "human_correctness_score"),
        ("judge_grounding", "human_grounding_score"),
        ("judge_escalation_behavior", "human_escalation_score")
    ]
    
    for judge_col, human_col in metrics:
        if judge_col in merged.columns and human_col in merged.columns:
            correlation = merged[judge_col].corr(merged[human_col], method='pearson')
            print(f"Pearson correlation for {judge_col} vs {human_col}: {correlation:.3f}")
        else:
            print(f"Missing columns for {judge_col} vs {human_col}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, help="Run judge on a subset of examples")
    parser.add_argument("--agreement", action="store_true", help="Calculate human agreement")
    parser.add_argument(
        "--input",
        default="agent_evaluation.csv",
        help="Evaluation CSV to judge",
    )
    parser.add_argument(
        "--output",
        default="judge_evaluation.csv",
        help="CSV file for judge results",
    )
    args = parser.parse_args()
    
    if args.agreement:
        calculate_human_agreement(judge_file=args.output)
    else:
        run_judge(
            input_file=args.input,
            output_file=args.output,
            sample_size=args.sample,
        )
