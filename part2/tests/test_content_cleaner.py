import unittest

from web_summary_agent.content_cleaner import clean_page
from web_summary_agent.scraper import FetchedPage


def make_page(html: str) -> FetchedPage:
    return FetchedPage(
        requested_url="https://example.com/",
        final_url="https://example.com/article",
        status_code=200,
        content_type="text/html",
        charset="utf-8",
        html=html,
        bytes_downloaded=len(html.encode("utf-8")),
    )


class ContentCleanerTests(unittest.TestCase):
    def test_removes_navigation_scripts_sidebar_and_footer(self):
        page = make_page(
            """
            <html>
              <head>
                <title>Useful Python Guide</title>
                <style>.hidden { display: none; }</style>
                <script>window.tracking = true;</script>
              </head>
              <body>
                <header><p>Company logo and account menu</p></header>
                <nav><a href="/">Home</a><a href="/news">News</a></nav>
                <main>
                  <h1>Why Python is useful</h1>
                  <p>Python is a readable programming language used in many fields.</p>
                  <p>Its ecosystem supports web development, automation, and data science.</p>
                  <p>Beginners can learn its clear syntax while experienced teams can build production systems.</p>
                </main>
                <aside><p>Sponsored training advertisement goes here.</p></aside>
                <footer><p>Privacy policy and copyright information.</p></footer>
              </body>
            </html>
            """
        )

        cleaned = clean_page(page)

        self.assertEqual(cleaned.title, "Useful Python Guide")
        self.assertTrue(cleaned.used_primary_content)
        self.assertIn("Why Python is useful", cleaned.text)
        self.assertIn("data science", cleaned.text)
        self.assertNotIn("account menu", cleaned.text)
        self.assertNotIn("Home", cleaned.text)
        self.assertNotIn("Sponsored", cleaned.text)
        self.assertNotIn("Privacy policy", cleaned.text)
        self.assertNotIn("window.tracking", cleaned.text)

    def test_keeps_feature_headline_inside_page_header(self):
        page = make_page(
            """
            <html><body>
              <header role="banner">
                <p>Account controls and site search</p>
                <nav><p>Products Pricing Documentation</p></nav>
                <div class="about-banner">
                  <h1>Python is powerful and easy to learn</h1>
                  <p>These are reasons people enjoy using the language.</p>
                </div>
              </header>
            </body></html>
            """
        )

        cleaned = clean_page(page)

        self.assertIn("Python is powerful", cleaned.text)
        self.assertIn("reasons people enjoy", cleaned.text)
        self.assertNotIn("Account controls", cleaned.text)
        self.assertNotIn("Products Pricing", cleaned.text)

    def test_falls_back_to_body_blocks_without_main_element(self):
        page = make_page(
            """
            <html>
              <head><title>Simple Page</title></head>
              <body>
                <h1>Page heading</h1>
                <p>This useful paragraph exists without a main HTML element.</p>
              </body>
            </html>
            """
        )

        cleaned = clean_page(page)

        self.assertFalse(cleaned.used_primary_content)
        self.assertIn("Page heading", cleaned.text)
        self.assertIn("useful paragraph", cleaned.text)

    def test_removes_duplicate_content_blocks(self):
        page = make_page(
            """
            <html><body>
              <p>This paragraph appears twice on the webpage.</p>
              <p>This paragraph appears twice on the webpage.</p>
            </body></html>
            """
        )

        cleaned = clean_page(page)

        self.assertEqual(cleaned.duplicate_blocks_removed, 1)
        self.assertEqual(cleaned.text.count("appears twice"), 1)

    def test_removes_elements_marked_as_hidden(self):
        page = make_page(
            """
            <html><body>
              <p aria-hidden="true">Screen reader duplicate content is hidden.</p>
              <div hidden><p>Hidden promotional message goes here.</p></div>
              <p>This visible content should remain available.</p>
            </body></html>
            """
        )

        cleaned = clean_page(page)

        self.assertNotIn("duplicate content", cleaned.text)
        self.assertNotIn("promotional", cleaned.text)
        self.assertIn("visible content", cleaned.text)

    def test_removes_noise_class_names(self):
        page = make_page(
            """
            <html><body>
              <div class="cookie-banner"><p>Please accept all cookies now.</p></div>
              <section class="article-body">
                <p>The article contains useful information for the reader.</p>
              </section>
            </body></html>
            """
        )

        cleaned = clean_page(page)

        self.assertNotIn("cookies", cleaned.text)
        self.assertIn("useful information", cleaned.text)

    def test_removes_browser_fallback_notice(self):
        page = make_page(
            """
            <html><body>
              <p>Notice: This page displays a fallback because interactive scripts did not run.</p>
              <p>The useful article content remains available to readers.</p>
            </body></html>
            """
        )

        cleaned = clean_page(page)

        self.assertNotIn("displays a fallback", cleaned.text)
        self.assertIn("useful article", cleaned.text)

    def test_root_layout_classes_do_not_hide_wikipedia_content(self):
        page = make_page(
            """
            <html class="vector-feature-main-menu-disabled vector-toc-available">
              <head><title>Reborn! - Wikipedia</title></head>
              <body class="skin-vector sidebar-enabled">
                <main>
                  <h1>Reborn!</h1>
                  <p>Reborn is a Japanese manga series written by Akira Amano.</p>
                  <p>The story follows Tsuna as he trains to lead the Vongola family.</p>
                  <p>An anime television adaptation was broadcast for 203 episodes.</p>
                </main>
              </body>
            </html>
            """
        )

        cleaned = clean_page(page)

        self.assertEqual(cleaned.title, "Reborn! - Wikipedia")
        self.assertTrue(cleaned.used_primary_content)
        self.assertIn("Japanese manga series", cleaned.text)
        self.assertIn("anime television adaptation", cleaned.text)

    def test_removes_trailing_reference_sections(self):
        page = make_page(
            """
            <html><body><main>
              <h1>Article title</h1>
              <p>The article contains useful publication and story information.</p>
              <h2>References</h2>
              <p>Long citation title that should not enter the summary.</p>
              <h2>External links</h2>
              <p>Official website and database links.</p>
            </main></body></html>
            """
        )

        cleaned = clean_page(page)

        self.assertIn("useful publication", cleaned.text)
        self.assertNotIn("Long citation", cleaned.text)
        self.assertNotIn("Official website", cleaned.text)


if __name__ == "__main__":
    unittest.main()
