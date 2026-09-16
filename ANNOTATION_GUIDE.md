# Amazon Customer Support Intent Annotation Guide

## Purpose

This guide defines how customer-support messages from the AmazonHelp
dataset should be labelled for the golden evaluation set.

The goal is to assign ONE primary intent to each customer message.

---

# 1. Primary Intent Rule

Every message receives exactly ONE primary intent.

Choose the intent that best represents the customer's MAIN problem
or requested resolution.

Do not assign multiple intents.

### Example

"My order hasn't arrived. Where is it?"

Intent:
delivery_issue

"My order never arrived. Please refund me."

Intent:
refund_issue

"My card was charged but the order failed."

Intent:
payment_billing_issue

---

# 2. Intent Taxonomy

## 1. delivery_issue

### Definition

Problems related to shipping, delivery, package arrival, tracking,
couriers, or delivery dates.

### Include

- Package hasn't arrived
- Delivery is late
- Package marked delivered but not received
- Tracking problem
- Shipping information missing
- Courier/delivery driver problem
- Delivery date problem
- Guaranteed delivery problem

### Examples

"Says delivered but I never received it."

"Where is my package?"

"My delivery is three days late."

### Do NOT use for

A product that arrived damaged or defective.

Use product_issue instead.

---

## 2. order_issue

### Definition

Problems involving the order itself, including placing, modifying,
cancelling, or understanding an order.

### Include

- Can't place an order
- Order status questions
- Order was cancelled
- Want to cancel an order
- Want to change an order
- Wrong order information
- Problems with order details

### Examples

"Can I cancel my order?"

"Why was my order cancelled?"

"I can't place my order."

### Do NOT use for

A package that has already shipped and has a delivery problem.

Use delivery_issue instead.

---

## 3. refund_issue

### Definition

Problems involving refunds or getting money back.

### Include

- Refund requested
- Refund not received
- Refund delayed
- Refund amount incorrect
- Customer asks when refund will arrive

### Examples

"Where is my refund?"

"I was promised a refund but haven't received it."

"When will I get my money back?"

### Do NOT use for

An original payment or unexpected charge.

Use payment_billing_issue instead.

---

## 4. payment_billing_issue

### Definition

Problems involving payments, charges, cards, billing, Amazon Pay,
or payment-related transactions.

### Include

- Payment failed
- Credit/debit card problem
- Unexpected charge
- Incorrect charge
- Amazon Pay problem
- Gift-card payment problem
- Billing problem
- Prime charge when the main issue is the charge itself

### Examples

"Why was my card charged?"

"My payment keeps failing."

"I was charged twice."

### Do NOT use for

A refund that has already been requested and is missing.

Use refund_issue instead.

---

## 5. return_issue

### Definition

Problems involving returning a product or the return process.

### Include

- How to return an item
- Return request
- Return pickup problem
- Return label problem
- Return already started
- Problems sending an item back

### Examples

"How do I return this item?"

"UPS didn't come to collect my return."

"I already started the return."

### Do NOT use for

Simply cancelling an order before delivery.

Use order_issue instead.

---

## 6. product_issue

### Definition

Problems with the physical product/item received or purchased.

### Include

- Damaged product
- Defective product
- Wrong product
- Fake/counterfeit product
- Missing item inside package
- Product quality problem
- Product does not match description

### Examples

"The book arrived damaged."

"I received the wrong item."

"The product doesn't work."

### Important

If the PRODUCT is the problem, use product_issue.

If the PACKAGE/DELIVERY is the problem, use delivery_issue.

---

## 7. account_membership_issue

### Definition

Problems involving the customer's Amazon account or Prime membership.

### Include

- Can't access account
- Login problems
- Forgotten account information
- Account security/access
- Prime membership problem
- Prime subscription problem
- Membership cancellation
- Membership status

### Examples

"I can't log into my Amazon account."

"I forgot which email I used."

"I can't cancel my Prime membership."

### Do NOT use for

