# Part 3 - Step 9: Reliability and Observability

## Goal

Make the document agent easier to operate and diagnose without recording user
prompts, conversation text, or API credentials.

## Operational safeguards

- Every agent turn has a UUID request ID and measured latency.
- Successful turns log status, evidence count, and tool count.
- Failed turns log a sanitized public error and exception type.
- Logs are JSON lines written to `logs/document_agent.log`.
- Log files rotate at 1 MB and retain three backups.
- `GET /api/health` reports the model, loaded document, and SQLite readiness
  metadata without exposing local filesystem paths.
- The launcher waits for `/api/health` before opening the browser.

## Existing reliability controls

- User messages and HTTP request bodies have explicit size limits.
- Model calls have a configurable timeout.
- Tool loops stop after two iterations.
- Calculator and date tools validate and bound their inputs.
- Grounding validation blocks unsupported policy answers and invalid citations.
- SQLite checkpoints persist conversation context between restarts.
- Per-thread locks prevent simultaneous writes to the same conversation.
- HTTP errors return safe messages instead of internal exception details.

## Verification

Run all offline tests from `part3`:

```powershell
$env:PYTHONPATH = (Resolve-Path "src").Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests do not call DeepSeek. A live API key is only needed for an actual
conversation.
