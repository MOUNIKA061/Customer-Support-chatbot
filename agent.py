
import os
import sys
import json
import argparse
import time
import re
import importlib

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Load optional third-party HTTP support dynamically so static analysis does
# not require the package to be installed in every development environment.
requests = importlib.import_module("requests")

# Load the optional Google GenAI SDK dynamically so static analysis does not
# require the package to be installed in every development environment.
genai = importlib.import_module("google.genai")
types = importlib.import_module("google.genai.types")

# pyrefly: ignore [missing-import]
import retrieval


# ============================================================
# CONFIGURATION
# ============================================================

# Supported providers:
#   gemini
#   groq
#   grok
#
# Gemini is the default.
#
# For Groq:
#   set LLM_PROVIDER=groq
#   set GROQ_MODEL=openai/gpt-oss-20b
#
# For Gemini:
#   set LLM_PROVIDER=gemini

LLM_PROVIDER = os.environ.get(
    "LLM_PROVIDER",
    "gemini"
).lower()

LLM_FALLBACK_PROVIDER = os.environ.get(
    "LLM_FALLBACK_PROVIDER",
    ""
).lower()

# Current working Groq model.
GROQ_MODEL = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

# Gemini model.
GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)

# xAI/Grok model.
GROK_MODEL = os.environ.get(
    "GROK_MODEL",
    "grok-4.6"
)


# ============================================================
# API KEY VALIDATION
# ============================================================

client = None


def get_current_provider():
    return os.environ.get("LLM_PROVIDER", "gemini").lower()


def get_fallback_provider():
    return os.environ.get("LLM_FALLBACK_PROVIDER", "").lower()


def validate_api_keys(exit_on_error=False):
    """
    Validate that required API keys are configured.
    When exit_on_error is True (CLI mode), exits with sys.exit(1).
    When False (web backend mode), returns (success, error_message).
    """
    global client
    provider = get_current_provider()
    fallback = get_fallback_provider()

    def check_one(p, is_fallback=False):
        if not p:
            return True, ""
        label = "fallback provider" if is_fallback else f"provider '{p}'"
        if p == "gemini":
            if not os.environ.get("GEMINI_API_KEY"):
                return False, f"GEMINI_API_KEY environment variable is not set for {label}."
        elif p == "groq":
            if not os.environ.get("GROQ_API_KEY"):
                return False, f"GROQ_API_KEY environment variable is not set for {label}."
        elif p == "grok":
            if not os.environ.get("XAI_API_KEY"):
                return False, f"XAI_API_KEY environment variable is not set for {label}."
        else:
            return False, f"Unknown LLM_PROVIDER '{p}'. Use 'gemini', 'groq', or 'grok'."
        return True, ""

    ok, err = check_one(provider, False)
    if not ok:
        if exit_on_error:
            print(f"ERROR: {err}")
            sys.exit(1)
        return False, err

    if fallback:
        ok_fb, err_fb = check_one(fallback, True)
        if not ok_fb:
            if exit_on_error:
                print(f"ERROR: {err_fb}")
                sys.exit(1)
            return False, err_fb

    if (provider == "gemini" or fallback == "gemini") and os.environ.get("GEMINI_API_KEY"):
        if client is None:
            try:
                client = genai.Client()
            except Exception as e:
                print(f"WARNING: Gemini client initialization failed: {e}")
                client = None

    return True, ""


# Initial check on module load (does not hard exit so web server can import cleanly)
_keys_ok, _ = validate_api_keys(exit_on_error=False)


# ============================================================
# INTENT TAXONOMY
# ============================================================

INTENTS = [
    "delivery_issue",
    "order_issue",
    "refund_issue",
    "payment_billing_issue",
    "return_issue",
    "product_issue",
    "account_membership_issue",
    "technical_issue",
    "pricing_promotion_issue",
    "other"
]


# ============================================================
# RETRY / BACKOFF
# ============================================================

def exponential_backoff(attempt):
    """
    Calculate retry delay.

    attempt 0 -> 5 seconds
    attempt 1 -> 10 seconds
    attempt 2 -> 20 seconds
    etc.
    """

    return (2 ** attempt) * 5


# ============================================================
# SINGLE LLM API CALL
# ============================================================

def call_llm_single_attempt(
    prompt,
    is_json=False,
    provider=None
):
    """
    Make one API call to the selected provider.
    """

    if provider == "gemini":

        if client is None:

            raise RuntimeError(
                "Gemini client is not initialized."
            )

        config = types.GenerateContentConfig()

        if is_json:

            config.response_mime_type = (
                "application/json"
            )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config
        )

        return response.text.strip()


    elif provider == "groq":

        url = (
            "https://api.groq.com/openai/v1/"
            "chat/completions"
        )

        headers = {
            "Authorization": (
                f"Bearer "
                f"{os.environ.get('GROQ_API_KEY')}"
            ),
            "Content-Type": "application/json"
        }

        data = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2
        }

        if is_json:

            data["response_format"] = {
                "type": "json_object"
            }

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code != 200:

            raise RuntimeError(
                "Groq API Error "
                f"{response.status_code}: "
                f"{response.text}"
            )

        return (
            response.json()
            ["choices"][0]
            ["message"]["content"]
            .strip()
        )


    elif provider == "grok":

        url = (
            "https://api.x.ai/v1/"
            "chat/completions"
        )

        headers = {
            "Authorization": (
                f"Bearer "
                f"{os.environ.get('XAI_API_KEY')}"
            ),
            "Content-Type": "application/json"
        }

        data = {
            "model": GROK_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2
        }

        if is_json:

            data["response_format"] = {
                "type": "json_object"
            }

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code != 200:

            raise RuntimeError(
                "xAI API Error "
                f"{response.status_code}: "
                f"{response.text}"
            )

        return (
            response.json()
            ["choices"][0]
            ["message"]["content"]
            .strip()
        )


    else:

        raise ValueError(
            f"Unknown provider: {provider}"
        )


