from dataclasses import dataclass
import os
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = WORKSPACE_ROOT / ".env"


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float

    @property
    def deepseek_enabled(self) -> bool:
        return self.provider == "deepseek" and bool(self.api_key)

    @property
    def gemini_enabled(self) -> bool:
        return self.provider == "gemini" and bool(self.api_key)


def load_llm_config(env_path: Path = ENV_PATH) -> LLMConfig:
    file_values = _read_env_file(env_path)
    provider = _setting("SUMMARY_PROVIDER", file_values, "deterministic").lower()
    if provider not in {"deepseek", "deterministic", "gemini"}:
        raise ValueError(
            "SUMMARY_PROVIDER must be 'deepseek', 'gemini', or 'deterministic'."
        )

    provider_prefix = provider.upper()
    timeout_name = (
        f"{provider_prefix}_TIMEOUT_SECONDS"
        if provider in {"deepseek", "gemini"}
        else "DEEPSEEK_TIMEOUT_SECONDS"
    )
    timeout_value = _setting(timeout_name, file_values, "45")
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as exc:
        raise ValueError(f"{timeout_name} must be a number.") from exc
    if not 5 <= timeout_seconds <= 120:
        raise ValueError(f"{timeout_name} must be between 5 and 120.")

    defaults = {
        "deepseek": {
            "api_key": "DEEPSEEK_API_KEY",
            "base_url": "DEEPSEEK_BASE_URL",
            "default_base_url": "https://api.deepseek.com",
            "model": "DEEPSEEK_MODEL",
            "default_model": "deepseek-v4-flash",
        },
        "gemini": {
            "api_key": "GEMINI_API_KEY",
            "base_url": "GEMINI_BASE_URL",
            "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
            "model": "GEMINI_MODEL",
            "default_model": "gemini-2.0-flash",
        },
        "deterministic": {
            "api_key": "DEEPSEEK_API_KEY",
            "base_url": "DEEPSEEK_BASE_URL",
            "default_base_url": "https://api.deepseek.com",
            "model": "DEEPSEEK_MODEL",
            "default_model": "deterministic",
        },
    }[provider]

    return LLMConfig(
        provider=provider,
        api_key=_setting(defaults["api_key"], file_values, ""),
        base_url=_setting(defaults["base_url"], file_values, defaults["default_base_url"]).rstrip("/"),
        model=_setting(defaults["model"], file_values, defaults["default_model"]),
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
