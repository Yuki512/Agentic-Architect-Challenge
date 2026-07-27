# Part 1 Step 6 - Tools Layer

## Purpose

Tools are the lowest-level executable actions in the system. Agents and subagents decide what should happen. Skills plan the workflow. Tools perform the concrete work.

## Implemented Tools

| Tool | Purpose |
| --- | --- |
| `PDFSearchTool` | Extracts text from the FAQ PDF and returns relevant evidence passages. |
| `HumanHandoffTool` | Creates a structured handoff ticket for urgent cases. |
| `AuditLoggingTool` | Creates structured audit events for observability. |

## Tool Flow

- Normal emails use `PDFSearchTool` after classification and subagent routing.
- Critical emails bypass normal response drafting and use `HumanHandoffTool`.
- Important decisions can create an `AuditLoggingTool` entry so the process is explainable.

## Design Note

The PDF search tool is deterministic for Part 1. This keeps testing simple and avoids requiring an API key. In production, the same tool interface could be replaced with vector search over PDFs, FAQs, and internal policy pages.