A technical problem with a device or application.

Use technical_issue instead.

---

## 8. technical_issue

### Definition

Problems involving Amazon applications, websites, devices,
streaming services, or technical functionality.

### Include

- Amazon app problems
- Website errors
- Checkout technical errors
- Kindle problems
- Fire TV problems
- Alexa problems
- Prime Video playback/errors
- Device/application not working

### Examples

"Prime Video keeps giving me an error."

"My Fire TV isn't working."

"The Amazon app keeps crashing."

### Important

If the technical problem is clearly caused by payment,
order, or another support issue, label the underlying support intent.

---

## 9. pricing_promotion_issue

### Definition

Problems involving product prices, discounts, promotions, coupons,
deals, or advertised offers.

### Include

- Incorrect price
- Discount not applied
- Coupon problem
- Promotion problem
- Lightning Deal problem
- Promotional price mismatch
- Black Friday / Prime Day offer problem

### Examples

"The discount wasn't applied."

"Why is the price different?"

"My coupon isn't working."

---

# 3. Other

Use:

other

only when the message genuinely does not fit any of the nine
defined intents.

Examples:

- Pure thanks
- Pure praise
- Greeting with no support request
- Unclear/contextless message
- General feedback with no identifiable support problem

Do NOT use other just because the message is difficult.

---

# 4. Handling Multiple Problems

When a message contains multiple problems, choose the PRIMARY
problem or requested resolution.

### Example 1

"My package hasn't arrived and I want a refund."

If the customer mainly asks for the money back:

refund_issue

### Example 2

"My package hasn't arrived. When will it arrive?"

delivery_issue

### Example 3

"My order was cancelled and now I want my money back."

If the main request is getting the money back:

refund_issue

### Example 4

"My card was charged but my order failed."

payment_billing_issue

---

# 5. Intent vs Sentiment

Anger, frustration, disappointment, or praise are NOT intents.

For example:

"Your courier service is terrible and my package is late."

Intent:

delivery_issue

NOT:

complaint_feedback

The emotional tone may be used separately when deciding escalation.

---

# 6. Escalation

Intent and escalation are separate decisions.

A message can have any intent and still require either automated
handling or human escalation.

---

# 7. should_escalate = FALSE

Use FALSE when the issue can reasonably be answered using:

- Historical Amazon support knowledge
- Retrieved similar resolved conversations
- General policy/instructional information
- Non-account-specific guidance

Examples:

"How do I return an item?"

"How long does Prime delivery normally take?"

"What is the return process?"

---

# 8. should_escalate = TRUE

Use TRUE when the customer requires information or action that the
support agent cannot safely perform from the available data.

Escalate when:

1. Account-specific information is required
2. Order-specific information is required
3. Payment/account verification is required
4. Sensitive personal information is involved
5. The customer requests an action requiring backend access
6. The issue is unusually ambiguous
7. Historical evidence is insufficient
8. The customer reports a serious/repeated unresolved problem
9. A technical or product issue requires specialist intervention

---

# 9. Escalation Reasons

Use one primary reason.

Allowed values:

- account_access_required
- order_access_required
- payment_verification_required
- backend_action_required
- sensitive_issue
- insufficient_evidence
- ambiguous_request
- repeated_unresolved_issue
- specialist_support_required

---

# 10. Important Rule

Never escalate simply because the customer is angry.

Example:

"This is ridiculous! My package is two days late."

Intent:

delivery_issue

Escalation:

Depends on whether the agent has enough evidence/action capability.

Anger alone is NOT an escalation reason.

---

# 11. Annotation Columns

The golden dataset should contain:

customer_tweet_id
customer_text
gold_intent
should_escalate
escalation_reason
notes

---

# 12. Quality Rule

When uncertain:

1. Read the complete customer message.
2. Identify what the customer actually wants.
3. Identify the underlying problem.
4. Choose exactly ONE primary intent.
5. Apply the escalation rules separately.
6. Add a short note explaining difficult decisions.