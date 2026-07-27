# Part 1 Step 1 - Email Input Definition

## Purpose

The production system would receive customer support emails from a real inbox platform such as Gmail, Zendesk, Freshdesk, or Intercom. For this prototype, the web UI will simulate that intake step by letting a user paste an email and enter basic customer metadata.

This keeps the project focused on the agentic workflow: critical detection, classification, routing, knowledge-base retrieval, drafting, and guardrails.

## Email Input Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `case_id` | string | yes | Unique ID for the support case. |
| `customer_id` | string | yes | Unique ID for the customer. |
| `customer_name` | string | yes | Customer name used for the drafted reply. |
| `customer_email` | string | yes | Customer email address. |
| `subject` | string | yes | Email subject line. |
| `body` | string | yes | Full customer email body. |
| `contact_count_last_7_days` | integer | yes | Number of times the customer contacted support in the last 7 days. |
| `received_at` | string | yes | ISO timestamp for when the email was received. |
| `metadata` | object | no | Optional order ID, product name, subscription type, or app version. |

## Example Input

```json
{
  "case_id": "CASE-1001",
  "customer_id": "CUST-042",
  "customer_name": "Alicia Tan",
  "customer_email": "alicia@example.com",
  "subject": "Can I return my order?",
  "body": "Hi, I received my order 10 days ago. The item is unused and still in the original packaging. Can I return it for a refund?",
  "contact_count_last_7_days": 1,
  "received_at": "2026-07-24T09:30:00+08:00",
  "metadata": {
    "order_id": "ORD-7781",
    "product": "Nimbus Bottle"
  }
}
```

## Why These Fields Matter

- `subject` and `body` are used by the router agent to classify the support issue.
- `contact_count_last_7_days` is required for the mandatory human handoff rule.
- `customer_name` helps the draft response sound natural.
- `metadata` gives the final response or handoff summary useful context without needing a real email integration.

## Production Extension

In production, these fields would be created by an email ingestion service:

1. Pull new support emails from Gmail, Zendesk, Freshdesk, or Intercom.
2. Normalize the message into the `EmailCase` structure.
3. Look up recent contact count from the CRM or support ticket database.
4. Pass the normalized case into the agent graph.