# ============================================================
# GENERAL LLM CALL WITH RETRIES
# ============================================================

def call_llm(prompt, is_json=False):
    """
    Call the configured LLM provider.

    Retries temporary failures.

    An explicitly configured fallback provider can be used
    if the primary provider fails.
    """

    ok, err = validate_api_keys(exit_on_error=False)
    if not ok:
        raise RuntimeError(err)

    max_retries = 5

    providers_to_try = [
        LLM_PROVIDER
    ]

    if (
        LLM_FALLBACK_PROVIDER
        and LLM_FALLBACK_PROVIDER != LLM_PROVIDER
    ):

        providers_to_try.append(
            LLM_FALLBACK_PROVIDER
        )

    for provider in providers_to_try:

        for attempt in range(max_retries):

            try:

                text = call_llm_single_attempt(
                    prompt,
                    is_json,
                    provider
                )

                if is_json:

                    # Validate JSON before accepting it.
                    json.loads(text)

                return text


            except json.JSONDecodeError:

                print(
                    f"[{provider}] Malformed JSON. "
                    f"Retrying "
                    f"({attempt + 1}/{max_retries})..."
                )


            except Exception as e:

                error_text = str(e).upper()

                temporary_error = (
                    "429" in error_text
                    or "RESOURCE_EXHAUSTED"
                    in error_text
                    or "503" in error_text
                    or "UNAVAILABLE" in error_text
                    or "TIMEOUT" in error_text
                )

                if temporary_error:

                    delay = exponential_backoff(
                        attempt
                    )

                    print(
                        f"[{provider}] Temporary API "
                        f"failure. Retrying in "
                        f"{delay} seconds "
                        f"({attempt + 1}/{max_retries})..."
                    )

                    time.sleep(delay)

                else:

                    print(
                        f"[{provider}] API error: {e}"
                    )

                    break


        print(
            f"[{provider}] Provider exhausted."
        )


    raise RuntimeError(
        "All configured LLM providers failed."
    )


# ============================================================
# INTENT CLASSIFICATION
# ============================================================

def classify_intent_llm(customer_msg):
    """
    Classify the customer message into exactly one
    of the ten predefined intents.
    """

    prompt = f"""

You are a customer-support intent classification system.

Classify the following customer message into exactly ONE
of these intents:

{json.dumps(INTENTS, indent=2)}

Definitions:

- delivery_issue:
  shipping, tracking, late delivery, lost package

- order_issue:
  cancel order, change order, cannot place order,
  or general order problems

- refund_issue:
  missing refund, refund not received, money back

- payment_billing_issue:
  payment failed, unexpected charge, duplicate charge,
  billing problem, Amazon Pay

- return_issue:
  how to return, return label, return request,
  return pickup problem

- product_issue:
  damaged, defective, wrong item, counterfeit product

- account_membership_issue:
  login problem, account access, Prime membership

- technical_issue:
  app crash, website error, technical problem,
  Prime Video, Kindle technical problems

- pricing_promotion_issue:
  price, discount, coupon, promotion, deal

- other:
  greetings, praise, unrelated messages, or anything
  that does not fit another category

Return ONLY valid JSON:

{{
    "intent": "<one exact intent>",
    "reasoning": "<one short sentence>"
}}

Customer Message:

{customer_msg}

"""

    text = call_llm(
        prompt,
        is_json=True
    )

    data = json.loads(text)

    if data.get("intent") not in INTENTS:

        data["intent"] = "other"

    if not data.get("reasoning"):

        data["reasoning"] = (
            "Classified from the customer message."
        )

    return data


# ============================================================
# RETRIEVAL
# ============================================================

def retrieve_history(customer_msg):
    """
    Reuse the existing retrieval.py system.

    Returns the top 3 similar historical Amazon
    customer-support conversations.
    """

    try:

        return retrieval.retrieve_similar_cases(
            customer_msg,
            top_k=3
        )

    except Exception as e:

        print(
            f"Retrieval error: {e}"
        )

        return []


# ============================================================
# DETERMINISTIC ESCALATION
# ============================================================

