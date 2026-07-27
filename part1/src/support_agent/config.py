from dataclasses import dataclass
import os
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = WORKSPACE_ROOT / ".env"


@dataclass(frozen=True)
class DraftLLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float

    @property
    def deepseek_enabled(self) -> bool:
        return self.provider == "deepseek" and bool(self.api_key)


def load_draft_llm_config(env_path: Path = ENV_PATH) -> DraftLLMConfig:
    file_values = _read_env_file(env_path)
    provider = _setting("DRAFT_PROVIDER", file_values, "deterministic").lower()
    if provider not in {"deepseek", "deterministic"}:
        raise ValueError(
            "DRAFT_PROVIDER must be either 'deepseek' or 'deterministic'."
        )

    timeout_value = _setting("DEEPSEEK_TIMEOUT_SECONDS", file_values, "45")
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be a number.") from exc
    if not 5 <= timeout_seconds <= 120:
        raise ValueError("DEEPSEEK_TIMEOUT_SECONDS must be between 5 and 120.")

    return DraftLLMConfig(
        provider=provider,
        api_key=_setting("DEEPSEEK_API_KEY", file_values, ""),
        base_url=_setting(
            "DEEPSEEK_BASE_URL",
            file_values,
            "https://api.deepseek.com",
        ).rstrip("/"),
        model=_setting(
            "DEEPSEEK_MODEL",
            file_values,
            "deepseek-v4-flash",
        ),
        timeout_seconds=timeout_seconds,
    )


def load_router_llm_config(env_path: Path = ENV_PATH) -> DraftLLMConfig:
    file_values = _read_env_file(env_path)
    default_provider = _setting(
        "DRAFT_PROVIDER",
        file_values,
        "deterministic",
    )
    provider = _setting(
        "ROUTER_PROVIDER",
        file_values,
        default_provider,
    ).lower()
    if provider not in {"deepseek", "deterministic"}:
        raise ValueError(
            "ROUTER_PROVIDER must be either 'deepseek' or 'deterministic'."
        )

    timeout_value = _setting(
        "DEEPSEEK_TIMEOUT_SECONDS",
        file_values,
        "45",
    )
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise ValueError(
            "DEEPSEEK_TIMEOUT_SECONDS must be a number."
        ) from exc
    if not 5 <= timeout_seconds <= 120:
        raise ValueError(
            "DEEPSEEK_TIMEOUT_SECONDS must be between 5 and 120."
        )

    return DraftLLMConfig(
        provider=provider,
        api_key=_setting("DEEPSEEK_API_KEY", file_values, ""),
        base_url=_setting(
            "DEEPSEEK_BASE_URL",
            file_values,
            "https://api.deepseek.com",
        ).rstrip("/"),
        model=_setting(
            "DEEPSEEK_MODEL",
            file_values,
            "deepseek-v4-flash",
        ),
        timeout_seconds=timeout_seconds,
    )


def _setting(name: str, file_values: dict[str, str], default: str) -> str:
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if name:
            values[name] = value
    return values
