# Part 3 Demo and Interview Guide

## Five-minute demonstration

Open `open_part3.bat`, then keep the chat, source document, and processing trace
visible.

### 1. Prove conversation memory

Ask:

```text
My name is Hojun.
```

Then ask:

```text
What is my name?
```

Expected proof: the agent recalls the name and the same thread remains visible
after a browser refresh.

### 2. Prove grounded direct lookup without a tool

Ask:

```text
What is the maximum hotel room rate in Singapore?
```

Expected proof: the answer cites the accommodation section. The trace shows
retrieved evidence and **No tool used**.

### 3. Prove selective calculator use and follow-up context

Ask:

```text
How much is that for three nights?
```

Expected proof: the agent uses the previous hotel context, calls the calculator,
and shows the tool event in the trace.

### 4. Prove selective date-tool use

Ask:

```text
If I return on 2026-08-10, what is my claim deadline?
```

Expected proof: the date tool adds the policy's 10 calendar days and the answer
cites the receipts and deadlines section.

### 5. Prove graceful refusal

Ask:

```text
Does Nimbus reimburse pet boarding while I travel?
```

Expected proof: the agent says the document does not provide this information
instead of inventing a policy.

## Interview explanation

Use this short narrative:

> I built Part 3 as an explicit LangGraph workflow rather than a single model
> call. Each turn updates SQLite-backed memory, retrieves relevant PDF sections,
> lets the model decide whether a bounded calculator or date tool is necessary,
> and validates the final answer against retrieved citation IDs. The UI exposes
> evidence and tool traces so the decision path is observable without revealing
> hidden chain-of-thought.

## Likely questions

**Why LangGraph?**

It provides explicit state transitions, tool routing, retry limits, and durable
checkpoints. Those behaviors are easier to test than an implicit prompt-only
agent.

**Why BM25 instead of a vector database?**

The sample corpus has only nine compact sections. BM25 is deterministic, local,
fast, and sufficient. Hybrid retrieval is the scale-up path for a larger
knowledge base.

**Why SQLite instead of PostgreSQL?**

This is a local single-user prototype. SQLite minimizes setup and is supported
directly by the LangGraph checkpointer. PostgreSQL becomes appropriate for
multiple instances, concurrent users, centralized operations, and stronger
access controls.

**How do you prevent hallucination?**

The model receives retrieved policy sections as its only policy source. Policy
claims require exact retrieved citation IDs. Unsupported answers, invented
citations, and answers without evidence are blocked; one citation-repair attempt
is allowed.

**How does the agent decide to use a tool?**

DeepSeek receives structured calculator and date tool definitions with automatic
tool choice. Direct lookups should not call a tool. Arithmetic and date
questions can trigger one, and the graph limits the loop to two iterations.

**What would you change for production?**

Use authenticated FastAPI endpoints, PostgreSQL checkpoints, asynchronous model
calls, hybrid retrieval, document lifecycle management, centralized telemetry,
rate limiting, evaluation datasets, and human review for high-impact decisions.

## Honest limitations

- One fixed sample document is loaded at startup.
- Retrieval is lexical rather than semantic.
- Name memory uses controlled pattern extraction.
- SQLite and the standard-library HTTP server target a local demonstration.
- Live answer quality and availability still depend on the configured model API.

Naming these limits clearly is stronger than presenting the prototype as a
production service.