def decide_escalation(
    customer_msg,
    intent,
    history
):
    """
    Deterministic escalation logic.

    The LLM does NOT decide escalation.
    """

    message = str(
        customer_msg
    ).lower()


    # --------------------------------------------------------
    # 1. Sensitive issues
    # --------------------------------------------------------

    sensitive_patterns = [
        r"\bsue\b", r"\blawsuit\b", r"\bpolice\b", r"\bscam\b",
        r"\bfraud\b", r"\bstolen\b", r"\blawyer\b",
        r"\blegal action\b", r"\breport to police\b", r"\bidentity theft\b"
    ]

    if any(re.search(p, message) for p in sensitive_patterns):
        return True, "sensitive_issue"


    # A topic-only message provides too little context for an automated
    # response. Restrict this to messages containing nothing beyond the
    # named service so ordinary delivery questions remain non-escalated.
    insufficient_evidence_patterns = [
        r"^\s*(?:amazon\s+)?(?:shipping|delivery|support|customer service)\s*[.!?]*\s*$"
    ]

    if any(re.search(p, message) for p in insufficient_evidence_patterns):
        return True, "insufficient_evidence"


    # --------------------------------------------------------
    # 2. Repeated unresolved problems
    # --------------------------------------------------------

    repeated_patterns = [
        r"\bstill waiting\b", r"\bcalled before\b",
        r"\bspoke with\b", r"\bno one helped\b", r"\bmissed again\b",
        r"\balready contacted\b", r"\bcontacted before\b",
        r"\bstill not\b", r"\bstill hasn't\b", r"\bstill have not\b",
        r"\balready contacted support\b", r"\bcontacted support before\b",
        r"\btalked to support\b", r"\bspoke to an agent\b",
        r"\bnobody helped\b", r"\bno help\b", r"\bprevious attempt\b",
        r"\btried before\b", r"\bmultiple times\b", r"\bseveral times\b",
        # Unresolved investigation
        r"\binvestigation\b.*\bdays ago\b", r"\binvestigation\b.*\bstill\b",
        r"\binvestigated\b.*\bstill\b", r"\binvestigation\b.*\bno resolution\b",
        r"\binvestigation\b.*\bnot resolved\b", r"\bcontacted\b.*\bstill\b",
        r"\bprevious investigation\b", r"\bpromised investigation\b.*\bno resolution\b",
        # Duplicate order still unresolved
        r"\bduplicate order\b.*\bstill\b", r"\bduplicated order\b.*\bstill\b",
        r"\bduplicate order\b.*\bunresolved\b", r"\bduplicate order\b.*\bnot resolved\b",
        r"\bduplicate order\b.*\bshowing\b", r"\bduplicated order\b.*\bshowing\b",
        r"\bduplicate order\b.*\bremains\b", r"\bduplicate order\b.*\bstill there\b"
    ]

    if any(re.search(p, message) for p in repeated_patterns):
        return True, "repeated_unresolved_issue"

    # Spanish refund language combined with a processing failure or a
    # request for additional information indicates a repeated refund
    # workflow that needs verification rather than a general question.
    spanish_repeated_refund_patterns = [
        r"\b(?:reembolsos?|reembolsado|reembolsar|devoluci[oó]n(?:es)?\s+de\s+dinero)\b.*"
        r"\b(?:no\s+se\s+pudo\s+procesar|no\s+procesado|rechazad[oa]?|fall[oó]|error|"
        r"informaci[oó]n\s+adicional)\b",
        r"\b(?:no\s+se\s+pudo\s+procesar|no\s+procesado|rechazad[oa]?|fall[oó]|error|"
        r"informaci[oó]n\s+adicional)\b.*"
        r"\b(?:reembolsos?|reembolsado|reembolsar|devoluci[oó]n(?:es)?\s+de\s+dinero)\b"
    ]

    if any(re.search(p, message) for p in spanish_repeated_refund_patterns):
        return True, "repeated_unresolved_issue"

    # Contextual 'again' check
    if re.search(r"\bagain\b", message):
        unresolved_context = [
            r"\bfailed\b", r"\bmissed\b", r"\bcancelled\b", r"\bcanceled\b",
            r"\bdelayed\b", r"\bcharged\b", r"\bbroken\b", r"\bdamaged\b",
            r"\bwrong\b", r"\bmissing\b", r"\blate\b", r"\bnot working\b",
            r"\berror\b", r"\bissue\b", r"\bproblem\b"
        ]
        if any(re.search(p, message) for p in unresolved_context):
            return True, "repeated_unresolved_issue"


    # --------------------------------------------------------
    # 2a. Failed support interaction / prolonged unresolved status
    # --------------------------------------------------------
    # These rules require an explicit prior-support failure, a concrete
    # prolonged fulfilment problem, or a clear request to resolve details
    # already supplied. They do not escalate ordinary complaints or anger.

    failed_support_patterns = [
        r"\b(?:contacted|called|emailed|sent emails?|spoke (?:with|to))\b.*"
        r"\b(?:no avail|no help|nobody (?:helped|is helping)|not resolved|unresolved)\b",
        r"\b(?:no avail|no help|nobody (?:helped|is helping)|not resolved|unresolved)\b.*"
        r"\b(?:contacted|called|emailed|sent emails?|spoke (?:with|to))\b",
        r"\b(?:required|requested) details\b.*\b(?:already )?(?:shared|provided|sent)\b.*"
        r"\b(?:resolve|urgent|asap)\b",
        r"\b(?:shared|provided|sent)\b.*\b(?:required|requested) details\b.*"
        r"\b(?:resolve|urgent|asap)\b",
        r"\b(?:wasn't|was not)\b.*\b(?:actually )?help(?:ing)?\b",
        r"\bnot actually help(?:ing)?\b",
        r"\bappearance of helping\b",
        r"\beverything (?:is|was) cancel(?:led|ed)\b",
        r"\binvestigation\b.*\b(?:\d+\s+(?:days?|hours?)\s+ago|been\s+\d+\s+days?)\b",
        r"\b(?:refunds?|order|delivery|return|shipment|package)\b.*"
        r"\b(?:been\s+(?:a\s+)?month|for\s+(?:days?|weeks?|months?))\b",
        r"\b(?:been\s+(?:a\s+)?month|for\s+(?:days?|weeks?|months?))\b.*"
        r"\b(?:refunds?|order|delivery|return|shipment|package)\b",
        r"\b(?:promised|supposed)\b.*\b(?:refund|resolve|delivery|return)\b.*\b(?:but|yet|still|no)\b",
        r"\b(?:refund|resolve|delivery|return)\b.*\b(?:promised|supposed)\b.*\b(?:but|yet|still|no)\b",
        r"\b(?:cannot|can't|can not) understand\b.*\b(?:cause|reason)\b.*\bdelay\b"
    ]

    if any(re.search(p, message) for p in failed_support_patterns):
        return True, "repeated_unresolved_issue"


    # --------------------------------------------------------
    # 2b. Serious delivery safety / severe fulfilment
    # --------------------------------------------------------
    # Safety hazards and an order where most paid quantities are missing
    # require human intervention even when no account lookup is requested.

    delivery_safety_patterns = [
        r"\bfire safety\b",
        r"\b(?:package|parcel|delivery)\b.*\bunattended\b",
        r"\bunattended\b.*\b(?:package|parcel|delivery)\b",
        r"\bunsafe delivery\b"
    ]

    if any(re.search(p, message) for p in delivery_safety_patterns):
        return True, "specialist_support_required"

    severe_fulfilment_patterns = [
        r"\b(?:paid for|ordered)\b.*\b(?:\d+|multiple|several)\b.*"
        r"\bonly\s+\d+\b.*\b(?:delivered|received)\b",
        r"\b(?:lost|missing)\b.*\b(?:no|aren't|not)\b.*\boptions?\b",
        r"\boptions?\b.*\b(?:aren't|not)\b.*\b(?:lost|missing)\b"
    ]

    if any(re.search(p, message) for p in severe_fulfilment_patterns):
        return True, "order_access_required"


    # --------------------------------------------------------
    # 3. Account access
    # --------------------------------------------------------

    if intent == "account_membership_issue":

        account_patterns = [
            r"\bforgot password\b", r"\bpassword problem\b", r"\blogin problem\b",
            r"\bcan't access\b", r"\bcannot access\b", r"\blocked account\b",
            r"\bhacked account\b", r"\bclosed account\b", r"\baccount was closed\b",
            r"\baccount you closed\b", r"\byou closed my account\b", 
            r"\baccount got closed\b", r"\baccount has been closed\b",
            r"\baccount suspended\b", r"\baccount disabled\b", r"\baccount locked\b",
            r"\bmissing funds\b", r"\bmissing balance\b", r"\bgift card missing\b", 
            r"\bgift card balance missing\b", r"\bgift card not showing\b",
            r"\bmembership charged incorrectly\b", r"\bmembership cancellation problem\b"
        ]

        if any(re.search(p, message) for p in account_patterns):
            return True, "account_access_required"


    # --------------------------------------------------------
    # 4. Payment / refund verification
    # --------------------------------------------------------

    if intent in [
        "payment_billing_issue",
        "refund_issue"
    ]:

        payment_patterns = [
            r"\bcharged twice\b", r"\bdouble charged\b", r"\bwrong charge\b",
            r"\bwrong amount\b", r"\bunauthorized charge\b", r"\bdon't recognize charge\b",
            r"\brefund missing\b", r"\brefund not received\b", r"\brefund failed\b",
            r"\brefund rejected\b", r"\brefund reversed\b", r"\bwrong refund\b",
            r"\bincorrect refund\b", r"\bwrong item refunded\b", r"\brefunded the wrong item\b",
            r"\brefund for the wrong item\b", r"\brefunded me for the wrong item\b",
            r"\bpartial refund\b", r"\bcashback missing\b",
            r"\bcashback not received\b",
            r"\bhaven['’]?t got (?:the )?cashback\b",
            r"\bhave not received (?:the )?cashback\b",
            r"\bdidn['’]?t get (?:the )?cashback\b",
            r"\bdid not get (?:the )?cashback\b",
            r"\brecharge cashback missing\b",
            r"\brecharge not credited\b",
            r"\bpayment failed\b", r"\bpayment declined\b", r"\brecharge problem\b",
            r"\bbilling problem\b"
        ]

        if any(re.search(p, message) for p in payment_patterns):
            return True, "payment_verification_required"


    # --------------------------------------------------------
    # 5. Order access & Explicit lookup
    # --------------------------------------------------------

    if intent in [
        "order_issue",
        "delivery_issue",
        "return_issue",
        "product_issue",
        "pricing_promotion_issue"
    ]:

        # Routine how-to informational inquiries should not automatically escalate.
        # Examples: "How can I check my order status?", "Where can I find my tracking information?",
        # "How do I track an order?", "How can I return an item?", "What is your return policy?"
        is_routine_howto = bool(re.search(
            r"^\s*(?:how\s+(?:can|do)\s+i\s+|where\s+(?:can|do)\s+i\s+|what\s+should\s+i\s+do\s+if\s+|how\s+to\s+|what\s+is\s+the\s+way\s+to\s+)"
            r"(?:check|find|view|track|see|locate|return)\s+"
            r"(?:my\s+)?(?:order\s+status|tracking(?:\s+info(?:rmation)?)?|package(?:\s+status)?|shipment(?:\s+status)?|an?\s+item|a\s+return)\b",
            message
        ))

        # Explicit order ID lookups require backend access
        explicit_id_patterns = [
            r"\border\s*(?:no\.?|number|#)\s*[:#]?\s*\d+",
            r"\b(?:find|check|look\s*up|inspect)\s+order\s*#?\s*\d+",
            r"\b4\d{2}-\d{7}-\d{7}\b"
        ]

        if any(re.search(p, message) for p in explicit_id_patterns):
            return True, "order_access_required"

        order_problem_patterns = [
            r"\border no\.?\b", r"\border number\b", r"\border\s?#\b",
            r"\bfind my order\b", r"\blook up my order\b",
            r"\border details\b", r"\bdetails of order\b",
            r"\bnever arrived\b", r"\bdidn't arrive\b",
            r"\bdid not arrive\b", r"\bmissing items?\b", r"\bmissing packages?\b",
            r"\bmissing parcels?\b", r"\bmissing products?\b",
            r"\blost parcels?\b", r"\blost packages?\b",
            r"\bwrong item\b", r"\bincorrect item\b", r"\bdamaged item\b",
            r"\bdamaged product\b", r"\bitem arrived damaged\b",
            r"\border cancelled\b", r"\border canceled\b", r"\bcannot cancel\b",
            r"\bcan't cancel\b",
            r"\bcan['’]?t cancel\b",
            r"\bcannot be cancelled\b",
            r"\bcan['’]?t be cancelled\b",
            r"\bcannot be canceled\b",
            r"\bcan['’]?t be canceled\b",
            r"\bwon['’]?t allow (?:the )?order to be cancelled\b",
            r"\bwon['’]?t allow (?:the )?order to be canceled\b",
            r"\bwon['’]?t let me cancel\b",
            r"\bunable to cancel\b",
            r"\bcancellation is blocked\b",
            r"\bcancellation problem\b", r"\bwrong console\b",
            r"\b(?:pickup|return)\b.*\bcancel(?:led|ed)\b",
            r"\b(?:new|replacement)\s+(?:cord|part|accessory)\b",
            r"\b(?:reorder|order again)\b.*\b(?:not paying|won['â€™]?t pay|will not pay)\b.*"
            r"\b(?:delivery|shipping)\b",
            r"\bwrong item received\b", r"\bdelivery date changed\b",
            r"\bguaranteed delivery\b", r"\bmissed delivery\b", r"\bdelivery failed\b",
            r"\bout for delivery\b", r"\banother parcel lost\b",
            r"\bmissed\b.*\b(?:assembly|service|pickup|appointment)\b",
            r"\bscheduled\b.*\b(?:assembly|service|pickup|appointment)\b"
        ]

        if not is_routine_howto:
            if any(re.search(p, message) for p in order_problem_patterns):
                return True, "order_access_required"
        else:
            # Even if phrased with how-to, explicit damage or loss reports require escalation
            loss_or_damage_patterns = [
                r"\bdamaged\b", r"\bbroken\b", r"\bdefective\b", r"\blost\b",
                r"\bnever arrived\b", r"\bstolen\b", r"\bwrong item\b"
            ]
            if any(re.search(p, message) for p in loss_or_damage_patterns):
                return True, "order_access_required"


    # --------------------------------------------------------
    # 6. Default
    # --------------------------------------------------------

    return False, ""


