# Part 1 Step 3 - Router Agent And Email Classification

## Purpose

The DeepSeek Router Agent labels every support email before the critical issue
check. This means a critical case still shows a useful category, such as
`Technical`, when it is sent to a human. Only non-critical cases continue to the
matching specialized subagent.

## Categories

The router supports these categories:

- `Billing`
- `Technical`
- `Refund`
- `Shipping`
- `Account`
- `Feedback`
- `Other`

## Router Output

The classifier returns:

- `primary_category`: main support category.
- `categories`: all detected categories ordered by score.
- `confidence`: simple confidence score from keyword match strength.
- `scores`: per-category keyword score.
- `reason`: short explanation for observability.
- `recommended_subagent`: target subagent, such as `RefundSubagent`.

## Design Note

DeepSeek returns strict JSON containing only supported categories. The response
is validated before LangGraph accepts it. If the API key is missing, the API is
unavailable, or the response is invalid, the existing deterministic keyword
classifier supplies the category instead. This hybrid approach improves
understanding of varied wording while keeping routing available and testable.
