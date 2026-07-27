# Part 1 Step 8 - Refund Hallucination Guardrail

## Purpose

Refund policy is sensitive because the challenge specifically requires the system to avoid hallucinating facts about refunds. The refund guardrail runs after a refund draft is created and blocks unsupported policy claims before the customer sees them.

## Guardrail Checks

For `Refund` cases, the guardrail verifies:

- PDF evidence was retrieved.
- The evidence came from the refund FAQ section.
- The customer did not ask for a specific refund condition that is missing from the evidence.

## Example

If a customer asks:

```text
Can I get a refund after 90 days?
```

The FAQ only states the standard 30-day refund window. The system must not imply that the 30-day policy fully answers the 90-day question. It should block the draft and recommend human review.

## Design Note

This guardrail stays deterministic even if an LLM is added later. The LLM can improve wording, but refund-policy eligibility must still be grounded in retrieved PDF evidence.