# ============================================================
# REPLY VALIDATOR
# ============================================================

def validate_reply(
    reply,
    customer_msg,
    intent,
    history,
    escalation_info
):
    """
    Deterministic post-generation safety validator.

    Rejects:

    - URLs
    - social handles
    - fake account access
    - fake actions
    - future promises
    - unsupported operational procedures
    - unsupported pricing/promotion claims
    - historical identifiers
    """

    if not reply:

        return {
            "valid": False,
            "reason": "empty_reply"
        }


    # Normalize curly apostrophes.
    text = (
        str(reply)
        .replace("’", "'")
        .replace("‘", "'")
    )

    lower = text.lower()


    # --------------------------------------------------------
    # 1. URLs
    # --------------------------------------------------------

    url_patterns = [
        r"https?://",
        r"www\.",
        r"amzn\.to/",
        r"t\.co/",
        r"bit\.ly/"
    ]

    for pattern in url_patterns:

        if re.search(
            pattern,
            lower
        ):

            return {
                "valid": False,
                "reason": "contains_url"
            }


    # --------------------------------------------------------
    # 2. Social-media handles
    # --------------------------------------------------------

    if re.search(
        r"@[A-Za-z0-9_]+",
        text
    ):

        return {
            "valid": False,
            "reason": "contains_handle"
        }


    # --------------------------------------------------------
    # 3. Account / order access claims
    # --------------------------------------------------------

    # Disallow the assistant claiming that IT (or an agent) accessed, viewed, pulled,
    # or looked up the customer's account or order details.
    account_access_patterns = [
        r"\b(?:i|we|my system|the assistant)\s+(?:can|will|have|am|'ll|'ve)?\s*(?:check(?:ed)?|access(?:ed)?|look(?:ed)?\s+into|verif(?:y|ied)|inspect(?:ed)?|view(?:ed)?|pull(?:ed)?)\s+(?:your|the)\s+(?:account|order|tracking|password|identity)\b",
        r"\b(?:i|we)\s+(?:can\s+)?see\s+(?:your\s+)?account\b",
        r"\b(?:dm|send|share)\s+(?:us|me)\s+(?:your\s+)?(?:order|account|password)\b",
        r"\bpull(?:ed)?\s+(?:it\s+)?from\s+your\s+account\b",
        r"\blooked\s+up\s+your\s+(?:order|account)\b"
    ]

    for pattern in account_access_patterns:

        if re.search(
            pattern,
            lower
        ):

            return {
                "valid": False,
                "reason": "unsupported_account_access"
            }


    # --------------------------------------------------------
    # 4. Claims of actions performed
    # --------------------------------------------------------

    action_patterns = [

        r"\bi[' ]?m\s+"
        r"(checking|verifying|contacting|escalating|forwarding|"
        r"investigating|scheduling|arranging|flagging|connecting)\b",

        r"\bi(?:'ve|\s+have)?\s+"
        r"(checked|verified|contacted|escalated|forwarded|"
        r"connected|investigated|scheduled|arranged|flagged)\b",

        r"\bi[' ]?ll\s+"
        r"(check|verify|contact|escalate|forward|connect|"
        r"investigate|schedule|arrange|flag)\b",

        r"\bescalated this\b",

        r"\bforwarded this\b",

        r"\bcontacted our support\b",

        r"\bnotified the support\b",

        r"\barranged a new pickup\b",

        r"\bcreated a support ticket\b",

        r"\ba ticket has been created\b",

        r"\bconnected you to (?:an? )?agent\b",

        r"\btransferred you to (?:an? )?agent\b",

        r"\bopened a case\b"
    ]

    for pattern in action_patterns:

        if re.search(
            pattern,
            lower
        ):

            return {
                "valid": False,
                "reason": "unsupported_action"
            }


    # --------------------------------------------------------
    # 5. Future promises
    # --------------------------------------------------------

    future_patterns = [

        r"\b(?:we|they)[' ]?ll\s+"
        r"(?:look|investigate|help|get back|contact|reach out|"
        r"resolve|assist)\b",

        r"\b(?:we|they)\s+will\s+"
        r"(?:look|investigate|help|get back|contact|reach out|"
        r"resolve|assist)\b",

        r"\bsomeone\s+will\s+(?:contact|reach out)\b",

        r"\ba\s+support\s+agent\s+needs\s+to\s+verify\b",

        r"\ba\s+support\s+(?:agent|specialist|team)\s+will\b",

        r"\bour\s+team\s+will\b",

        r"\b(?:i|we)\s+will\s+"
        r"(?:check|verify|contact|escalate|forward|connect|"
        r"investigate|schedule|arrange|flag|help you)\b",

        r"\bi[' ]?ll\s+(?:help you)\b",

        r"\bpass this on to\b",

        r"\b(?:we|they|i|our team)\s+(?:will|'ll)\s+(?:look into it|investigate)\b",

        r"\b(?:we|they|i|our team)\s+(?:will|'ll)\s+resolve\s+the\s+issue\b"
    ]

    for pattern in future_patterns:

        if re.search(
            pattern,
            lower
        ):

            return {
                "valid": False,
                "reason": "unsupported_future_action"
            }


    # --------------------------------------------------------
    # 6. Retrieval similarity
    # --------------------------------------------------------

    max_similarity = max(
        [
            case.get(
                "similarity",
                0
            )
            for case in history
        ],
        default=0
    )


    # --------------------------------------------------------
    # 7. PRICING / PROMOTION VALIDATION
    # --------------------------------------------------------
    #
    # IMPORTANT:
    #
    # This check is intentionally OUTSIDE the
    # max_similarity <= 0.30 block.
    #
    # A high TF-IDF similarity does NOT prove that
    # the historical case contains current pricing
    # or promotion policy.
    #
    # Therefore pricing/promotion claims require
    # explicit validation regardless of similarity.
    #

    if intent == "pricing_promotion_issue":

        promotion_patterns = [

            # Current availability / policy claims
            r"\bwe\s+(?:run|offer|have|provide)\s+"
            r"(?:discounts?|promotions?|deals?|offers?)\b",

            r"\b(?:we|amazon)\s+"
            r"(?:run|offer|have|provide)\s+"
            r"(?:discounts?|promotions?|deals?|offers?)\b",

            r"\bcurrent\s+(?:discounts?|promotions?|offers?|deals?)\b",

            r"\blatest\s+(?:discounts?|promotions?|offers?|deals?)\b",

            r"\bavailable\s+(?:discounts?|promotions?|offers?|deals?)\b",

            r"\b(?:discounts?|promotions?|deals?|offers?)\s+"
            r"(?:are|is)\s+(?:available|running|active)\b",

            # Deals / coupon claims
            r"\bcheck\s+(?:the\s+)?deals?\s+(?:section|page)\b",

            r"\b(?:deals?\s+page|deals?\s+section)\b",

            r"\bcheck\s+(?:for\s+)?(?:current|latest)\s+offers?\b",

            r"\bcheck\s+(?:for\s+)?(?:available\s+)?coupons?\b",

            r"\bcoupons?\s+(?:are|is)\s+(?:available|active)\b",

            # Savings claims
            r"\b(?:current|latest|available|relevant)\s+savings\b",

            r"\bexclusive\s+savings\b",

            r"\bprime\s+savings\b",

            r"\bprime\s+benefits\b",

            r"\bfree\s+shipping\s+benefits?\b",

            r"\bearly\s+access\b",

            # Offers applying to products/items
            r"\boffers?\s+that\s+apply\b",

            r"\boffers?\s+available\s+for\s+(?:your|my)\s+"
            r"(?:items?|products?|order)\b",

            # Assistant claims that it can find/check savings
            r"\bi\s+can\s+(?:help\s+you\s+)?"
            r"(?:find|check|locate|identify)\s+"
            r"(?:any\s+)?(?:current|latest|available|relevant)?\s*"
            r"(?:discounts?|promotions?|offers?|deals?|savings)\b",

            r"\bi\s+can\s+help\s+you\s+find\s+"
            r"(?:any\s+)?(?:relevant|current|latest|available)?\s*"
            r"(?:savings|discounts?|offers?|deals?)\b",

            # Email signup as a claimed source of current discounts
            r"\bsign\s+up\s+for\s+(?:email|emails|email\s+updates)\b"
            r".{0,100}\b(?:discounts?|promotions?|offers?|deals?|savings)\b",

            # General claim of regular promotions
            r"\b(?:we|amazon)\s+"
            r"(?:run|have|offer|provide)\s+"
            r"(?:regular|frequent|various|a\s+variety\s+of)\s+"
            r"(?:discounts?|promotions?|deals?|offers?)\b",

            r"\ba\s+variety\s+of\s+"
            r"(?:discounts?|promotions?|deals?|offers?)\b",

            r"\bvariety\s+of\s+"
            r"(?:discounts?|promotions?|deals?|offers?)\b",

            r"\boffers?\s+a\s+variety\s+of\b"
        ]

        for pattern in promotion_patterns:

            if re.search(
                pattern,
                lower
            ):

                return {
                    "valid": False,
                    "reason": "unsupported_promotion_claim"
                }


    # --------------------------------------------------------
    # 8. Operational / procedural claims
    # --------------------------------------------------------

    # These claims are unsafe when retrieval evidence
    # is weak.

    if max_similarity < 0.15:

        operational_patterns = [

            r"\breturn or replace\b",

            r"\bprint a prepaid\b",

            r"\bprepaid return label\b",

            r"\bprepaid label\b",

            r"\bshipping label\b",

            r"\bpayment methods\b",

            r"\bcredit card\b",

            r"\bdebit card\b",

            r"\bamazon pay\b",

            r"\bgift card\b",

            r"\bbusiness days\b",

            r"\barrive tomorrow\b",

            r"\barrive by tomorrow\b",

            r"\brefund will arrive\b",

            r"\brefund should arrive\b",

            r"\bdelivery will arrive\b",

            r"\beligible for a prepaid\b",

            r"\bhelp & settings\b",

            r"\bdeals page\b",

            r"\bprime benefits\b",

            r"\bvariety of discounts\b",

            r"\boffers a variety\b"
        ]

        for pattern in operational_patterns:

            if re.search(
                pattern,
                lower
            ):

                return {
                    "valid": False,
                    "reason": "unsupported_operational_claim"
                }


    # --------------------------------------------------------
    # 9. Historical identifiers
    # --------------------------------------------------------

    historical_identifier_patterns = [

        r"\bt\.co\b",

        r"\bamzn\.to\b"
    ]

    for pattern in historical_identifier_patterns:

        if re.search(
            pattern,
            lower
        ):

            return {
                "valid": False,
                "reason": "historical_identifier"
            }


    # --------------------------------------------------------
    # Passed validation
    # --------------------------------------------------------

    return {
        "valid": True,
        "reason": ""
    }


