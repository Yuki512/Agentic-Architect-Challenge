from dataclasses import dataclass
import ipaddress
import socket
from typing import Any
import zlib
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from web_summary_agent.url_input import validate_public_url


DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_MAX_BYTES = 2_000_000
ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
USER_AGENT = "WebSummaryAgent/1.0 (developer exercise)"


class ScrapeError(RuntimeError):
    """Raised when a webpage cannot be downloaded safely."""


@dataclass(frozen=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    charset: str
    html: str
    bytes_downloaded: int


class PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> Request | None:
        safe_url = validate_public_url(new_url)
        _ensure_public_host(safe_url)
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            safe_url,
        )


def fetch_web_page(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    opener: Any | None = None,
) -> FetchedPage:
    requested_url = validate_public_url(url)
    _ensure_public_host(requested_url)

    http_opener = opener or build_opener(PublicRedirectHandler())
    request = Request(
        requested_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Encoding": "gzip, deflate",
        },
    )

    try:
        with http_opener.open(request, timeout=timeout) as response:
            final_url = validate_public_url(response.geturl())
            _ensure_public_host(final_url)

            status_code = int(getattr(response, "status", response.getcode()))
            if not 200 <= status_code < 300:
                raise ScrapeError(f"Website returned HTTP {status_code}.")

            content_type = response.headers.get_content_type().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise ScrapeError(
                    f"Expected an HTML page but received {content_type or 'unknown content'}."
                )

            raw_body = response.read(max_bytes + 1)
            if len(raw_body) > max_bytes:
                raise ScrapeError(
                    f"Page exceeds the {max_bytes:,}-byte download limit."
                )

            content_encoding = response.headers.get("Content-Encoding", "identity")
            raw_html = _decompress_body(raw_body, content_encoding, max_bytes)
            charset = response.headers.get_content_charset() or "utf-8"
            html = _decode_html(raw_html, charset)
    except ScrapeError:
        raise
    except HTTPError as exc:
        raise ScrapeError(f"Website returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise ScrapeError(f"Could not download the webpage: {exc}") from exc
    except ValueError as exc:
        raise ScrapeError(str(exc)) from exc

    return FetchedPage(
        requested_url=requested_url,
        final_url=final_url,
        status_code=status_code,
        content_type=content_type,
        charset=charset,
        html=html,
        bytes_downloaded=len(raw_body),
    )


def _ensure_public_host(url: str) -> None:
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if not hostname:
        raise ScrapeError("URL must include a hostname.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        address_info = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ScrapeError(f"Could not resolve website hostname: {hostname}.") from exc

    addresses = {item[4][0] for item in address_info}
    if not addresses:
        raise ScrapeError(f"Could not resolve website hostname: {hostname}.")

    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise ScrapeError("Website resolved to a private or local IP address.")


def _decode_html(raw_html: bytes, charset: str) -> str:
    try:
        return raw_html.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return raw_html.decode("utf-8", errors="replace")


def _decompress_body(
    raw_body: bytes,
    content_encoding: str,
    max_bytes: int,
) -> bytes:
    encoding = content_encoding.strip().lower()
    if encoding in {"", "identity"}:
        return raw_body
    if encoding == "gzip":
        return _bounded_decompress(raw_body, 16 + zlib.MAX_WBITS, max_bytes)
    if encoding == "deflate":
        try:
            return _bounded_decompress(raw_body, zlib.MAX_WBITS, max_bytes)
        except zlib.error:
            return _bounded_decompress(raw_body, -zlib.MAX_WBITS, max_bytes)
    raise ScrapeError(f"Unsupported content encoding: {encoding}.")


def _bounded_decompress(raw_body: bytes, window_bits: int, max_bytes: int) -> bytes:
    decompressor = zlib.decompressobj(window_bits)
    decoded = decompressor.decompress(raw_body, max_bytes + 1)
    if len(decoded) > max_bytes or decompressor.unconsumed_tail:
        raise ScrapeError(
            f"Decompressed page exceeds the {max_bytes:,}-byte download limit."
        )

    remaining = max_bytes + 1 - len(decoded)
    decoded += decompressor.flush(remaining)
    if len(decoded) > max_bytes:
        raise ScrapeError(
            f"Decompressed page exceeds the {max_bytes:,}-byte download limit."
        )
    return decoded
