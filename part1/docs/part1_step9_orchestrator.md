# Part 1 Step 9 - End-To-End LangGraph Workflow

## Purpose

LangGraph controls the Part 1 support email pipeline. `process_email()` remains
the backend entrypoint, but it now invokes a compiled state graph instead of
manually controlling the steps with `if/else` statements.

## Pipeline

```text
process_email(email_case)
  -> LangGraph
      -> DeepSeek Router Agent
      -> Critical Keyword Check
      -> if no match: DeepSeek Semantic Check
      -> if critical: HumanReviewSkill -> HumanHandoffTool
      -> if normal: Subagent Routing
      -> Skill Planning
      -> PDFSearchTool
      -> GroundedDraftSkill
      -> RefundGuardrailSkill
      -> Final Result + Audit Logs
```

## Output

The orchestrator returns:

- `status`: `drafted` or `human_review`.
- `critical_check`: result from the deterministic critical gate.
- `classification`: category decision for every valid case.
- `route`: selected subagent for non-critical cases.
- `skill_plan`: ordered skills used by the workflow.
- `search_result`: retrieved PDF evidence for non-critical cases.
- `guardrail`: refund guardrail result when applicable.
- `final_draft`: customer-facing draft when safe.
- `handoff_ticket`: human-agent ticket for critical cases.
- `audit_logs`: structured trace of key decisions.

## Design Note

The graph has explicit nodes and conditional edges, making each route visible
and testable. The public function keeps the same return type, so the web UI and
API do not need to change.
