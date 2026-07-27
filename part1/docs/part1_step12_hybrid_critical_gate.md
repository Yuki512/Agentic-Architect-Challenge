# Part 1 Step 12 - Hybrid Critical Gate

## Goal

Improve detection of critical paraphrases without allowing an LLM to override
mandatory deterministic escalation rules.

## Flow

```text
Validated EmailCase
        |
        v
DeepSeek Router Agent
        |
        v
Deterministic Critical Gate
        |
        |-- known trigger or contact count > 3 --> Human Review
        |
        v
DeepSeek Semantic Check
        |
        |-- critical or uncertain --> Human Review
        |
        |-- high-confidence non-critical --> Specialist Subagent
        |
        |-- skipped or API error --> deterministic fallback --> Specialist Subagent
```

## Semantic Contract

DeepSeek returns structured JSON containing:

- `decision`: `critical`, `non_critical`, or `uncertain`.
- `condition`: `data_loss`, `service_outage`, `security_breach`, or `none`.
- `confidence`: number from 0 to 1.
- `evidence`: an exact contiguous quote from the customer email.
- `reason`: a short explanation.

A critical result without email evidence is rejected. A non-critical result
below 0.75 confidence is changed to uncertain and routed to human review.

## Trade-Off

The semantic stage catches wording that fixed patterns may miss, but it adds
latency, API cost, availability risk, and probabilistic decisions. Running
deterministic rules first preserves fast and explainable handling of every
mandatory condition explicitly listed in the challenge.

## Operational Behavior

- Deterministic matches never call DeepSeek.
- DeepSeek cannot reverse a deterministic handoff.
- Contact frequency remains a Python numeric comparison.
- Semantic failures are recorded in the audit trace.
- Semantic API failure falls back to the deterministic result so ordinary email
  processing remains available.