# ============================================================
# SAFE FALLBACK
# ============================================================

def safe_fallback(
    customer_msg,
    intent,
    history,
    escalation_info
):
    """
    Conservative response used when the LLM response
    fails validation.
    """

    should_escalate, escalation_reason = (
        escalation_info
    )


    # Distinct, calm escalation follow-up notice
    escalation_notice = ""
    if should_escalate:
        escalation_notice = (
            "\n\nIf these steps don't resolve it, the support team may need to "
            "follow up. I can't connect you to an agent or create a ticket here."
        )


    # --------------------------------------------------------
    # Pricing / promotion fallback
    # --------------------------------------------------------
    if intent == "pricing_promotion_issue":
        return (
            "I don't have access to real-time promotion policies. To verify promotional pricing:\n"
            "1. Review the product detail page for active coupons or promotion terms.\n"
            "2. Check the promotional terms and expiration date.\n"
            "3. Review the order summary at checkout to ensure discounts are applied."
            + escalation_notice
        )

    # --------------------------------------------------------
    # Order / Delivery guidance fallback
    # --------------------------------------------------------
    if intent in ["order_issue", "delivery_issue"]:
        return (
            "Here is how you can check and track your order:\n"
            "1. Sign in to your account and go to \"Your Orders\".\n"
            "2. Locate the order and select \"Track Package\" to review the carrier details and estimated delivery date.\n"
            "3. Check your registered email for any delay updates or carrier notifications.\n"
            "4. If tracking shows no updates past your estimated delivery date, select \"Problem with order\" in your account."
            + escalation_notice
        )

    # --------------------------------------------------------
    # Return / Product guidance fallback
    # --------------------------------------------------------
    if intent in ["return_issue", "product_issue"]:
        return (
            "Here is how to proceed with a return or defective item:\n"
            "1. Sign in to your account and navigate to \"Your Orders\".\n"
            "2. Locate the item and select \"Return or Replace Items\".\n"
            "3. Select the reason that best describes the issue and choose your preferred resolution.\n"
            "4. Follow the on-screen instructions to obtain a return shipping label or drop-off instructions."
            + escalation_notice
        )

    # --------------------------------------------------------
    # Account / Membership guidance fallback
    # --------------------------------------------------------
    if intent == "account_membership_issue":
        return (
            "Here is how to manage your account or membership:\n"
            "1. If you are having trouble logging in, use the \"Forgot Password\" link on the sign-in page.\n"
            "2. Check your registered email for password reset instructions.\n"
            "3. For Prime membership inquiries, visit \"Your Account\" and select \"Prime Membership\"."
            + escalation_notice
        )

    # --------------------------------------------------------
    # General / insufficient evidence fallback
    # --------------------------------------------------------
    return (
        "I don't have enough verified information in our records to provide specific step-by-step instructions for that request. "
        "Please check the official Customer Service or Help page in your account for direct assistance."
        + escalation_notice
    )


