# 1. Initialize the system
Insert API key on env, then open bat file for each part 


# 2. Part 1 Email Customer Support Agent
![Part 1 Workflow](diagram/Part1flow.png)

### How Part 1 Works

1. **Customer Email**  
   The system receives an email from the customer.

2. **Input Validation**  
   The system checks that the email contains valid information and is not empty.

3. **Main Agent**  
   The Main Agent starts and controls the support process.

4. **Keyword Check**  
   The system searches for words connected to serious issues, such as data loss, security problems or service outages.

5. **DeepSeek Meaning Check**  
   If no keyword is found, DeepSeek checks whether the email describes a serious issue using different words.

6. **Human Review Skill**  
   If the issue is serious or unclear, the case is prepared for human review.

7. **Human Handoff Tool**  
   The system creates a handoff request for the support team.

8. **Router Classifier**  
   If the issue is not serious, the system identifies the email category.

9. **Specialist Subagent**  
   The email is sent to the agent responsible for that category.

10. **Skill Planning**  
    The specialist selects the steps and tools needed to answer the email.

11. **PDF Search Tool**  
    The system searches the internal PDF document.

12. **Retrieve from Knowledge Base**  
    Relevant information is collected from the PDF.

13. **Draft Skill**  
    DeepSeek uses the collected information to prepare a reply. A rule-based reply can be used when the API is unavailable.

14. **Refund Category Check**  
    The system checks whether the email is about a refund.

15. **Refund Guardrail**  
    A refund reply is checked to ensure it does not promise something that is not allowed.

16. **Output**  
    A reply that passes the checks is shown as the final output. A failed refund check is sent to the Human Review Skill.
