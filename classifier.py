import re


# ============================================================
# AMAZON CUSTOMER SUPPORT INTENTS
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
    "other",
]


# ============================================================
# KEYWORDS
# ============================================================
#
# Higher weight = stronger evidence for that intent.
#
# We use phrases as well as individual words because:
#
# "refund" is much stronger evidence for refund_issue
# than the generic word "order" is for order_issue.
#
# ============================================================

KEYWORDS = {

    "delivery_issue": {
        "package": 2,
        "parcel": 2,
        "colis": 2,
        "delivery": 3,
        "delivered": 3,
        "shipping": 2,
        "shipment": 2,
        "tracking": 3,
        "courier": 2,
        "arrive": 2,
        "arrived": 2,
        "arrival": 2,
        "late": 2,
        "delivery date": 4,
        "not arrived": 4,
        "hasn't arrived": 4,
        "didn't arrive": 4,
        "wrong address": 4,
        "guaranteed delivery": 5,
        "out for delivery": 4,
        "delivery commitment": 5,
    },

    "order_issue": {
        "cancel my order": 5,
        "cancel order": 5,
        "cancelled order": 5,
        "change my order": 5,
        "modify my order": 5,
        "place an order": 4,
        "can't place": 4,
        "cannot place": 4,
        "order": 1,
    },

    "refund_issue": {
        "refund": 5,
        "refunded": 5,
        "money back": 5,
        "refund pending": 6,
        "refund not received": 6,
        "haven't received my refund": 6,
        "didn't receive my refund": 6,
        "wrong refund": 6,
        "refund email": 6,
        "refund failed": 6,
        "refund couldn't be processed": 7,
        "refund could not be processed": 7,
    },

    "payment_billing_issue": {
        "payment": 4,
        "payment failed": 5,
        "payment problem": 5,
        "charged": 4,
        "charge": 4,
        "charged twice": 6,
        "double charge": 6,
        "billing": 4,
        "credit card": 4,
        "debit card": 4,
        "gift card": 4,
        "amazon pay": 4,
        "unexpected charge": 6,
        "cashback": 5,
        "recharge": 4,
        "transaction": 4,
    },

    "return_issue": {
        "return": 4,
        "returning": 4,
        "send back": 5,
        "return label": 6,
        "return pickup": 6,
        "how to return": 6,
        "return request": 6,
    },

    "product_issue": {
        "damaged": 5,
        "damage": 5,
        "defective": 5,
        "broken": 5,
        "wrong product": 6,
        "wrong item": 6,
        "different product": 6,
        "fake": 5,
        "counterfeit": 5,
        "doesn't work": 5,
        "does not work": 5,
        "not working": 5,
        "quality": 4,
        "missing item": 6,
        "product problem": 5,
        "wrong console": 6,
        "wrong model": 6,
        "wrong version": 6,
    },

    "account_membership_issue": {
        "account": 2,
        "login": 4,
        "log in": 4,
        "password": 4,
        "locked account": 5,
        "account access": 5,
        "prime membership": 6,
        "prime member": 5,
        "membership": 5,
        "cancel prime": 5,
    },

    "technical_issue": {
        "website": 4,
        "app": 4,
        "application": 4,
        "error": 4,
        "bug": 5,
        "crash": 5,
        "crashing": 5,
        "kindle": 5,
        "fire tv": 5,
        "alexa": 5,
        "prime video": 5,
        "not loading": 5,
        "doesn't load": 5,
        "does not load": 5,
        "blank screen": 6,
        "screen": 3,
        "display": 3,
        "echo": 5,
        "dot": 5,
    },

    "pricing_promotion_issue": {
        "price": 4,
        "pricing": 4,
        "discount": 5,
        "coupon": 5,
        "promotion": 5,
        "promo": 5,
        "deal": 5,
        "offer": 4,
        "sale": 4,
        "cashback": 5,
        "discount not applied": 6,
        "coupon not working": 6,
        "offer not applied": 6,
    },
}


# ============================================================
# INTENT PRIORITY
# ============================================================
#
# Used when two intents receive similar scores.
#
# More specific support problems come before generic
# "order" or "account" matches.
#
# ============================================================

PRIORITY = [
    "refund_issue",
    "payment_billing_issue",
    "return_issue",
    "product_issue",
    "delivery_issue",
    "pricing_promotion_issue",
    "technical_issue",
    "account_membership_issue",
    "order_issue",
]


# ============================================================
# HIGH-CONFIDENCE PRECEDENCE RULES
# ============================================================
#
# These narrowly scoped patterns resolve ambiguities before the
# general keyword scorer. They describe a more specific customer
# problem than an overlapping keyword such as "gift card" or
# "delivery" can capture alone.
#

ACCOUNT_CLOSURE_PATTERNS = [
    r"\baccount\b.{0,40}\b(?:closed|locked|deactivated|disabled|suspended)\b",
    r"\b(?:closed|locked|deactivated|disabled|suspended)\b.{0,40}\baccount\b",
]

