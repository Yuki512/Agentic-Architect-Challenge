# 1. Initialize the system
Insert API key on env, then open bat file for each part 


# 2. Part 1 Email Customer Support Agent
### System workflow (will explain later)
![Part 1 Workflow](diagram/Part1flow.png)




### Demo Result (Example 1 - Category - Billing)
![Part 1 Workflow](diagram/part1_demo1.png)
The right panel shows how the email was processed:
- **Critical issue: No**  
  The request is not a critical issue, so it continues through the normal process.

- **Category: Billing**  
  The system identifies the email as a billing problem.

- **Subagent: BillingSubagent**  
  The billing agent is selected to handle the request.

- **KnowledgeRetrievalSkill**  
  The system searches the internal FAQ for information about duplicate charges.

- **GroundedDraftSkill**  
  DeepSeek prepares a reply using the billing information found in the FAQ.

- **Refund guardrail: Not applied**  
  The email is classified as billing rather than a refund request.

- **Response writer: DeepSeek**  
  DeepSeek asks the customer for the information needed to check both charges.

- **FAQ evidence**  
  The billing FAQ explains what information to collect and how duplicate charges are handled.

- **Final result: Draft ready**  
  The system prepares a reply for the customer.



### (Example 2 -  Critical Data-Loss Issue)
![Part 1 Workflow](diagram/part1_demo2.png)
- **Critical issue: Yes**  
  The system detects the phrase “data loss” as a serious issue.

- **Category: Not used**  
  The system stops the normal classification process.

- **Subagent: HumanReview**  
  The case is sent directly to human review.

- **HumanReviewSkill**  
  This skill prepares the customer’s issue for the support team.

- **Response writer: Not used**  
  DeepSeek does not create an automatic customer reply.

- **Refund guardrail: Not used**  
  This is not a refund request, and the normal process was skipped.

- **FAQ evidence: Not used**  
  The system does not search the FAQ because the critical issue requires immediate human attention.

- **Final result: Human review required**  
  The support team must investigate the possible data loss.

### (Example 3 - Reduce hallucination for refund policy)
![Part 1 Workflow](diagram/part1_demo3.png)
- **Critical issue: No**  
  The request is not an emergency.

- **Category: Refund**  
  The system identifies it as a refund request.

- **Subagent: RefundSubagent**  
  The refund agent processes the request.

- **KnowledgeRetrievalSkill**  
  The system searches the FAQ for the refund rules.

- **GroundedDraftSkill**  
  The system tries to prepare a reply using the available FAQ information.

- **Refund guardrail: Blocked**  
  The FAQ does not support promising a refund after 90 days for a used product.

- **HumanReviewSkill**  
  The case is prepared for the support team to review.

- **Response writer: Human review template**  
  A safe message is returned instead of DeepSeek guessing the refund policy.

- **Final result: Human review required**  
  The customer is informed that the support team will review the case.
