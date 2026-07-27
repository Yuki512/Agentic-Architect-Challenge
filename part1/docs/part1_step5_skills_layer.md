# Part 1 Step 5 - Skills Layer

## Purpose

The skills layer sits between specialized subagents and low-level tools. A subagent chooses the skill it needs, and the skill defines the reusable workflow, rules, and tools required to complete that task.

## Skills

| Skill | Purpose | Planned tools |
| --- | --- | --- |
| `KnowledgeRetrievalSkill` | Finds relevant FAQ evidence before drafting. | `PDFSearchTool` |
| `GroundedDraftSkill` | Writes a concise reply using retrieved evidence. | `DraftBuilderTool` |
| `RefundGuardrailSkill` | Blocks unsupported refund policy claims. | `RefundEvidenceCheckTool` |
| `HumanReviewSkill` | Prepares critical or unsupported cases for a human agent. | `HumanHandoffTool`, `AuditLoggingTool` |

## Design Rule

A skill is not another agent. In this project, a skill is a reusable workflow capability. It receives a task from a subagent, follows its rules, and chooses the tools needed for that workflow.

## Example

For a refund email:

1. `RefundSubagent` receives the routed case.
2. It uses `KnowledgeRetrievalSkill` to find PDF evidence.
3. It uses `GroundedDraftSkill` to draft a reply.
4. It uses `RefundGuardrailSkill` to confirm the refund answer is supported.

For a critical email:

1. The critical gate detects a required handoff trigger.
2. The system bypasses normal subagents.
3. It uses `HumanReviewSkill` to prepare a human-agent summary.
