from dataclasses import asdict, dataclass
from typing import Any, Callable

from web_summary_agent.chunker import ContentChunk, chunk_cleaned_page
from web_summary_agent.content_cleaner import clean_page
from web_summary_agent.llm_summarizer import summarize_with_configured_provider
from web_summary_agent.scraper import FetchedPage, fetch_web_page
from web_summary_agent.summarizer import SummaryResult
from web_summary_agent.url_input import ScrapeRequest, parse_scrape_request


PIPELINE_COMPONENTS = (
    "WebsiteScraperTool",
    "UsefulContentCleaner",
    "LongContentChunkingSkill",
    "GroundedSummarizationSkill",
    "ConciseSummaryGuardrail",
)
DEEPSEEK_PIPELINE_COMPONENTS = (
    "WebsiteScraperTool",
    "UsefulContentCleaner",
    "LongContentChunkingSkill",
    "DeepSeekLLMSummarizationSkill",
    "ConciseSummaryGuardrail",
)
GEMINI_PIPELINE_COMPONENTS = (
    "WebsiteScraperTool",
    "UsefulContentCleaner",
    "LongContentChunkingSkill",
    "GeminiLLMSummarizationSkill",
    "ConciseSummaryGuardrail",
)

SummaryFunction = Callable[..., SummaryResult]


@dataclass(frozen=True)
class FetchProof:
    final_url: str
    status_code: int
    content_type: str
    bytes_downloaded: int


@dataclass(frozen=True)
class CleaningProof:
    title: str
    useful_words: int
    useful_blocks: int
    used_primary_content: bool
    duplicate_blocks_removed: int


@dataclass(frozen=True)
class ChunkProof:
    chunk_id: str
    word_count: int


@dataclass(frozen=True)
class WebSummaryPipelineResult:
    status: str
    case_id: str
    requested_url: str
    focus: str
    fetch: FetchProof
    cleaning: CleaningProof
    chunks: tuple[ChunkProof, ...]
    summary: SummaryResult
    components: tuple[str, ...]


def process_scrape_request(
    request: ScrapeRequest,
    *,
    fetcher: Callable[[str], FetchedPage] = fetch_web_page,
    summarizer: SummaryFunction = summarize_with_configured_provider,
) -> WebSummaryPipelineResult:
    fetched_page = fetcher(request.url)
    cleaned_page = clean_page(fetched_page)
    chunks = chunk_cleaned_page(cleaned_page)
    summary = summarizer(
        chunks,
        focus=request.focus,
        max_words=request.max_summary_words,
    )

    return WebSummaryPipelineResult(
        status="summary_ready",
        case_id=request.case_id,
        requested_url=request.url,
        focus=request.focus,
        fetch=FetchProof(
            final_url=fetched_page.final_url,
            status_code=fetched_page.status_code,
            content_type=fetched_page.content_type,
            bytes_downloaded=fetched_page.bytes_downloaded,
        ),
        cleaning=CleaningProof(
            title=cleaned_page.title,
            useful_words=cleaned_page.word_count,
            useful_blocks=cleaned_page.block_count,
            used_primary_content=cleaned_page.used_primary_content,
            duplicate_blocks_removed=cleaned_page.duplicate_blocks_removed,
        ),
        chunks=_chunk_proof(chunks),
        summary=summary,
        components=_components_for_provider(summary.provider),
    )


def process_url_payload(
    payload: dict[str, Any],
    *,
    fetcher: Callable[[str], FetchedPage] = fetch_web_page,
    summarizer: SummaryFunction = summarize_with_configured_provider,
) -> dict[str, Any]:
    request = parse_scrape_request(payload)
    result = process_scrape_request(
        request,
        fetcher=fetcher,
        summarizer=summarizer,
    )
    return asdict(result)


def _chunk_proof(chunks: tuple[ContentChunk, ...]) -> tuple[ChunkProof, ...]:
    return tuple(
        ChunkProof(
            chunk_id=chunk.chunk_id,
            word_count=chunk.word_count,
        )
        for chunk in chunks
    )


def _components_for_provider(provider: str) -> tuple[str, ...]:
    if provider == "deepseek":
        return DEEPSEEK_PIPELINE_COMPONENTS
    if provider == "gemini":
        return GEMINI_PIPELINE_COMPONENTS
    return PIPELINE_COMPONENTS
