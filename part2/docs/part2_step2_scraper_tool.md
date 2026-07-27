# Part 2 - Step 2: Website Scraper Tool

## Goal

Download the HTML for a validated public webpage and return structured metadata
for later cleaning and summarization.

## Tool

`fetch_web_page(url)` performs the website download.

It returns:

- Requested and final URLs.
- HTTP status.
- Content type and character encoding.
- Raw HTML.
- Number of downloaded bytes.

## Safety and reliability

- Only public HTTP and HTTPS URLs are accepted.
- DNS results are checked to prevent access to private or local IP addresses.
- Redirect destinations receive the same public URL checks.
- Only HTML and XHTML responses are accepted.
- Downloads stop at 2,000,000 bytes.
- Gzip and deflate responses are decompressed with the same 2,000,000-byte limit.
- Requests time out after 15 seconds.
- Character encoding failures fall back safely to UTF-8.

## Step 2 flow

`ScrapeRequest -> WebsiteScraperTool -> FetchedPage`

This step intentionally keeps the raw HTML. Step 3 will remove menus, scripts,
styles, repeated links, advertisements, and footer content before summarization.
