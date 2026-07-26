# Part 1: Support Email Agent
## Workflow and Agent
01. LangGraph - Connects the nodes, passes state and selects the next step.
02. Router Agent - Reads the email and selects its category.
03. BillingSubagent - Handles charges, payments, invoices and receipts.
04. RefundSubagent - Handles refunds, returns and cancellations.
05. TechnicalSubagent - Handles crashes, bugs and technical errors.
06. AccountSubagent - Handles login, password, profile and privacy questions.
07. ShippingSubagent - Handles delivery, tracking and package questions.
08. FeedbackSubagent - Handles suggestions, complaints and feedback.
## Skill
09. KnowledgeRetrievalSkill - Finds relevant information from the internal PDF.
10. GroundedDraftSkill - Creates a customer reply using retrieved PDF information.
11. RefundGuardrailSkill - Prevents refund claims that are not supported by the PDF.
12. HumanReviewSkill - Prepares critical or unsupported cases for human review.
## Tools
13. PDFSearchTool - Searches the internal PDF.