# ============================================================
# REPLY GENERATION
# ============================================================

def generate_reply(
    customer_msg,
    intent,
    history,
    escalation_info
):
    """
    Generate a concise support response.

    Historical conversations are supporting evidence only.
    They are not treated as current policy.
    """

    should_escalate, escalation_reason = (
        escalation_info
    )

    # Explicit evidence quality check
    evidence_ok, max_sim, quality_reason = retrieval.check_evidence_quality(
        customer_msg,
        history,
        threshold=0.20
    )


    # --------------------------------------------------------
    # Build retrieval context.
    # --------------------------------------------------------

    if history:

        history_context = (
            "Historical Similar Support Conversations "
            "(SUPPORTING EVIDENCE ONLY):\n"
        )

        for case in history:

            similarity = case.get(
                "similarity",
                0.0
            )

            customer_text = case.get(
                "customer_text",
                ""
            )

            amazon_text = case.get(
                "amazon_text",
                ""
            )

            history_context += (
                f"- Similarity: {similarity:.3f}\n"
            )

            history_context += (
                f"- Past Customer: {customer_text}\n"
            )

            history_context += (
                f"- Past Amazon Reply: {amazon_text}\n\n"
            )

    else:

        history_context = (
            "No historical conversations retrieved."
        )


    # --------------------------------------------------------
    # Prompt.
    # --------------------------------------------------------

    prompt = f"""You are an AI customer-support assistant providing clear, practical guidance.

Customer Message:
{customer_msg}

Detected Intent:
{intent}

Evidence Quality Assessment:
{quality_reason} (max similarity: {max_sim:.3f})

Human Escalation Recommended:
{should_escalate}
Escalation Reason:
{escalation_reason}

{history_context}

RESPONSE INSTRUCTIONS:

1. DIRECT ANSWER & ACTIONABLE GUIDANCE FIRST:
   - Answer the customer's question directly in the opening sentence.
   - If useful self-service steps exist for the topic, give clear, numbered steps:
     1. Where to go (e.g. go to "Your Orders" or check your confirmation email).
     2. What to select (e.g. locate the specific item or select "Track Package").
     3. What information to verify (e.g. carrier tracking updates, estimated delivery date).
     4. What next step to take if the first action does not resolve the issue.
   - Avoid vague filler phrases such as "Please check the options available for your order or account."

2. EVIDENCE-BASED GUIDANCE & INSUFFICIENT EVIDENCE:
   - Base your steps on standard self-service procedures supported by the retrieved cases.
   - If the available evidence does NOT contain information to answer the question (for example: unsupported services like booking flights, cryptocurrency/Bitcoin payments, or topics outside our records), do NOT invent policies or instructions. State clearly:
     "I don't have enough verified information in our records to provide specific steps for that. Please check our official Customer Service or Help pages for assistance."

3. SEPARATION OF GUIDANCE FROM ESCALATION:
   - Always provide the helpful self-service steps first whenever possible.
   - If Human Escalation Recommended is True, append this exact calm notice at the very end:
     "If these steps don't resolve it, the support team may need to follow up. I can't connect you to an agent or create a ticket here."
   - If Human Escalation Recommended is False, do NOT include any escalation notice.
   - NEVER say "A support agent is verifying your details," "A support agent needs to verify the details and assist with this issue," "I've escalated this," or "A ticket has been created."

4. CRITICAL SAFETY BOUNDARIES:
   - NEVER claim that you or an agent accessed the customer's account, checked their live order, or verified their details.
   - NEVER claim that you scheduled, arranged, refunded, or performed any backend action.
   - Do NOT include any URLs, links, or Twitter handles (@username).
   - Keep the tone polite, professional, and clear.

Return ONLY the final customer-facing response.
"""

    try:

        return call_llm(
            prompt,
            is_json=False
        )

    except Exception as e:

        print(
            f"Error generating reply: {e}"
        )

        return safe_fallback(
            customer_msg,
            intent,
            history,
            escalation_info
        )


