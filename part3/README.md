# Part 3 - Nimbus Policy Document Agent

A document-grounded conversational agent that answers questions from one sample
PDF, remembers conversation context, and decides when calculator or date tools
are necessary.

## Requirement coverage

| Challenge requirement | Implementation |
| --- | --- |
| Open-source agent framework | LangGraph state graph with explicit routing |
| Single sample document | `data/nimbus_travel_expense_policy.pdf` |
| Conversation memory | LangGraph SQLite checkpoints by thread ID |
| Remember user context | Name extraction plus the latest 20 conversation turns |
| Selective tool use | Model chooses calculator or date tool only when needed |
| Grounded answers | BM25 retrieval, page/section citations, answer validation |
| Operational thinking | Tests, bounded inputs, timeouts, request IDs, JSON logs |

## Quick start

From the workspace root on Windows:

```powershell
.\open_part3.bat
```

The launcher checks the Part 3 environment, starts the service, waits for
`GET /api/health`, and opens `http://127.0.0.1:9000`.

The server runs in its own terminal window. Close that window or press `Ctrl+C`
there to stop it.

## First-time setup

Part 3 uses its own virtual environment:

```powershell
cd part3
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create or update `.env` in the workspace root, one level above `part3`:

```dotenv
QA_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=45
PART3_TIMEZONE=Asia/Singapore
```

Environment variables override values from the `.env` file. Never commit the
real API key.

## Run options

Start the web interface manually:

```powershell
cd part3
.\.venv\Scripts\python.exe scripts\run_web_app.py --port 9000
```

Start an interactive terminal conversation:

```powershell
cd part3
.\.venv\Scripts\python.exe scripts\run_agent.py
```

Send one question and return JSON:

```powershell
.\.venv\Scripts\python.exe scripts\run_agent.py `
  --message "What is the Singapore hotel limit?" --json
```

Resume a terminal conversation by passing its existing UUID:

```powershell
.\.venv\Scripts\python.exe scripts\run_agent.py `
  --thread-id "existing-thread-uuid"
```

## Test

The complete test suite is offline and does not spend API credits:

```powershell
cd part3
$env:PYTHONPATH = (Resolve-Path "src").Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## What to inspect

- `src/document_agent/agent.py`: LangGraph orchestration and grounding guardrail.
- `src/document_agent/retriever.py`: section-level BM25 retrieval.
- `src/document_agent/memory.py`: SQLite conversation checkpoints.
- `src/document_agent/tools.py`: bounded calculator and date tools.
- `src/document_agent/web_app.py`: local HTTP API and static interface server.
- `web/`: chat, source PDF, and processing-trace interface.
- `tests/`: offline behavior and safety tests.
- `docs/part3_architecture.md`: design, trade-offs, and failure handling.
- `docs/part3_demo_interview_guide.md`: repeatable demonstration script.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Readiness and dependency metadata |
| `GET` | `/api/config` | Public UI configuration |
| `POST` | `/api/chat` | Ask a question within a conversation thread |
| `GET` | `/api/conversations/{thread_id}` | Restore visible conversation history |
| `DELETE` | `/api/conversations/{thread_id}` | Clear one conversation |
| `GET` | `/document` | Display the sample policy PDF |

## Local data

Conversation state is stored in `data/conversations.sqlite3`. SQLite is suitable
for this single-machine prototype because it needs no database service and works
directly with the LangGraph checkpointer. PostgreSQL would be the next step for
multiple application instances, many concurrent writers, centralized backups,
or production access controls.

Runtime logs are JSON lines in `logs/document_agent.log`. They contain request
metadata and sanitized failures, not prompts, conversation text, or API keys.

## Troubleshooting

- `DEEPSEEK_API_KEY is not configured`: add the key to the workspace `.env`.
- Authentication failure: verify the key and `DEEPSEEK_BASE_URL`.
- Rate limit or timeout: wait and retry; the configured timeout is bounded from
  5 to 120 seconds.
- Port 9000 is already in use: stop the existing Part 3 server or run the manual
  command with another `--port`.
- Conversation appears old: choose **New conversation** in the UI or delete
  `data/conversations.sqlite3` while the server is stopped.