ACCOUNT_ACCESS_OR_GIFT_CARD_PATTERNS = [
    r"\bgift\s*card\b",
    r"\bgc\b",
    r"\baccount\s+access\b",
    r"\b(?:access|recover|restore|unlock)\b.{0,40}\baccount\b",
    r"\b(?:balance|funds)\b",
]

SCHEDULED_SERVICE_PATTERNS = [
    r"\b(?:scheduled|appointment|booked)\b",
    r"\b(?:assembly|installation|install(?:ation)?|service)\b",
]

SERVICE_NOT_COMPLETED_PATTERNS = [
    r"\b(?:never|didn't|did not|hasn't|has not)\s+happen(?:ed)?\b",
    r"\b(?:missed|failed|didn't occur|did not occur)\b",
]

VAGUE_INVESTIGATION_PATTERN = re.compile(
    r"\binvestigation\b.*\b(?:contact(?:ing)?|callback|call(?:ed)?|line)\b"
    r"|\b(?:contact(?:ing)?|callback|call(?:ed)?|line)\b.*\binvestigation\b"
)

# A vague investigation statement is only "other" when none of these
# concrete domains identify what the customer actually needs help with.
CONCRETE_SUPPORT_DOMAIN_PATTERN = re.compile(
    r"\b(?:order|package|parcel|delivery|shipping|shipment|tracking|"
    r"refund|payment|charge|billing|credit\s+card|debit\s+card|gift\s+card|"
    r"return|product|item|account|login|password|membership|website|app|"
    r"error|kindle|fire\s+tv|alexa|prime\s+video|price|discount|coupon|"
    r"promotion|promo|deal|offer)\b"
)

# Explicit Spanish refund concepts are high-confidence refund issues.
# Generic information or email language is intentionally not included,
# so those words alone cannot trigger refund_issue.
SPANISH_REFUND_STATUS_PATTERN = re.compile(
    r"\b(?:reembolsos?|reembolsado|reembolsar|devoluci[oó]n(?:es)?\s+de\s+dinero)\b"
)

# Refund status language is more specific than a product-description
# phrase such as "wrong item". It keeps refund processing complaints in
# refund_issue instead of letting the product keyword win on score.
REFUND_STATUS_PATTERN = re.compile(
    r"\b(?:refund|refunded|reimburse(?:d|ment)?)\b.*\b(?:wrong\s+(?:item|product)|"
    r"email|status|pending|failed|couldn't\s+be\s+processed|"
    r"could\s+not\s+be\s+processed|more\s+info|information)\b"
    r"|\b(?:wrong\s+(?:item|product)|email|status|pending|failed|"
    r"couldn't\s+be\s+processed|could\s+not\s+be\s+processed|"
    r"more\s+info|information)\b.*\b(?:refund|refunded|reimburse(?:d|ment)?)\b"
)

# Cashback is a promotion term in isolation, but cashback tied to
# Amazon Pay, recharge, payment, or a transaction is a billing matter.
PAYMENT_CASHBACK_PATTERN = re.compile(
    r"\bcashback\b.*\b(?:amazon\s+pay|recharge|payment|transaction|charged?)\b"
    r"|\b(?:amazon\s+pay|recharge|payment|transaction|charged?)\b.*\bcashback\b"
)

# Receiving a wrong model/version/console is a product compatibility
# problem. Refund precedence above still handles a wrong item being
# discussed as part of a refund process.
PRODUCT_COMPATIBILITY_PATTERN = re.compile(
    r"\bwrong\s+(?:console|model|version)\b"
    r"|\b(?:wrong\s+(?:item|product)|(?:item|product)\s+received\s+is\s+wrong)\b"
)

# These combinations identify fulfilment or shipment issues without
# treating a standalone mention of Prime, an item, or a location as delivery.
DELIVERY_FULFILMENT_PATTERN = re.compile(
    r"\b(?:package|parcel|colis)\b.*\b(?:due|today|tomorrow|out\s+for\s+delivery|"
    r"guaranteed|commitment)\b"
    r"|\b(?:due|today|tomorrow|out\s+for\s+delivery|guaranteed|commitment)\b.*"
    r"\b(?:package|parcel|colis|delivery)\b"
    r"|\bmissing\s+items?\b.*\b(?:shipment|package|parcel|delivery|location)\b"
    r"|\b(?:shipment|package|parcel|delivery|location)\b.*\bmissing\s+items?\b"
    r"|\b(?:unsafe|unsecure|insecure)\b.*\b(?:missing|items?|package|parcel|shipment|delivery|location)\b"
    r"|\b(?:missing|items?|package|parcel|shipment|delivery|location)\b.*\b(?:unsafe|unsecure|insecure)\b"
)

