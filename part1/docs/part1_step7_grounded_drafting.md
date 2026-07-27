# Part 1 Step 7 - Grounded Response Drafting

## Purpose

The drafting step creates a concise customer-facing reply only after the case passes the critical gate, is classified, is routed to a subagent, and retrieves FAQ evidence from the PDF.

## Draft Output

The draft returns:

- `status`: `drafted` or `needs_human_review`.
- `reply`: customer-facing response.
- `evidence`: PDF passages used to support the response.
- `internal_notes`: trace of which subagent and evidence source created the draft.

## Behavior

- If PDF evidence is found, the draft uses the highest-scoring passage.
- If no evidence is found, the draft does not invent an answer and recommends human review.
- Critical cases do not use this step because they are routed to human handoff first.

## Design Note

This is a deterministic draft builder for Part 1. Later, an LLM can improve tone and wording, but it should still receive retrieved evidence and must not add unsupported policy facts.
