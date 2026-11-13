"""Domain normalization, validation and suffix-boundary matching."""
from __future__ import annotations

import re

_ALLOWED = re.compile(r"^[A-Za-z0-9.-]+$")


def is_valid_domain_input(value: str) -> bool:
    """Apply the exact input constraints described in the project PDF."""
    if not value or not _ALLOWED.fullmatch(value):
        return False
    if value.startswith(".") or ".." in value:
        return False
    return True


def normalize_domain(value: str) -> str:
    """Lowercase and remove one final dot (the only normalization required)."""
    normalized = value.lower()
    if normalized.endswith("."):
        normalized = normalized[:-1]
    return normalized


def is_valid_normalized_domain(value: str) -> bool:
    return bool(value) and is_valid_domain_input(value) and not value.endswith(".")


def domain_matches(name: str, entry: str) -> bool:
    """Match exact domain or a true subdomain, never a mere string suffix."""
    return name == entry or name.endswith("." + entry)
