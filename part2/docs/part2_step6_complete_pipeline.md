# Part 2 - Step 6: Complete Processing Pipeline

## Goal

Connect every Part 2 component behind one function that can later be called by
the URL-input web UI.

## Entry points

- `process_scrape_request(request)` processes a validated `ScrapeRequest`.
- `process_url_payload(payload)` validates a dictionary received from a future
  HTTP API and returns a JSON-safe result.

## Complete flow

`URL payload`

`-> URL validation`

`-> WebsiteScraperTool`

`-> UsefulContentCleaner`

`-> LongContentChunkingSkill`

`-> GroundedSummarizationSkill`

`-> ConciseSummaryGuardrail`

`-> summary_ready`

## Pipeline proof

The result contains:

- Final URL, HTTP status, content type, and downloaded byte count.
- Page title, useful word and block counts, and cleaning decisions.
- Chunk IDs and word counts.
- Final summary, source chunk IDs, and concise guardrail result.
- Names of the components used.

Raw HTML and full chunk text are intentionally excluded from the serialized
result. This keeps the future UI response small and avoids exposing unnecessary
webpage content.
