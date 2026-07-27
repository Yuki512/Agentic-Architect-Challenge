# Part 1 Step 2 - Critical Issue Gate

## Purpose

The critical issue gate runs after the email receives a category label and
before subagent routing, knowledge retrieval, or response drafting. This keeps
the category available for human reviewers while ensuring that urgent cases
never receive an automatic draft.

## Hybrid Gate

The gate uses two ordered checks:

1. Deterministic Python rules check the mandatory phrases and contact count.
2. DeepSeek checks semantic paraphrases only when no deterministic trigger
   matched.

The deterministic stage routes an email to a human when any of these conditions
are true:

- The subject or body mentions `data loss`.
- The subject or body mentions `service outage`.
- The subject or body mentions `security breach`.
- The customer contacted support more than 3 times in the last 7 days.

DeepSeek may detect paraphrases such as customer records disappearing or an
unknown person accessing protected information. Its structured response is
limited to `data_loss`, `service_outage`, `security_breach`, or `none`.

The semantic result must quote evidence that exists in the email. A `critical`
or `uncertain` result goes to human review. A high-confidence `non_critical`
result continues to subagent routing.

## Output

The combined gate returns:

- `is_critical`: whether a human handoff is required.
- `matched_triggers`: which deterministic or semantic trigger matched.
- `contact_count_last_7_days`: normalized contact count.
- `reason`: explanation of the decision.
- `recommended_action`: either `handoff_to_human_agent` or `continue_to_classification`.
- `semantic_critical_check`: model status, condition, confidence, quoted email
  evidence, provider, and model.

## Design Note

DeepSeek never overrides a deterministic match. The numeric repeat-contact rule
also remains deterministic. If the semantic API is disabled or unavailable, the
system records the failure and continues with the deterministic result.

This hybrid design improves paraphrase coverage while preserving a fast,
auditable mandatory gate. The accepted trade-off is one additional model call
for non-matching emails and probabilistic semantic classification.
