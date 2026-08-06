"""Input validation, injection flags, hashing, and local rate limiting."""

from __future__ import annotations

import hashlib
import re
import threading
import time
import unicodedata
from collections import defaultdict, deque
from typing import Callable

PROJECT_ID = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?$")
INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|forget)\b.{0,40}\b(?:previous|prior|system|developer)\b.{0,30}\b(?:instructions?|messages?|prompt)\b",
            re.I | re.S,
        ),
    ),
    (
        "prompt_exfiltration",
        re.compile(
            r"\b(?:reveal|show|print|repeat|expose)\b.{0,40}\b(?:system|developer|hidden)\b.{0,20}\b(?:prompt|message|instructions?)\b",
            re.I | re.S,
        ),
    ),
    ("role_spoofing", re.compile(r"(?:^|\n)\s*(?:system|developer|assistant)\s*:", re.I | re.M)),
    (
        "tool_coercion",
        re.compile(
            r"\b(?:execute|run|invoke|call)\b.{0,30}\b(?:shell|terminal|command|tool)\b",
            re.I | re.S,
        ),
    ),
    (
        "secret_exfiltration",
        re.compile(
            r"\b(?:send|upload|exfiltrate|leak)\b.{0,40}\b(?:secret|token|password|api[-_ ]?key|credential)\b",
            re.I | re.S,
        ),
    ),
)


def validate_project_id(value: object) -> str:
    project_id = str(value or "").strip()
    if not PROJECT_ID.fullmatch(project_id) or project_id in {".", ".."}:
        raise ValueError(
            "projectId must be 1-64 URL-safe characters (letters, numbers, dot, underscore, or hyphen)."
        )
    return project_id


def sanitize_user_text(value: object, *, field: str = "input", max_chars: int = 4_000) -> str:
    text = unicodedata.normalize("NFKC", str(value if value is not None else ""))
    text = "".join(char for char in text if char in "\n\r\t" or ord(char) >= 32).strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string.")
    if len(text) > max_chars:
        raise ValueError(f"{field} exceeds the {max_chars}-character limit.")
    return text


def detect_prompt_injection(value: object) -> dict[str, object]:
    text = str(value or "")
    flags = [name for name, pattern in INJECTION_PATTERNS if pattern.search(text)]
    return {"detected": bool(flags), "flags": flags}


def stable_hash(value: object, length: int = 24) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:length]


class NestraRateLimitError(RuntimeError):
    code = "rate_limited"

    def __init__(self, retry_after_ms: int) -> None:
        super().__init__("NESTRA rate limit exceeded.")
        self.retry_after_ms = retry_after_ms


class SlidingWindowRateLimiter:
    def __init__(
        self, *, limit: int = 60, window_ms: int = 60_000, clock: Callable[[], float] | None = None
    ) -> None:
        self.limit = max(1, int(limit))
        self.window_ms = max(1, int(window_ms))
        self.clock = clock or (lambda: time.time() * 1000)
        self._rows: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(self, actor_id: str) -> dict[str, int | bool]:
        now = self.clock()
        with self._lock:
            rows = self._rows[str(actor_id)]
            while rows and rows[0] <= now - self.window_ms:
                rows.popleft()
            if len(rows) >= self.limit:
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retryAfterMs": max(1, round(rows[0] + self.window_ms - now)),
                }
            rows.append(now)
            return {"allowed": True, "remaining": self.limit - len(rows), "retryAfterMs": 0}