# ============================================================
# COMPLETE AGENT PIPELINE
# ============================================================

def process_message(customer_msg):
    """
    Complete support-agent pipeline:

        1. LLM intent classification
        2. TF-IDF historical retrieval
        3. Deterministic escalation
        4. LLM response generation
        5. Deterministic response validation
        6. Safe fallback if validation fails
    """

    # --------------------------------------------------------
    # 1. Intent
    # --------------------------------------------------------

    intent_data = classify_intent_llm(
        customer_msg
    )

    intent = intent_data.get(
        "intent",
        "other"
    )


    # --------------------------------------------------------
    # 2. Retrieval
    # --------------------------------------------------------

    history = retrieve_history(
        customer_msg
    )


    # --------------------------------------------------------
    # 3. Deterministic escalation
    # --------------------------------------------------------

    should_escalate, escalation_reason = (
        decide_escalation(
            customer_msg,
            intent,
            history
        )
    )

    escalation_info = (
        should_escalate,
        escalation_reason
    )


    # --------------------------------------------------------
    # 4. Generate response
    # --------------------------------------------------------

    generated_reply = generate_reply(
        customer_msg,
        intent,
        history,
        escalation_info
    )


    # --------------------------------------------------------
    # 5. Validate response
    # --------------------------------------------------------

    validation = validate_reply(
        generated_reply,
        customer_msg,
        intent,
        history,
        escalation_info
    )


    # --------------------------------------------------------
    # 6. Safe fallback
    # --------------------------------------------------------

    if validation["valid"]:

        final_reply = generated_reply

    else:

        print(
            "WARNING: Generated reply rejected by "
            f"validator: {validation['reason']}"
        )

        final_reply = safe_fallback(
            customer_msg,
            intent,
            history,
            escalation_info
        )


    # --------------------------------------------------------
    # 7. Final JSON
    # --------------------------------------------------------

    return {
        "intent": intent,
        "should_escalate": should_escalate,
        "escalation_reason": escalation_reason,
        "reply": final_reply,
        "retrieved_cases": history
    }


