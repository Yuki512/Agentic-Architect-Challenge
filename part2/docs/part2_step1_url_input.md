# Part 2 - Step 1: URL Input

## Goal

Create a safe and clear input contract for the website scraping and summarization
pipeline.

## Real test page

- URL: `https://en.wikipedia.org/wiki/Reborn!`
- Reason: It is a long public article with useful content plus navigation,
  contents, references, tables, and footer noise. It tests scraping, cleaning,
  chunking, focus ranking, and concise summarization.

## Input fields

- `case_id`: identifies the test request.
- `url`: the public HTTP or HTTPS page to process.
- `focus`: tells the summarizer which information is useful.
- `max_summary_words`: limits the final summary to 40-250 words.

## Validation

The input layer rejects:

- Missing or unsupported URL schemes.
- Localhost, `.local` hosts, and private IP addresses.
- URLs containing usernames or passwords.
- Missing case IDs or summary focus.
- Summary limits outside 40-250 words.

The URL fragment is removed because it is not sent to the web server.

## Step 1 flow

`sample_urls.json -> load_scrape_requests -> validate_public_url -> ScrapeRequest`

No website content is downloaded in this step. Step 2 will add the scraping tool
that fetches this validated public URL.
