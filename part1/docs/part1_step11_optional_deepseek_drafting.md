# Part 1 - Step 11: Optional DeepSeek Response Drafting

## Goal

Use DeepSeek only to improve the wording of a customer-facing reply. Critical
detection, routing, PDF search, refund-policy checks, and human-review decisions
remain deterministic.

## Configure

Open the shared `.env` in the workspace root, beside the `part1` and `part2`
folders, and fill in the API key:

```env
DEEPSEEK_API_KEY=your_real_api_key_here
```

The same root file is shared by Parts 1, 2, and 3. The defaults select
`deepseek-v4-flash` through `https://api.deepseek.com`. The Python backend reads
the root `.env` for every request. The API key is never sent to browser
JavaScript or included in a pipeline response.

## Drafting flow

1. The fixed Critical Gate checks the email.
2. The Router Agent selects a category, with keyword rules as its fallback.
3. `PDFSearchTool` retrieves FAQ evidence.
4. DeepSeek receives the email and retrieved passages, then writes a natural
   reply.
5. The LLM must return evidence IDs and exact supporting quotes.
6. Fixed grounding checks reject unsupported numbers, promises, citations, or
   excessive length.
7. The deterministic Refund Guardrail checks refund-policy support.

If the key is missing, the API is unavailable, or an LLM grounding check fails,
the existing deterministic template creates the draft. If PDF evidence is
missing or refund conditions are unsupported, the case goes to human review.

The Pipeline Proof panel displays the response writer and any fallback reason.

## GitHub safety

The root `.env` is ignored by Git. Commit the root `.env.example`, which
contains no secret key.
