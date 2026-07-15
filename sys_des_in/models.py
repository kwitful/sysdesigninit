"""Central LLM model factory for the system-design assistant.

ADK supports non-Gemini providers through ``LiteLlm``
(``google.adk.models.lite_llm.LiteLlm``), which routes to LiteLLM's provider
layer. OpenRouter is configured as a first-class option via that path:

    LLM_PROVIDER=openrouter
    LLM_MODEL=openrouter/openai/gpt-4o-mini
    OPENROUTER_API_KEY=sk-or-...

Gemini remains the default and needs no LiteLLM wrapper (pass the model name
string directly, per ADK docs).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


# Known-bad LiteLLM releases called out in ADK security advisories.
_BLOCKED_LITELLM = {"1.82.7", "1.82.8"}


def _load_local_dotenv() -> None:
    """Load ``sys_des_in/.env`` early so ``get_model()`` sees provider keys.

    Does not override variables already set in the process environment.
    Safe no-op if the file or python-dotenv is missing.
    """
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
        return
    load_dotenv(env_path, override=False)


_load_local_dotenv()
# Windows + LiteLLM: ADK docs recommend forcing UTF-8 file I/O.
os.environ.setdefault("PYTHONUTF8", "1")


def _check_litellm_version() -> None:
    """Refuse to load if a blocked LiteLLM version is installed."""
    try:
        import litellm  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "LiteLLM is required for LLM_PROVIDER=openrouter (or litellm). "
            "Install with: pip install 'litellm>=1.40.0'"
        ) from exc
    version = getattr(litellm, "__version__", "") or ""
    # litellm versions are often like "1.82.7" or longer; compare prefix.
    for blocked in _BLOCKED_LITELLM:
        if version == blocked or version.startswith(blocked + "."):
            raise RuntimeError(
                f"Installed litellm=={version} is blocked by ADK security "
                f"guidance. Upgrade or downgrade away from {_BLOCKED_LITELLM}."
            )


def get_model() -> Any:
    """Return an ADK-compatible model object based on environment config.

    Environment variables
    ---------------------
    LLM_PROVIDER:
        ``gemini`` (default), ``openrouter``, or ``litellm``.
    LLM_MODEL:
        Model id. For Gemini, a bare name like ``gemini-flash-latest``.
        For OpenRouter, prefer a full LiteLLM id
        ``openrouter/<provider>/<model>`` (a missing ``openrouter/`` prefix
        is added automatically).
    OPENROUTER_API_KEY:
        Required when ``LLM_PROVIDER=openrouter``.
    OPENAI_API_KEY / ANTHROPIC_API_KEY / etc.:
        Used when ``LLM_PROVIDER=litellm`` with the matching provider prefix.

    Returns
    -------
    str | LiteLlm
        A Gemini model name string, or a ``LiteLlm`` wrapper for other
        providers (ADK's documented multi-model path).
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    model_name = os.getenv("LLM_MODEL", "").strip()

    if provider in ("", "gemini", "google"):
        return model_name or "gemini-flash-latest"

    if provider == "openrouter":
        _check_litellm_version()
        from google.adk.models.lite_llm import LiteLlm

        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY in the "
                "environment (e.g. sys_des_in/.env)."
            )
        model_id = model_name or "openrouter/openai/gpt-4o-mini"
        if not model_id.startswith("openrouter/"):
            model_id = f"openrouter/{model_id}"
        # Optional OpenRouter attribution headers (supported by LiteLLM).
        site = os.getenv("OR_SITE_URL", "").strip()
        app = os.getenv("OR_APP_NAME", "sysdesigninit").strip()
        if site:
            os.environ.setdefault("OR_SITE_URL", site)
        if app:
            os.environ.setdefault("OR_APP_NAME", app)
        return LiteLlm(model=model_id, api_key=api_key)

    if provider == "litellm":
        _check_litellm_version()
        from google.adk.models.lite_llm import LiteLlm

        if not model_name:
            raise ValueError(
                "LLM_PROVIDER=litellm requires LLM_MODEL "
                "(e.g. openai/gpt-4o or anthropic/claude-3-haiku-20240307)."
            )
        return LiteLlm(model=model_name)

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}. "
        "Use 'gemini', 'openrouter', or 'litellm'."
    )