# ============================================================
# COMMAND-LINE INTERFACE
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Test the AI Customer Support Agent."
        )
    )

    parser.add_argument(
        "--msg",
        type=str,
        help="Customer message to test"
    )

    args = parser.parse_args()


    print(
        f"System Check: provider='{LLM_PROVIDER}', "
        f"fallback='{LLM_FALLBACK_PROVIDER or 'None'}'"
    )

    if LLM_PROVIDER == "groq":

        print(
            f"Groq model: {GROQ_MODEL}"
        )

    elif LLM_PROVIDER == "gemini":

        print(
            f"Gemini model: {GEMINI_MODEL}"
        )


    # --------------------------------------------------------
    # Single-message mode
    # --------------------------------------------------------

    if args.msg:

        print(
            f"\nProcessing Message: {args.msg}\n"
        )

        try:

            result = process_message(
                args.msg
            )

            print(
                json.dumps(
                    result,
                    indent=2
                )
            )

        except Exception as e:

            print(
                f"Execution Failed: {e}"
            )

            sys.exit(1)


    # --------------------------------------------------------
    # Interactive mode
    # --------------------------------------------------------

    else:

        print(
            "\nInteractive Mode. "
            "Type 'exit' to quit.\n"
        )

        while True:

            msg = input(
                "Customer Message: "
            )

            if msg.lower() in [
                "exit",
                "quit"
            ]:

                break

            try:

                result = process_message(
                    msg
                )

                print(
                    json.dumps(
                        result,
                        indent=2
                    )
                )

            except Exception as e:

                print(
                    f"Execution Failed: {e}"
                )

            print(
                "-" * 50
            )
