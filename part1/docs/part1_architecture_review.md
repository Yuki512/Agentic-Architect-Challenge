## 1. Architecture Flow

```text
Customer Email Input
        |
        v
LangGraph Workflow
        |
        v
DeepSeek Router Agent
        |
        v
Critical Gate
        |
        |-- critical trigger found --> HumanReviewSkill --> Human review
        |
        v
Specialized Subagent
        |
        v
Reusable Skills
        |
        v
Tools
        |
        v
Drafted response or Human review
```

## 3. Agents, Skills, And Tools

### Agents

- **LangGraph Workflow** controls the nodes, branches, and final output.
- **DeepSeek Router Agent** labels every email with a support category.
  Validated structured output selects the category, while deterministic keyword
  classification remains available when the API cannot be used. Non-critical
  emails continue to the matching specialized subagent.
- **Specialized Subagents** handle domain-specific cases:
  - `RefundSubagent`
  - `BillingSubagent`
  - `AccountSubagent`
  - `TechnicalSubagent`
  - `ShippingSubagent`
  - `FeedbackSubagent`
  - `OtherSubagent` as fallback

### Skills

Skills are reusable workflows. They are not one-to-one with agents.

- **KnowledgeRetrievalSkill** searches the FAQ PDF for relevant evidence.
- **GroundedDraftSkill** creates a response using retrieved evidence.
- **RefundGuardrailSkill** blocks unsupported refund-policy answers.
- **HumanReviewSkill** sends the case to a human when it is critical or cannot be answered safely.

### Tools

Tools perform concrete actions:

- **PDFSearchTool** extracts and searches the FAQ PDF.
- **HumanHandoffTool** creates a human review ticket payload.
- **AuditLoggingTool** records key pipeline decisions.

## 4. Safety And Trade-Offs

The **DeepSeek Router Agent** labels the email before the **Critical Gate** runs,
so human reviewers can still see the issue type. If the Router Agent is
unavailable or returns invalid JSON, deterministic keyword rules provide the
category. The gate still runs before subagent routing, PDF search, or drafting.
Its first stage is deterministic and checks for:

- `data loss`
- `service outage`
- `security breach`
- more than 3 support contacts in 7 days

Known matches and the numeric contact rule immediately go to human review.
When no rule matches, DeepSeek performs a structured semantic check for
paraphrases of the same three incident types. Critical and uncertain semantic
results also go to human review. The model must quote evidence from the email,
and it cannot override a deterministic match.

The **Refund Guardrail** prevents hallucination by checking whether the retrieved PDF evidence supports the refund answer. For example, if the customer asks about a refund after 90 days but the PDF only supports a 30-day refund window, the system blocks the draft and sends the case to human review.

The web workflow uses DeepSeek for Router Agent classification, semantic
critical checking, and response drafting. Strict category validation prevents
unknown routes, while keyword routing and template drafting keep the workflow
available when DeepSeek fails. The mandatory trigger rules and Refund Guardrail
remain deterministic safety layers.

LangGraph replaces the earlier manual Python `if/else` orchestrator. Each major
step is now an explicit node, and conditional edges route critical cases to
human handoff or normal cases to the specialist path.

## 5. Example Outcomes

| Case | Result |
| --- | --- |
| Refund within 30 days | Classified as Refund, PDF evidence found, guardrail passed, draft created. |
| Duplicate charge | Classified as Billing, billing FAQ evidence found, draft created. |
| Login issue | Classified as Account, account FAQ evidence found, draft created. |
| Data loss | Classified as Technical, Critical Gate detects trigger, HumanReviewSkill runs, no auto-draft. |
| More than 3 contacts in 7 days | Critical Gate routes to human review. |
| Refund after 90 days | RefundGuardrailSkill blocks unsupported answer, HumanReviewSkill runs. |

## 6. Failure Handling

- If a critical trigger is found, the system bypasses normal drafting and creates a human review ticket.
- If a semantic critical result is uncertain, the system chooses human review.
- If semantic checking is unavailable, the system records the failure and
  continues using the deterministic result.
- If the PDF search returns no reliable evidence, the system avoids guessing and sends the case to human review.
- If the refund policy evidence does not support the requested condition, the refund guardrail blocks the response.
- Every major decision is represented in structured outputs and can be logged for observability.

## 7. Prototype Scope

This prototype does not connect to a real email inbox. The local web UI simulates email intake. In production, the same `process_email(email_case)` pipeline could be connected to Gmail, Zendesk, Freshdesk, Intercom, or another support platform.

The implementation is intentionally small and testable for the exercise while still representing a production-style agent architecture.
