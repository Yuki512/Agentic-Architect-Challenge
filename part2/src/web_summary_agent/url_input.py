from dataclasses import dataclass
import ipaddress
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


DEFAULT_MAX_SUMMARY_WORDS = 120
MIN_SUMMARY_WORDS = 40
MAX_SUMMARY_WORDS = 250


@dataclass(frozen=True)
class ScrapeRequest:
    case_id: str
    url: str
    focus: str
    max_summary_words: int = DEFAULT_MAX_SUMMARY_WORDS


def load_scrape_requests(path: str | Path) -> list[ScrapeRequest]:
    source_path = Path(path)
    raw_requests = json.loads(source_path.read_text(encoding="utf-8"))

    if not isinstance(raw_requests, list) or not raw_requests:
        raise ValueError("URL input file must contain a non-empty JSON list.")

    return [parse_scrape_request(item, index) for index, item in enumerate(raw_requests)]


def validate_public_url(value: str) -> str:
    url = value.strip()
    if not url:
        raise ValueError("URL is required.")
    if len(url) > 2048:
        raise ValueError("URL must not exceed 2048 characters.")

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("URL must use http or https.")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("URL must not include login credentials.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("URL must point to a public website.")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address is not None and not address.is_global:
        raise ValueError("URL must not point to a private or local IP address.")

    normalized_path = parsed.path or "/"
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            normalized_path,
            parsed.query,
            "",
        )
    )


def parse_scrape_request(value: Any, index: int = 0) -> ScrapeRequest:
    if not isinstance(value, dict):
        raise ValueError(f"URL input at index {index} must be a JSON object.")

    case_id = str(value.get("case_id") or "").strip()
    if not case_id:
        raise ValueError(f"URL input at index {index} requires case_id.")

    focus = str(value.get("focus") or "").strip()
    if not focus:
        raise ValueError(f"URL input {case_id} requires a summary focus.")

    max_summary_words = _parse_word_limit(
        value.get("max_summary_words", DEFAULT_MAX_SUMMARY_WORDS),
        case_id,
    )

    return ScrapeRequest(
        case_id=case_id,
        url=validate_public_url(str(value.get("url") or "")),
        focus=focus,
        max_summary_words=max_summary_words,
    )


def _parse_word_limit(value: Any, case_id: str) -> int:
    try:
        word_limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"URL input {case_id} has an invalid max_summary_words.") from exc

    if not MIN_SUMMARY_WORDS <= word_limit <= MAX_SUMMARY_WORDS:
        raise ValueError(
            f"URL input {case_id} max_summary_words must be between "
            f"{MIN_SUMMARY_WORDS} and {MAX_SUMMARY_WORDS}."
        )
    return word_limit
