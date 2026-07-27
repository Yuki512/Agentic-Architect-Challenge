# Part 2 - Step 5: Grounded Concise Summary

## Goal

Summarize cleaned webpage chunks without an external model or API key.

## Summarization skill

`summarize_chunks(chunks, focus, max_words)`:

- Extracts sentence candidates from every chunk.
- Removes duplicate sentences caused by chunk overlap.
- Scores candidates using the user's summary focus.
- Selects a maximum of four useful points.
- Keeps the final result within the requested word limit.
- Records the source chunk IDs used by the summary.

The initial prototype is deterministic and extractive. Every summary point comes
directly from the scraped page, which prevents invented facts.

## Concise summary guardrail

The guardrail blocks a summary when:

- It contains no useful points.
- It exceeds the requested word limit.
- It repeats a point.
- Any point is not supported by the scraped chunks.

## Step 5 flow

`ContentChunk[] -> rank grounded sentences -> select concise points -> guardrail`

An LLM can replace the ranking layer later, while the word-limit and grounding
guardrail remains deterministic.
