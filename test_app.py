import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app import app
import agent
import retrieval


class TestCustomerSupportUnit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def assert_safe_reply(self, reply: str):
        """Assert that reply contains no forbidden claims or vague refusal filler."""
        forbidden_phrases = [
            "i have checked your account",
            "i checked your account",
            "i have looked up your order",
            "i looked up your order",
            "i have opened a ticket",
            "i opened a ticket",
            "i have created a ticket",
            "i created a ticket",
            "ticket #",
            "ticket has been opened",
            "ticket has been created",
            "connecting you to an agent",
            "transferred to a live agent",
            "i am connecting you",
            "i'm connecting you",
            "a support agent needs to verify the details and assist with this issue",
            "please check the options available for your order or account",
        ]
        lower_reply = reply.lower()
        for phrase in forbidden_phrases:
            self.assertNotIn(
                phrase,
                lower_reply,
                f"Reply contained forbidden phrase: '{phrase}'\nFull reply:\n{reply}"
            )

    # ------------------------------------------------------------
    # Basic Endpoint Tests
    # ------------------------------------------------------------

    def test_health_endpoint(self):
        """Test GET /health returns status 200 and provider info."""
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn("provider", data)

    def test_static_index_served(self):
        """Test root / serves index.html."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))
        self.assertIn("Customer Support Assistant", res.text)

    def test_static_assets_served(self):
        """Test style.css, app.js, and vendor markdown/purify libraries are served properly."""
        css_res = self.client.get("/static/style.css")
        self.assertEqual(css_res.status_code, 200)

        js_res = self.client.get("/static/app.js")
        self.assertEqual(js_res.status_code, 200)

        marked_res = self.client.get("/static/vendor/marked.min.js")
        self.assertEqual(marked_res.status_code, 200)

        purify_res = self.client.get("/static/vendor/purify.min.js")
        self.assertEqual(purify_res.status_code, 200)

    def test_chat_empty_message_400(self):
        """Test POST /chat rejects empty or whitespace-only messages with 400."""
        res1 = self.client.post("/chat", json={"message": ""})
        self.assertEqual(res1.status_code, 400)

        res2 = self.client.post("/chat", json={"message": "   "})
        self.assertEqual(res2.status_code, 400)
        self.assertIn("detail", res2.json())

    def test_chat_missing_credentials_503(self):
        """Test POST /chat returns 503 if credentials are unconfigured without crashing."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GROQ_API_KEY": ""}, clear=False):
            res = self.client.post("/chat", json={"message": "Hello"})
            self.assertEqual(res.status_code, 503)
            self.assertIn("detail", res.json())
            self.assertIn("Chatbot service unavailable", res.json()["detail"])

    # ------------------------------------------------------------
    # Dimension 1: Order-status guidance without vague refusal
    # ------------------------------------------------------------

    def test_order_status_guidance(self):
        """Verify order-status queries receive actionable steps and do not escalate unnecessarily."""
        mock_intent = {"intent": "order_issue", "reasoning": "Customer asks how to check order status."}
        mock_reply = (
            "To check your order status:\n"
            "1. Sign in and open 'Your Orders'.\n"
            "2. Locate the specific order.\n"
            "3. Click 'Track Package' or 'View Order Details'.\n"
            "If the order is not visible, check under a different registered email."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=mock_reply):

            res = self.client.post("/chat", json={"message": "How can I check my order status?"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertEqual(data["intent"], "order_issue")
            self.assertFalse(data["should_escalate"])
            self.assertIn("Your Orders", data["reply"])
            self.assertIn("Track Package", data["reply"])
            self.assert_safe_reply(data["reply"])

    # ------------------------------------------------------------
    # Dimension 2: Tracking-information guidance
    # ------------------------------------------------------------

    def test_tracking_information_guidance(self):
        """Verify tracking queries receive practical navigation steps."""
        mock_intent = {"intent": "delivery_issue", "reasoning": "Customer asks where to find tracking info."}
        mock_reply = (
            "You can find your tracking information with these steps:\n"
            "1. Go to 'Your Orders' on the website or mobile app.\n"
            "2. Find your item and select 'Track Package'.\n"
            "3. Review the tracking number and carrier updates.\n"
            "If no tracking updates appear, check the estimated delivery date on your receipt."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=mock_reply):

            res = self.client.post("/chat", json={"message": "Where can I find my tracking information?"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertEqual(data["intent"], "delivery_issue")
            self.assertFalse(data["should_escalate"])
            self.assertIn("Your Orders", data["reply"])
            self.assertIn("Track Package", data["reply"])
            self.assert_safe_reply(data["reply"])

    # ------------------------------------------------------------
    # Dimension 3: Delayed-order guidance
    # ------------------------------------------------------------

    def test_delayed_order_guidance(self):
        """Verify delayed-order queries receive concrete steps grounded in data."""
        mock_intent = {"intent": "delivery_issue", "reasoning": "Customer asks what to do if order is delayed."}
        mock_reply = (
            "If your order is delayed:\n"
            "1. Go to 'Your Orders' and select 'Track Package'.\n"
            "2. Confirm your shipping address and carrier delivery estimate.\n"
            "3. Wait 48 hours past the estimated delivery date for carrier updates.\n"
            "4. If still missing, select 'Problem with order' from your account."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=mock_reply):

            res = self.client.post("/chat", json={"message": "What should I do if my order is delayed?"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertEqual(data["intent"], "delivery_issue")
            self.assertFalse(data["should_escalate"])
            self.assertIn("Track Package", data["reply"])
            self.assert_safe_reply(data["reply"])

    # ------------------------------------------------------------
    # Dimension 4: Damaged-item / return guidance with calm escalation
    # ------------------------------------------------------------

    def test_damaged_item_guidance_and_escalation(self):
        """Verify damaged item queries receive practical steps and explain escalation calmly."""
        mock_intent = {"intent": "product_issue", "reasoning": "Customer received a damaged item."}
        mock_reply = (
            "I'm sorry your item arrived damaged. Here is how you can resolve it:\n"
            "1. Go to 'Your Orders' in your account.\n"
            "2. Click 'Return or Replace Items' next to the damaged item.\n"
            "3. Select 'Item arrived damaged' as the return reason.\n"
            "4. Submit your request to generate a prepaid return label.\n\n"
            "If these steps don't resolve it, the support team may need to follow up. "
            "I can't connect you to an agent or create a ticket here."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=mock_reply):

            res = self.client.post("/chat", json={"message": "My item arrived damaged. What should I do?"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertEqual(data["intent"], "product_issue")
            self.assertTrue(data["should_escalate"])
            self.assertEqual(data["escalation_reason"], "order_access_required")
            self.assertIn("Return or Replace", data["reply"])
            self.assertIn("I can't connect you to an agent or create a ticket here", data["reply"])
            self.assert_safe_reply(data["reply"])

    # ------------------------------------------------------------
    # Dimension 5: Insufficient or weak evidence handling
    # ------------------------------------------------------------

    def test_weak_or_insufficient_evidence_handling(self):
        """Verify that weak evidence queries do not hallucinate false instructions."""
        mock_intent = {"intent": "other", "reasoning": "Customer asks about an unsupported topic."}
        mock_reply = (
            "I don't have enough specific information in my support documentation to answer this question. "
            "Please check the official Help & Customer Service directory online for supported policies."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=mock_reply):

            res = self.client.post("/chat", json={"message": "Can I book an international flight ticket?"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertIn("intent", data)
            self.assert_safe_reply(data["reply"])
            self.assertIn("don't have enough specific information", data["reply"])

    # ------------------------------------------------------------
    # Dimension 6: Genuine escalation with order number / sensitive issue
    # ------------------------------------------------------------

    def test_genuine_escalation_with_order_number(self):
        """Verify genuine escalation triggers escalation flag and provides self-service steps first."""
        mock_intent = {"intent": "order_issue", "reasoning": "Unauthorized charge with order number."}
        mock_reply = (
            "Here is how you can review this order:\n"
            "1. Sign in and open 'Your Orders'.\n"
            "2. Review order # 405-3693108-1234567 for unrecognized transactions.\n"
            "3. Update your account password under 'Login & Security'.\n\n"
            "If these steps don't resolve it, the support team may need to follow up. "
            "I can't connect you to an agent or create a ticket here."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=mock_reply):

            res = self.client.post(
                "/chat",
                json={"message": "Unauthorized charge on order # 405-3693108-1234567, please cancel it!"}
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertTrue(data["should_escalate"])
            self.assertIn(data["escalation_reason"], ["order_access_required", "sensitive_issue"])
            self.assertIn("Your Orders", data["reply"])
            self.assert_safe_reply(data["reply"])

    # ------------------------------------------------------------
    # Dimension 7: Routine questions without escalation
    # ------------------------------------------------------------

    def test_routine_question_without_escalation(self):
        """Verify routine guidance questions do not escalate unnecessarily."""
        mock_intent = {"intent": "return_issue", "reasoning": "General return policy inquiry."}
        mock_reply = (
            "Most items can be returned within 30 days of receipt:\n"
            "1. Visit 'Your Orders' in your account.\n"
            "2. Choose 'Return or Replace Items'.\n"
            "3. Follow the onscreen instructions to receive your return label."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=mock_reply):

            res = self.client.post("/chat", json={"message": "What is the standard return policy?"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            self.assertEqual(data["intent"], "return_issue")
            self.assertFalse(data["should_escalate"])
            self.assert_safe_reply(data["reply"])

    # ------------------------------------------------------------
    # Dimension 8: Safety assertions & validator rejection of false claims
    # ------------------------------------------------------------

    def test_safety_assertions_rejection_of_hallucinated_claims(self):
        """Verify validator catches and rejects claims of live connection or ticket creation."""
        mock_intent = {"intent": "order_issue", "reasoning": "User inquiry."}
        hallucinated_reply = (
            "I have looked up your account and created ticket #98765 for you. "
            "I am now transferring you to a live representative."
        )

        with patch("agent.classify_intent_llm", return_value=mock_intent), \
             patch("agent.call_llm", return_value=hallucinated_reply):

            res = self.client.post("/chat", json={"message": "Help me with my order"})
            self.assertEqual(res.status_code, 200)
            data = res.json()

            # The validator must have rejected hallucinated_reply and substituted safe_fallback
            self.assertNotIn("ticket #98765", data["reply"])
            self.assertNotIn("transferring you", data["reply"])
            self.assertNotIn("looked up your account", data["reply"])
            self.assert_safe_reply(data["reply"])
            # Fallback should provide structured guidance
            self.assertIn("Your Orders", data["reply"])

    # ------------------------------------------------------------
    # Dimension 9: Fallback behavior produces clean, specific guidance
    # ------------------------------------------------------------

    def test_safe_fallback_produces_clean_guidance(self):
        """Verify safe_fallback produces structured steps for each intent without crashing."""
        actionable_intents = [
            "order_issue",
            "delivery_issue",
            "return_issue",
            "product_issue",
            "account_membership_issue",
            "pricing_promotion_issue"
        ]

        for intent in actionable_intents:
            # Test non-escalated fallback
            reply_no_esc = agent.safe_fallback(
                "How do I do this?",
                intent,
                [],
                (False, None)
            )
            self.assertIsInstance(reply_no_esc, str)
            self.assertTrue(len(reply_no_esc) > 50)
            self.assertIn("1.", reply_no_esc)
            self.assertNotIn("I can't connect you to an agent or create a ticket here", reply_no_esc)
            self.assert_safe_reply(reply_no_esc)

            # Test escalated fallback
            reply_esc = agent.safe_fallback(
                "I need help urgently",
                intent,
                [],
                (True, "order_access_required")
            )
            self.assertIsInstance(reply_esc, str)
            self.assertIn("I can't connect you to an agent or create a ticket here", reply_esc)
            self.assert_safe_reply(reply_esc)

        # Test "other" intent fallback (safe insufficient-evidence message)
        reply_other = agent.safe_fallback("Unknown request", "other", [], (False, None))
        self.assertIn("don't have enough verified information", reply_other)
        self.assert_safe_reply(reply_other)

    # ------------------------------------------------------------
    # Retrieval Unit Tests
    # ------------------------------------------------------------

    def test_retrieval_clean_tweet_text(self):
        """Test clean_tweet_text strips Twitter noise from indexing corpus."""
        raw = "@AmazonHelp @user123 Order delayed https://t.co/xyz123 ^SQ"
        cleaned = retrieval.clean_tweet_text(raw)
        self.assertNotIn("@AmazonHelp", cleaned)
        self.assertNotIn("@user123", cleaned)
        self.assertNotIn("https://t.co/xyz123", cleaned)
        self.assertNotIn("^SQ", cleaned)
        self.assertIn("order delayed", cleaned.lower())

    def test_retrieval_evidence_quality_check(self):
        """Test evidence quality check detects weak/out-of-domain evidence."""
        # Unrelated query should yield low similarity (< 0.20)
        cases = retrieval.retrieve_similar_cases("book international flight ticket to Paris", top_k=3)
        self.assertEqual(len(cases), 3)
        is_sufficient, max_sim, reason = retrieval.check_evidence_quality(
            "book international flight ticket to Paris",
            cases,
            threshold=0.20
        )
        self.assertFalse(is_sufficient)
        self.assertTrue(
            "below threshold" in reason or "do not contain relevant support" in reason,
            f"Unexpected reason: {reason}"
        )


class TestCustomerSupportLiveIntegration(unittest.TestCase):
    """Optional end-to-end integration test calling live LLM API if key is present."""

    @unittest.skipUnless(
        os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY"),
        "Live LLM API key required for integration test"
    )
    def test_live_process_message_e2e(self):
        """Verify real LLM returns compliant response structure and safe content."""
        query = "Where can I find my tracking information?"
        result = agent.process_message(query)

        self.assertIn("intent", result)
        self.assertIn("should_escalate", result)
        self.assertIn("escalation_reason", result)
        self.assertIn("reply", result)
        self.assertIn("retrieved_cases", result)

        self.assertEqual(result["intent"], "delivery_issue")
        self.assertFalse(result["should_escalate"])
        self.assertTrue(len(result["retrieved_cases"]) > 0)
        self.assertIn("track", result["reply"].lower())

        # Assert no forbidden phrases in real LLM output
        for phrase in [
            "i looked up your order",
            "i have accessed your account",
            "ticket has been created",
            "connecting you to an agent",
        ]:
            self.assertNotIn(phrase, result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
