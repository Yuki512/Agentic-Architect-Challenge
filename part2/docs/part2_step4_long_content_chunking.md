# Part 2 - Step 4: Long-Content Bottleneck

## Bottleneck

Passing an entire long webpage to one summarization call creates three problems:

- The content may exceed the model or summarizer context limit.
- Processing becomes slower and more expensive.
- Important information can be lost among repeated or unrelated text.

## Fix

`chunk_cleaned_page(cleaned_page)` divides useful content into sentence-aware
chunks after HTML cleaning.

Default limits:

- Maximum 180 words per chunk.
- Up to 20 words of whole-sentence overlap between neighboring chunks.
- Oversized individual sentences are split safely.

The overlap preserves context when a topic continues across a chunk boundary.
Every chunk includes an ID and exact word count for pipeline evidence.

## Step 4 flow

`CleanedPage -> sentence units -> bounded chunks -> ContentChunk[]`

Step 5 can summarize each chunk separately and combine only the useful results
into one concise answer.
