"""Configuration constants for the web app."""

from __future__ import annotations

from pathlib import Path

# Repo root = parent of this package (contains sys_des_in/ and app/).
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
STATIC_DIR = APP_DIR / "static"

MAX_MESSAGE_LENGTH = 8_000
POLL_HINT_MS = 1_500

# Labels for pipeline checklist (filename -> short label).
PIPELINE_LABELS: dict[str, str] = {
    "00-problem-brief.md": "Problem brief",
    "01-requirements.md": "Requirements",
    "02-architecture.md": "Architecture",
    "03-api.md": "API",
    "04-data-model.md": "Data model",
    "05-component-design.md": "Component design",
    "06-resilience.md": "Resilience",
    "07-security-ops.md": "Security / ops",
    "08-decisions-log.md": "Decisions log",
    "09-capacity-estimates.md": "Capacity",
    "00-review.md": "Review",
    "00-index.md": "Index",
}
