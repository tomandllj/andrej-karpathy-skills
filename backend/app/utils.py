from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def gen_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def gen_share_token() -> str:
    return secrets.token_urlsafe(24)


# 普通用户密码哈希参数；存库格式 pbkdf2$盐hex$摘要hex
_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """把明文密码加盐哈希成可存库的字符串。"""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """校验明文密码是否与库里的哈希一致；没有哈希（如管理员）一律不通过。"""
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 3 or parts[0] != "pbkdf2":
        return False
    try:
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest, expected)
