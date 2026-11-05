from __future__ import annotations

import secrets
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def gen_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def gen_share_token() -> str:
    return secrets.token_urlsafe(24)
