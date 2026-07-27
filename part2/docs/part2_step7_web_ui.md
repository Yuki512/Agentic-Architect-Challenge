# Part 2 - Step 7: URL Input Web UI

## Goal

Provide a usable interface where the user enters any public webpage URL and sees
the grounded summary plus compact processing proof.

## User inputs

- Public webpage URL.
- Summary focus.
- Maximum summary length from 40 to 250 words.

The English Reborn! Wikipedia article is an optional sample and is not fixed as
the only input.

## Output

- Page title and source link.
- Grounded summary points.
- HTTP status and downloaded size.
- Useful content word count.
- Chunk IDs and sizes.
- Concise guardrail result.
- Components used by the pipeline.

The UI supports light and dark themes and remembers the selected theme.

## HTTP endpoints

- `GET /api/examples`
- `POST /api/process`

Run the interface with `scripts/run_web_app.py`. The default local address is
`http://127.0.0.1:8765`.
