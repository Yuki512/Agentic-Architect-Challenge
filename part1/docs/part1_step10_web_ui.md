# Part 1 Step 10 - Simple Web UI

## Purpose

The web UI simulates the support inbox intake step. A user can paste a customer email or choose a mock case, then run the full Part 1 pipeline from the browser.

## UI Flow

1. Enter customer name, contact count, subject, and email body.
2. Click `Process Email`.
3. The UI calls the local backend endpoint.
4. The result displays:
   - critical status
   - category
   - selected subagent
   - guardrail status
   - final draft or human handoff summary
   - PDF evidence
   - skill plan
   - audit trail

## Backend Endpoint

```text
POST /api/process
```

The endpoint calls:

```python
process_email(email_case)
```

and returns the serialized pipeline result.

## Design Note

This UI is intentionally a local prototype. In production, the same backend pipeline could sit behind a support inbox integration such as Zendesk, Freshdesk, Gmail, or Intercom.