# Screen symptoms, cross-device failures, and Echo/Dot setup problems are
# technical functionality issues even when the message omits app/website.
TECHNICAL_DEVICE_PATTERN = re.compile(
    r"\b(?:blank\s+screen|screen\s+is\s+blank|display\s+(?:is\s+)?blank)\b"
    r"|\bworks?\s+on\b.*\b(?:but|not|doesn't|does\s+not)\b"
    r"|\b(?:echo|dots?)\b.*\b(?:not|connect|connection|setup|set\s+up|add|work)\b"
    r"|\b(?:not|connect|connection|setup|set\s+up|add|work)\b.*\b(?:echo|dots?)\b"
)


def _matches_any(patterns, text):
    """Return whether any regular-expression pattern matches text."""

    return any(re.search(pattern, text) for pattern in patterns)


# ============================================================
# CLASSIFIER
# ============================================================

def classify_intent(text):
    """
    Classify a customer message using weighted keyword matching.

    Returns:
        intent, score
    """

    text = str(text).lower()

    # An account closure combined with a gift-card, balance, or access
    # problem is fundamentally an account-access issue. This takes
    # precedence over the generic payment weight for "gift card".
    if (
        _matches_any(ACCOUNT_CLOSURE_PATTERNS, text)
        and _matches_any(ACCOUNT_ACCESS_OR_GIFT_CARD_PATTERNS, text)
    ):
        return "account_membership_issue", 100

    # A missed scheduled assembly, installation, or service concerns
    # fulfillment of the booked service, not package delivery.
    if (
        _matches_any(SCHEDULED_SERVICE_PATTERNS, text)
        and _matches_any(SERVICE_NOT_COMPLETED_PATTERNS, text)
    ):
        return "order_issue", 100

    # A Spanish refund term plus processing/status language is a
    # high-confidence refund-processing complaint.
    if SPANISH_REFUND_STATUS_PATTERN.search(text):
        return "refund_issue", 100

    # Refund processing status takes precedence over the description of
    # the returned or refunded item.
    if REFUND_STATUS_PATTERN.search(text):
        return "refund_issue", 100

    # Cashback related to Amazon Pay, recharge, or a transaction is a
    # payment/billing issue, not a general promotion question.
    if PAYMENT_CASHBACK_PATTERN.search(text):
        return "payment_billing_issue", 100

    # Shipment timing, delivery commitments, and missing shipment items
    # identify delivery fulfilment without broadening Prime/item matches.
    if DELIVERY_FULFILMENT_PATTERN.search(text):
        return "delivery_issue", 100

    # A wrong console/model/version or explicitly wrong received product
    # is a product compatibility issue when no refund process is named.
    if PRODUCT_COMPATIBILITY_PATTERN.search(text):
        return "product_issue", 100

    # Screen and cross-device symptoms, plus Echo/Dot setup failures,
    # are technical issues even without an app or website keyword.
    if TECHNICAL_DEVICE_PATTERN.search(text):
        return "technical_issue", 100

    # Investigation/contact language alone does not establish a support
    # intent. Keep it as other unless a concrete support domain is named.
    if (
        VAGUE_INVESTIGATION_PATTERN.search(text)
        and not CONCRETE_SUPPORT_DOMAIN_PATTERN.search(text)
    ):
        return "other", 100

    scores = {
        intent: 0
        for intent in INTENTS
    }

    # Calculate weighted scores
    for intent, keywords in KEYWORDS.items():

        for keyword, weight in keywords.items():

            if re.search(
                r"\b" + re.escape(keyword) + r"\b",
                text
            ):
                scores[intent] += weight

    # No intent-specific keyword found
    if max(scores.values()) == 0:
        return "other", 0

    # Highest score
    best_score = max(scores.values())

    # Get all intents with the highest score
    candidates = [
        intent
        for intent, score in scores.items()
        if score == best_score
    ]

    # Resolve ties using our priority order
    for intent in PRIORITY:

        if intent in candidates:
            return intent, best_score

    return candidates[0], best_score


# ============================================================
# TEST CASES
# ============================================================

if __name__ == "__main__":

    test_messages = [

        "My package is late and has not arrived yet.",

        "I want a refund for my order.",

        "The product I received is damaged.",

        "My payment was charged twice.",

        "How can I return this item?",

        "The Amazon website keeps showing an error.",

        "I want to cancel my order.",

        "My Prime membership is not working.",

        "Why didn't I get my discount?",

        "Thank you Amazon!",

        "My order hasn't arrived.",

        "Amazon sent me the wrong item.",

    ]

    print("=" * 70)
    print("IMPROVED AMAZON INTENT CLASSIFIER")
    print("=" * 70)

    for message in test_messages:

        intent, score = classify_intent(message)

        print("\nCustomer:")
        print(message)

        print("Intent:")
        print(intent)

        print("Score:")
        print(score)
