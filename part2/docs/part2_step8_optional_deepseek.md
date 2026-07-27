# Part 2 - Step 8: Optional LLM Summarizer

## Goal

Use an LLM when the summary focus contains detailed instructions, while keeping
the original deterministic summarizer as a safe fallback.

## Configure

Open the shared `.env` in the workspace root, beside the `part1` and `part2`
folders. To use Gemini for Part 2:

```env
SUMMARY_PROVIDER=gemini
GEMINI_API_KEY=your_real_api_key_here
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT_SECONDS=45
```

To use DeepSeek instead:

```env
SUMMARY_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_real_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=45
```

To use the local deterministic summarizer:

```env
SUMMARY_PROVIDER=deterministic
```

The same root file is shared by Parts 1, 2, and 3. The server reads it for every
request, so the key can be added while the UI is running. The key is used only
by the Python backend. It is never returned by the API or sent to browser
JavaScript.

## Processing

1. Scrape and clean the public webpage.
2. Split useful content into source chunks.
3. Send relevant chunks, the summary focus, and word limit to the selected LLM.
4. Require JSON points with source chunk IDs.
5. Check length, duplicates, citations, numbers, and source-term coverage.
6. Use the deterministic summarizer if the key is missing or the LLM response
   fails a check.

The Processing Proof panel identifies the configured LLM model when the LLM
succeeds or `Deterministic fallback` with a reason when it does not.

## GitHub safety

The root `.env` is ignored by Git. Commit the root `.env.example`, which
contains no secret key.
