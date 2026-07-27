# Part 2 - Step 3: Useful Content Cleaner

## Goal

Convert raw webpage HTML into useful readable text before summarization.

## Cleaner

`clean_page(fetched_page)` uses a structured HTML parser. It does not attempt to
clean HTML with one large regular expression.

The cleaner removes:

- Scripts, styles, templates, SVG, and canvas content.
- Navigation, footer, form, and sidebar content.
- Non-feature header blocks while preserving genuine hero or introduction text.
- Hidden and `aria-hidden` elements.
- Common cookie, advertisement, menu, social, and promotional containers.
- Repeated text blocks.
- Common fallback notices, skip links, and back-to-top text.

It keeps:

- Page title.
- Headings.
- Paragraphs.
- Useful list, table, quote, and preformatted text.

When a page contains enough content inside `<main>` or `<article>`, that content is
preferred. Pages without semantic main elements fall back to all useful body text.

## Step 3 flow

`FetchedPage -> UsefulContentParser -> deduplicate -> CleanedPage`

Step 4 will handle the remaining long-content bottleneck by splitting cleaned text
into manageable chunks before summarization.
