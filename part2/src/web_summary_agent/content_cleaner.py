from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import Iterable

from web_summary_agent.scraper import FetchedPage


EXCLUDED_TAGS = {
    "aside",
    "canvas",
    "dialog",
    "footer",
    "form",
    "nav",
    "noscript",
    "script",
    "style",
    "svg",
    "template",
}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
BLOCK_TAGS = {
    "blockquote",
    "dd",
    "dt",
    "figcaption",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "pre",
    "td",
    "th",
}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
PRIMARY_TAGS = {"article", "main"}
NOISE_ROLES = {
    "complementary",
    "contentinfo",
    "navigation",
    "search",
}
NOISE_TOKENS = {
    "advert",
    "breadcrumb",
    "cookie",
    "footer",
    "menu",
    "modal",
    "nav",
    "newsletter",
    "popup",
    "promo",
    "related",
    "share",
    "sidebar",
    "social",
}
HEADER_FEATURE_TOKENS = {"banner", "hero", "intro", "masthead"}
BOILERPLATE_PATTERNS = (
    re.compile(r"^notice:\s*this page displays a fallback\b", re.IGNORECASE),
    re.compile(r"^skip to (?:main )?content$", re.IGNORECASE),
    re.compile(r"^back to top$", re.IGNORECASE),
)
TRAILING_SECTION_HEADINGS = {
    "bibliography",
    "citations",
    "external links",
    "further reading",
    "notes",
    "references",
}
MIN_PRIMARY_WORDS = 25


@dataclass(frozen=True)
class ContentBlock:
    tag: str
    text: str
    is_primary: bool


@dataclass(frozen=True)
class CleanedPage:
    source_url: str
    title: str
    text: str
    blocks: tuple[str, ...]
    word_count: int
    block_count: int
    used_primary_content: bool
    duplicate_blocks_removed: int


class UsefulContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[ContentBlock] = []
        self.duplicate_blocks_removed = 0
        self._element_stack: list[tuple[str, bool, bool, bool, bool]] = []
        self._block_tag: str | None = None
        self._block_parts: list[str] = []
        self._block_is_primary = False
        self._title_parts: list[str] = []
        self._inside_title = False
        self._ignore_trailing_sections = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        attribute_map = {name.lower(): value or "" for name, value in attrs}
        excluded = self._is_excluded(tag, attribute_map)
        primary = tag in PRIMARY_TAGS
        identity = f"{attribute_map.get('id', '')} {attribute_map.get('class', '')}".lower()
        identity_tokens = set(re.findall(r"[a-z]+", identity))
        header_feature = bool(identity_tokens & HEADER_FEATURE_TOKENS)

        if tag not in VOID_TAGS:
            self._element_stack.append(
                (tag, excluded, primary, tag == "header", header_feature)
            )

        if self._is_inside_excluded():
            return

        if tag == "title":
            self._inside_title = True
            return

        if tag in BLOCK_TAGS:
            if self._is_inside_header() and not self._is_inside_header_feature():
                return
            self._finish_block()
            self._block_tag = tag
            self._block_parts = []
            self._block_is_primary = self._is_inside_primary()

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag == self._block_tag:
            self._finish_block()
        if tag == "title":
            self._inside_title = False
            self.title = _normalize_text(" ".join(self._title_parts))

        for index in range(len(self._element_stack) - 1, -1, -1):
            if self._element_stack[index][0] == tag:
                del self._element_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._is_inside_excluded():
            return
        if self._inside_title:
            self._title_parts.append(data)
        if self._block_tag:
            self._block_parts.append(data)

    def close(self) -> None:
        super().close()
        self._finish_block()
        if not self.title:
            self.title = _normalize_text(" ".join(self._title_parts))

    def _finish_block(self) -> None:
        if not self._block_tag:
            return

        text = _normalize_text(" ".join(self._block_parts))
        if (
            self._block_tag in HEADING_TAGS
            and text.casefold().rstrip(":") in TRAILING_SECTION_HEADINGS
        ):
            self._ignore_trailing_sections = True

        if (
            text
            and not self._ignore_trailing_sections
            and not _is_boilerplate_text(text)
            and (self._block_tag in HEADING_TAGS or len(text.split()) >= 3)
        ):
            self.blocks.append(
                ContentBlock(
                    tag=self._block_tag,
                    text=text,
                    is_primary=self._block_is_primary,
                )
            )

        self._block_tag = None
        self._block_parts = []
        self._block_is_primary = False

    def _is_inside_excluded(self) -> bool:
        return any(item[1] for item in self._element_stack)

    def _is_inside_primary(self) -> bool:
        return any(item[2] for item in self._element_stack)

    def _is_inside_header(self) -> bool:
        return any(item[3] for item in self._element_stack)

    def _is_inside_header_feature(self) -> bool:
        return any(item[4] for item in self._element_stack)

    @staticmethod
    def _is_excluded(tag: str, attrs: dict[str, str]) -> bool:
        if tag in EXCLUDED_TAGS or "hidden" in attrs:
            return True
        if attrs.get("aria-hidden", "").lower() == "true":
            return True
        if attrs.get("role", "").lower() in NOISE_ROLES:
            return True
        if tag in {"html", "body"}:
            return False

        identity = f"{attrs.get('id', '')} {attrs.get('class', '')}".lower()
        tokens = set(re.findall(r"[a-z]+", identity))
        return bool(tokens & NOISE_TOKENS)


def clean_page(page: FetchedPage) -> CleanedPage:
    parser = UsefulContentParser()
    parser.feed(page.html)
    parser.close()

    unique_blocks, duplicates_removed = _deduplicate(parser.blocks)
    primary_blocks = [block for block in unique_blocks if block.is_primary]
    primary_word_count = _count_words(block.text for block in primary_blocks)
    use_primary = primary_word_count >= MIN_PRIMARY_WORDS
    selected_blocks = primary_blocks if use_primary else unique_blocks

    text = "\n\n".join(block.text for block in selected_blocks)
    return CleanedPage(
        source_url=page.final_url,
        title=parser.title,
        text=text,
        blocks=tuple(block.text for block in selected_blocks),
        word_count=_count_words([text]),
        block_count=len(selected_blocks),
        used_primary_content=use_primary,
        duplicate_blocks_removed=duplicates_removed,
    )


def _deduplicate(
    blocks: Iterable[ContentBlock],
) -> tuple[list[ContentBlock], int]:
    unique_blocks: list[ContentBlock] = []
    seen: set[str] = set()
    duplicates_removed = 0

    for block in blocks:
        key = re.sub(r"\W+", " ", block.text).strip().lower()
        if key in seen:
            duplicates_removed += 1
            continue
        seen.add(key)
        unique_blocks.append(block)

    return unique_blocks, duplicates_removed


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_boilerplate_text(value: str) -> bool:
    return any(pattern.search(value) for pattern in BOILERPLATE_PATTERNS)


def _count_words(values: Iterable[str]) -> int:
    return sum(len(value.split()) for value in values)
