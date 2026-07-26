# 1. Initialize the system
Insert API key on env, then open bat file for each part 


# 2. Part 1 Email Customer Support Agent
### System workflow (will explain later)
![Part 1 Workflow](diagram/Part1flow.png)




### Demo Result (Example 1)
![Part 1 Workflow](diagram/part1_demo1.png)
The right panel shows how the email was processed:

- **Status: Draft ready**  
  The system successfully prepared a reply.

- **Critical issue: No**  
  The email was not serious, so it did not require human review.

- **Category: Refund**  
  The system identified the email as a refund request.

- **Subagent: RefundSubagent**  
  The refund agent was selected to handle the request.

- **Response writer: DeepSeek**  
  DeepSeek wrote the customer reply.

  ### (Example 2 - Data Lost)

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
