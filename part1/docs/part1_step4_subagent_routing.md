# Part 1 Step 4 - Specialized Subagent Routing

## Purpose

After the router agent classifies a non-critical email, the system delegates it to a specialized subagent. Each subagent has a narrow responsibility and a limited set of skills it is allowed to use.

## Subagents

| Subagent | Category | Responsibility |
| --- | --- | --- |
| `BillingSubagent` | Billing | Invoices, duplicate charges, failed payments, receipts, and safe payment verification. |
| `RefundSubagent` | Refund | Refund windows, return eligibility, subscription cancellations, refund timing, and non-refundable items. |
| `TechnicalSubagent` | Technical | App crashes, bugs, checkout errors, and technical tracking issues. |
| `AccountSubagent` | Account | Login, password, profile, email address, and privacy questions. |
| `ShippingSubagent` | Shipping | Delivery timelines, missing packages, damaged shipments, and carrier tracking. |
| `FeedbackSubagent` | Feedback | Suggestions, feature requests, complaints, praise, and product feedback. |
| `OtherSubagent` | Other | Uncategorized questions where the system may need to say the KB has insufficient information. |

## Skill Permissions

- Most subagents can use `KnowledgeRetrievalSkill` and `GroundedDraftSkill`.
- `RefundSubagent` also gets `RefundGuardrailSkill` because refund policy answers must not be invented.
- Critical cases bypass these subagents and go directly to `HumanReviewSkill`.

## Design Note

The subagents are deliberately constrained. They do not freely call every tool. This makes the system easier to test, easier to explain, and safer for policy-sensitive topics like refunds.
