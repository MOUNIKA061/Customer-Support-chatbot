# Customer Support Chatbot — Implementation & Improvements Report

This document details the engineering work, architectural enhancements, bug fixes, UI integration, and testing completed on the **Customer Support Chatbot** project.

---

## Table of Contents
1. [Project Overview & Objectives](#1-project-overview--objectives)
2. [Phase 1: Full-Stack Web Application (`app.py`, `static/`)](#2-phase-1-full-stack-web-application)
3. [Phase 2: Diagnosis & Root Cause Analysis](#3-phase-2-diagnosis--root-cause-analysis)
4. [Phase 3: Backend & Retrieval Improvements (`agent.py`, `retrieval.py`)](#4-phase-3-backend--retrieval-improvements)
5. [Phase 4: Markdown Formatting & Security Sanitization (`static/app.js`, `static/style.css`, `static/vendor/`)](#5-phase-4-markdown-formatting--security-sanitization)
6. [Phase 5: Automated Test Suite & Verification](#6-phase-5-automated-test-suite--verification)
7. [Before vs. After Comparison](#7-before-vs-after-comparison)
8. [Data Limitations & Knowledge Gaps in `amazon_sample_200.csv`](#8-data-limitations--knowledge-gaps-in-amazon_sample_200csv)
9. [How to Run the Application & Tests](#9-how-to-run-the-application--tests)

---

## 1. Project Overview & Objectives

The goal of this project was to transform an experimental Twitter Customer Support (TWCS / AmazonHelp) prototype into a polished, safe, and actionable full-stack customer support chatbot.

### Core Operating Principles & Boundaries
- **Guidance-Only Assistant**: Explains step-by-step how a customer can check order status, find tracking details, or initiate returns.
- **No False Claims**: Never claims to connect to a live agent, create a support ticket, or access customer accounts/live databases.
- **Separation of Escalation from Self-Service**: When human follow-up is needed, provides practical self-service steps first, accompanied by a calm escalation notice.
- **Zero Hallucination / Safe Fallbacks**: When evidence is missing or weak, gives clear, grounded assistance instead of fabricating policies.

---

## 2. Phase 1: Full-Stack Web Application

### Backend API ([`app.py`](app.py))
- Built with **FastAPI** to expose the existing `process_message(message)` pipeline.
- **Endpoints**:
  - `POST /chat`: Accepts `{"message": "..."}`, validates input, executes pipeline, and returns:
    ```json
    {
      "intent": "delivery_issue",
      "should_escalate": false,
      "escalation_reason": null,
      "reply": "Step-by-step guidance...",
      "retrieved_cases": [...]
    }
    ```
  - `GET /health`: Returns service health, configured LLM provider (`groq` / `gemini`), and readiness status.
  - `GET /` and `GET /static/*`: Serves the responsive web frontend.
- Added input validation (rejecting empty or whitespace-only messages with HTTP 400).
- Handled unconfigured API credentials gracefully with HTTP 503 without crashing.

### Responsive Web UI ([`static/`](static/))
- **`index.html`**: Clean semantic HTML layout with header status indicator, guidance disclaimer banner, conversation log, example prompt pills, and accessible message form.
- **`style.css`**: Modern chat styling with responsive layout, user/bot message bubbles, animations, and accessible focus states.
- **`app.js`**: Client-side logic handling message submissions, auto-resizing textareas, Enter/Shift+Enter keybindings, loading indicators, error banners with retry capability, and a developer diagnostics accordion (hidden by default).

---

## 3. Phase 2: Diagnosis & Root Cause Analysis

Before our changes, the bot frequently gave vague or evasive answers such as:
> *"Please check the options available for your order or account..."*
> *"A support agent needs to verify the details and assist with this issue."*

Our inspection of [`agent.py`](agent.py) and [`retrieval.py`](retrieval.py) uncovered four specific root causes:

1. **Over-Broad Escalation Matching**:
   - `decide_escalation()` flagged any message containing `"check"`, `"order"`, or `"tracking"` as requiring account access (`should_escalate = True`).
   - This caused routine queries like *"How can I check my order status?"* to escalate immediately and refuse to answer.

2. **Defeatist Prompt Guidelines**:
   - Rule 11 in `generate_reply()` explicitly recommended: *"You may say: 'A support agent needs to verify the details and assist with this issue.'"*
   - The LLM defaulted to this evasion rather than providing helpful self-service instructions.

3. **Flawed Validator Regular Expressions**:
   - In `validate_reply()`, `account_access_patterns` matched phrases like `"view your tracking"` or `"check your order"`.
   - The validator mistook instructions given *to* the user for the assistant falsely claiming *it* accessed the user's account. This caused valid replies to be rejected and replaced with generic fallback filler.

4. **Corpus Noise & Accidental Token Matches**:
   - Retrieval originally searched only raw customer tweets (`customer_text`).
   - Twitter noise (handles like `@AmazonHelp`, shortened links `https://t.co/...`, agent codes `^SQ`) degraded TF-IDF term weights.
   - Accidental customer words (e.g. *"I have a flight in the evening"*, *"where is the cat tree for my cat's birthday"*) caused irrelevant tweets to achieve high similarity for unrelated questions like *"Can I book a flight?"* or *"Can I adopt a pet?"*.

---

## 4. Phase 3: Backend & Retrieval Improvements

### Improved Retrieval & Evidence Quality ([`retrieval.py`](retrieval.py))
- **`clean_tweet_text(text)`**: Strips `@handles`, URLs, and agent sign-offs so term frequency accurately reflects customer support concepts.
- **Dual-Corpus Indexing**: Combined cleaned customer text with historical Amazon agent responses (`search_corpus = cleaned_customer + " " + cleaned_amazon`).
- **Support Guidance Vectorizer (`response_vectorizer`)**: Measures whether the historical Amazon reply actually provides relevant guidance.
- **Explicit Quality Check (`check_evidence_quality`)**: Verifies both overall similarity ($\ge 0.18$) and support guidance relevance ($\ge 0.05$). Queries with zero response relevance (e.g., flight booking) are marked as insufficient evidence.

### Escalation Logic Calibration ([`agent.py`](agent.py))
- Added `is_routine_howto` check to `decide_escalation()`:
  - Routine self-service queries (*"How can I check my order status?"*, *"Where can I find tracking?"*, *"What is your return policy?"*) are **not** escalated (`should_escalate = False`).
  - Genuine escalations (explicit order IDs, damaged/broken/lost items, unauthorized charges) correctly set `should_escalate = True`.

### Actionable Prompt Engineering ([`agent.py`](agent.py))
- Revised system instructions in `generate_reply()`:
  - Prioritize direct answers with concrete numbered steps:
    1. Where to go (e.g., "Your Orders").
    2. What to select (e.g., "Track Package", "Return or Replace").
    3. What information to verify (e.g., estimated delivery date, carrier updates).
    4. Next steps if the first action does not resolve the issue.
  - If `should_escalate` is true, explain self-service steps first and calmly append the notice:
    > *"If these steps don't resolve it, the support team may need to follow up. I can't connect you to an agent or create a ticket here."*

### Validator & Safe Fallback Overhaul ([`agent.py`](agent.py))
- Refined `account_access_patterns` and `future_patterns` in `validate_reply()` to allow user-directed guidance while continuing to block false claims of live handoff or ticket creation.
- Replaced single-line fallback filler with structured, intent-specific guidance across all 10 intent categories.

---

## 5. Phase 4: Markdown Formatting & Security Sanitization

### Problem Solved
Backend replies returned Markdown formatting (`**bold text**`, numbered lists `1. Step`), but the frontend previously used `bubble.textContent = data.reply`, displaying asterisks and list markers literally as raw text.

### Implementation Details
1. **Local Vendor Integration ([`static/vendor/`](static/vendor/))**:
   - Downloaded and bundled `marked.min.js` (v15.0) and `purify.min.js` (DOMPurify v3.4) locally in the repository.
   - Zero external CDN dependencies; operates completely offline and in restricted environments.
   - Loaded in [`static/index.html`](static/index.html) prior to `app.js`.

2. **Safe Rendering Pipeline ([`static/app.js`](static/app.js))**:
   - Implemented `renderMarkdownSafe(text)`:
     - Parses Markdown using `marked.parse(text, { gfm: true, breaks: true })`.
     - Sanitizes generated HTML via `DOMPurify.sanitize(...)`, permitting safe formatting tags (`<p>`, `<strong>`, `<ol>`, `<li>`, `<code>`, `<em>`, etc.) while strictly stripping `<script>`, `<iframe>`, `onerror`, `onload`, and `javascript:` URIs.
   - Built-in safe fallback parser (`renderFallbackMarkdown`) that HTML-escapes all entities (`&`, `<`, `>`, `"`, `'`) before applying regex-based bold and list formatting.

3. **Strict Plain-Text User Messages**:
   - In `appendMessage(sender, text)`, user inputs are rendered strictly using `bubble.textContent = text;`. User text is never evaluated as HTML or Markdown.

4. **Typographic Spacing ([`static/style.css`](static/style.css))**:
   - Added styles for `.bot-bubble`: sets `white-space: normal;` and defines clean margins for `<p>`, `<ol>`, and `<li>` elements to ensure readability.

---

## 6. Phase 5: Automated Test Suite & Verification

### Python Backend & API Tests ([`test_app.py`](test_app.py))
17 automated tests covering all 9 required testing dimensions:

```bash
python -m unittest -v test_app.py
```

- `test_order_status_guidance`: Verifies actionable steps and non-escalation for order status queries.
- `test_tracking_information_guidance`: Verifies practical navigation steps for tracking queries.
- `test_delayed_order_guidance`: Verifies concrete delayed-order steps grounded in data.
- `test_damaged_item_guidance_and_escalation`: Verifies self-service steps + calm escalation notice.
- `test_weak_or_insufficient_evidence_handling`: Verifies out-of-domain queries acknowledge lack of evidence without hallucinating.
- `test_genuine_escalation_with_order_number`: Verifies sensitive/order-numbered queries trigger escalation.
- `test_routine_question_without_escalation`: Verifies policy questions do not escalate unnecessarily.
- `test_safety_assertions_rejection_of_hallucinated_claims`: Verifies validator blocks false ticket creation/handoff claims.
- `test_safe_fallback_produces_clean_guidance`: Verifies intent-specific fallback formatting across all intents.
- `test_retrieval_clean_tweet_text`: Verifies handle and URL stripping.
- `test_retrieval_evidence_quality_check`: Verifies evidence quality filtering.
- `test_health_endpoint`: Verifies HTTP 200 health check response.
- `test_static_index_served`: Verifies `index.html` root route.
- `test_static_assets_served`: Verifies `style.css`, `app.js`, `marked.min.js`, and `purify.min.js`.
- `test_chat_empty_message_400`: Verifies HTTP 400 validation on empty messages.
- `test_chat_missing_credentials_503`: Verifies HTTP 503 handling when API keys are absent.
- `test_live_process_message_e2e`: End-to-end integration test calling live LLM API.

**Result**: `Ran 17 tests in 2.978s — OK`

### Frontend Markdown & Sanitization Tests ([`test_markdown_render.js`](test_markdown_render.js))
7 tests executed via JSDOM and Node.js:

```bash
node test_markdown_render.js
```

1. **Bold Formatting**: `**Your Orders**` renders as `<strong>Your Orders</strong>` without literal `**`.
2. **Numbered Lists**: `1. Log in ... 2. Navigate` renders as `<ol><li>...</li></ol>` without literal markers.
3. **Mixed Content**: Correctly formats combination of intro paragraph, bold tags, and ordered lists.
4. **XSS Script Injection**: Strips `<script>alert("XSS")</script>` completely.
5. **Dangerous Attributes & Protocols**: Strips `onerror` handlers and `javascript:` URIs.
6. **Fallback Parser**: Safely escapes HTML entities and formats lists when libraries are bypassed.
7. **User Message Isolation**: Confirms user messages remain 100% plain text.

**Result**: `All 7 markdown formatting & sanitization tests PASSED!`

---

## 7. Before vs. After Comparison

| Query | Metric / Field | Before Changes | After Changes |
|---|---|---|---|
| **"How can I check my order status?"** | **Intent**<br>**Escalate**<br>**Reason**<br>**Similarity**<br>**Reply** | `order_issue`<br>`True`<br>`order_access_required`<br>`0.358`<br>*(Vague refusal)*<br>`"A support agent needs to verify the details and assist with this issue."` | `order_issue`<br>`False`<br>`None`<br>`0.358` (response relevance: `0.197`)<br>*(Actionable numbered steps)*<br>`1. Log in to your account on the Amazon website or app.`<br>`2. Go to "Your Orders".`<br>`3. Find the order in question and click "Track Package" (or "View Order Details").`<br>`4. The page will show current status, carrier tracking number, and estimated delivery date.` |
| **"Where can I find my tracking information?"** | **Intent**<br>**Escalate**<br>**Reason**<br>**Similarity**<br>**Reply** | `delivery_issue`<br>`True`<br>`order_access_required`<br>`0.305`<br>*(Vague refusal)*<br>`"A support agent needs to verify the details and assist with this issue."` | `delivery_issue`<br>`False`<br>`None`<br>`0.305` (response relevance: `0.417`)<br>*(Actionable navigation steps)*<br>`1. Sign in to your account and go to "Your Orders".`<br>`2. Locate the order and select "Track Package" to review carrier details and estimated delivery date.`<br>`3. Check your registered email for delay updates or carrier notifications.`<br>`4. If tracking shows no updates past estimated delivery date, select "Problem with order".` |
| **"What should I do if my order is delayed?"** | **Intent**<br>**Escalate**<br>**Reason**<br>**Similarity**<br>**Reply** | `delivery_issue`<br>`False`<br>`None`<br>`0.336`<br>*(Sparse general advice)*<br>`"Check the tracking status in your order details. If the package is still delayed, you can contact customer service for further help."` | `delivery_issue`<br>`False`<br>`None`<br>`0.336` (response relevance: `0.276`)<br>*(Clear troubleshooting sequence)*<br>`1. Go to "Your Orders" and click "Track Package".`<br>`2. Review carrier tracking for latest notes or exceptions.`<br>`3. Verify the shipping address matches what was entered.`<br>`4. Contact carrier directly using the tracking link if needed.`<br>`5. If delay persists past estimated date, click "Problem with this order?".` |
| **"My item arrived damaged. What should I do?"** | **Intent**<br>**Escalate**<br>**Reason**<br>**Similarity**<br>**Reply** | `product_issue`<br>`True`<br>`order_access_required`<br>`0.198`<br>*(Vague refusal)*<br>`"I'm sorry to hear that. A support agent needs to verify the details and assist with this issue."` | `product_issue`<br>`True`<br>`order_access_required`<br>`0.198` (response relevance: `0.237`)<br>*(Self-service return steps + calm escalation notice)*<br>`1. Open "Your Orders" page in your account.`<br>`2. Locate the order containing the damaged item.`<br>`3. Click "Return or Replace Item" (or "Report a Problem").`<br>`4. Select "Damaged item" as the reason and follow prompts.`<br>`5. Upload photos of damage and packaging if prompted.`<br>`6. Submit claim to receive return shipping label and confirmation.`<br><br>*"If these steps don't resolve the issue, the support team may need to follow up. I can't connect you to an agent or create a ticket here."* |

---

## 8. Data Limitations & Knowledge Gaps in `amazon_sample_200.csv`

1. **Zero Damaged Item Cases**: The words `"damaged"` and `"damage"` appear **0** times across all 200 customer messages and Amazon replies. The dataset only contains one mention of `"defective"` and one mention of `"broken"`. Damage queries rely on return workflows and safe fallbacks.
2. **Tweet Character Limits**: Historical tweets (140/280 characters) often directed users to external links (`amzn.to`, `t.co`) or stated *"We've sent a correspondence to your registered email"* rather than containing full policy text.
3. **Conversational Side-Tracks**: Past tweets frequently included unrelated personal context (*"flight in evening"*, *"cat's birthday"*). The dual-corpus response relevance check was introduced specifically to prevent false matches on these terms.

---

## 9. How to Run the Application & Tests

### Prerequisites
- Python 3.9+
- A valid API key in `.env` (either `GROQ_API_KEY` or `GEMINI_API_KEY`):
  ```env
  LLM_PROVIDER=groq
  GROQ_API_KEY=gsk_...
  GROQ_MODEL=llama-3.3-70b-versatile
  ```

### Installation
```powershell
pip install -r requirements.txt
```

### Running the Application
```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)**.

### Running Backend Tests
```powershell
python -m unittest -v test_app.py
```

### Running Frontend Formatting & Security Tests
```powershell
node test_markdown_render.js
```

