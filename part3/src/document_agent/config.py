from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_openai import ChatOpenAI
from pydantic import SecretStr


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = WORKSPACE_ROOT / ".env"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_TIMEZONE = "Asia/Singapore"


class AgentConfigurationError(ValueError):
    """Raised when Part 3 cannot create its configured LLM client."""


@dataclass(frozen=True)
class AgentConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    timezone_name: str
    max_output_tokens: int = 2_048


def load_agent_config(env_path: Path = ENV_PATH) -> AgentConfig:
    file_values = _read_env_file(env_path)
    provider = _setting("QA_PROVIDER", file_values, "deepseek").lower()
    if provider != "deepseek":
        raise AgentConfigurationError(
            "QA_PROVIDER must be 'deepseek' for Part 3."
        )

    timeout_value = _setting(
        "DEEPSEEK_TIMEOUT_SECONDS",
        file_values,
        "45",
    )
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise AgentConfigurationError(
            "DEEPSEEK_TIMEOUT_SECONDS must be a number."
        ) from exc
    if not 5 <= timeout_seconds <= 120:
        raise AgentConfigurationError(
            "DEEPSEEK_TIMEOUT_SECONDS must be between 5 and 120."
        )

    timezone_name = _setting(
        "PART3_TIMEZONE",
        file_values,
        DEFAULT_TIMEZONE,
    )
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise AgentConfigurationError(
            f"PART3_TIMEZONE is not recognized: {timezone_name}"
        ) from exc

    return AgentConfig(
        provider=provider,
        api_key=_setting("DEEPSEEK_API_KEY", file_values, ""),
        base_url=_setting(
            "DEEPSEEK_BASE_URL",
            file_values,
            DEFAULT_BASE_URL,
        ).rstrip("/"),
        model=_setting(
            "DEEPSEEK_MODEL",
            file_values,
            DEFAULT_MODEL,
        ),
        timeout_seconds=timeout_seconds,
        timezone_name=timezone_name,
    )


def build_chat_model(config: AgentConfig) -> ChatOpenAI:
    if not config.api_key:
        raise AgentConfigurationError(
            "DEEPSEEK_API_KEY is not configured for Part 3."
        )
    os.environ["PART3_TIMEZONE"] = config.timezone_name
    return ChatOpenAI(
        api_key=SecretStr(config.api_key),
        base_url=config.base_url,
        model=config.model,
        temperature=0,
        timeout=config.timeout_seconds,
        max_retries=1,
        max_tokens=config.max_output_tokens,
        extra_body={"thinking": {"type": "disabled"}},
    )


def _setting(
    name: str,
    file_values: dict[str, str],
    default: str,
) -> str:
    environment_value = os.environ.get(name, "").strip()
    if environment_value:
        return environment_value
    return file_values.get(name, default).strip()


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {
            "'",
            '"',
        }:
            value = value[1:-1]
        if name:
            values[name] = value
    return values
