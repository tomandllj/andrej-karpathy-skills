"""管理员固定 URI 登录：凭据校验、IP 失败锁定、内存会话 token。"""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import ADMIN_DB_USERNAME, get_db
from app.models import AppUser
from app.schemas import AdminGateIn, AdminGateOut, AdminMeOut
from app.settings import get_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

FAIL_LIMIT = 5
LOCK_SECONDS = 60
TOKEN_TTL_SECONDS = 12 * 3600


@dataclass
class IpGate:
    """单个 IP 的失败次数与锁定截止时间。"""

    fails: int = 0
    locked_until: float | None = None


@dataclass
class Session:
    """内存中的登录会话，记下是哪个账号。"""

    expires_at: float
    user_id: int


_ip_gates: dict[str, IpGate] = {}
_tokens: dict[str, Session] = {}


def _client_ip(request: Request) -> str:
    """从请求里取出客户端 IP（优先 X-Forwarded-For）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _const_eq(a: str, b: str) -> bool:
    """常量时间比较两个字符串（长度不同直接视为不等）。"""
    aa = (a or "").encode("utf-8")
    bb = (b or "").encode("utf-8")
    if len(aa) != len(bb):
        return False
    return hmac.compare_digest(aa, bb)


def _normalize_path(raw: str) -> str:
    """把登录 path 规范成以 / 开头、无尾斜杠（根路径除外）。"""
    path = (raw or "").strip() or "/"
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


def _lock_remaining(gate: IpGate) -> int | None:
    """若仍在锁定期，返回剩余秒数；锁到期则清零失败计数。"""
    if gate.locked_until is None:
        return None
    now = time.time()
    if now < gate.locked_until:
        return max(1, int(gate.locked_until - now + 0.999))
    gate.fails = 0
    gate.locked_until = None
    return None


def _get_gate(ip: str) -> IpGate:
    """取或创建该 IP 的限流状态。"""
    gate = _ip_gates.get(ip)
    if gate is None:
        gate = IpGate()
        _ip_gates[ip] = gate
    return gate


def _locked_response(retry_after: int) -> JSONResponse:
    """返回 429 与剩余锁定秒数。"""
    return JSONResponse(
        status_code=429,
        content={"detail": {"message": "登录失败次数过多，请稍后再试", "retry_after": retry_after}},
        headers={"Retry-After": str(retry_after)},
    )


def _record_failure(ip: str) -> JSONResponse | None:
    """记录一次失败；达阈值则锁定并返回 429 响应，否则返回 None。"""
    gate = _get_gate(ip)
    gate.fails += 1
    if gate.fails >= FAIL_LIMIT:
        gate.locked_until = time.time() + LOCK_SECONDS
        return _locked_response(LOCK_SECONDS)
    return None


def _clear_gate(ip: str) -> None:
    """登录成功后清掉该 IP 的失败与锁定。"""
    _ip_gates.pop(ip, None)


def _issue_token(user_id: int) -> tuple[str, int]:
    """签发内存会话 token，返回 (token, expires_in)。"""
    _purge_expired_tokens()
    token = secrets.token_urlsafe(32)
    _tokens[token] = Session(
        expires_at=time.time() + TOKEN_TTL_SECONDS,
        user_id=user_id,
    )
    return token, TOKEN_TTL_SECONDS


def _purge_expired_tokens() -> None:
    """清理已过期的会话 token。"""
    now = time.time()
    dead = [t for t, sess in _tokens.items() if sess.expires_at <= now]
    for t in dead:
        _tokens.pop(t, None)


def _session(token: str | None) -> Session | None:
    """取出仍有效的会话。"""
    if not token:
        return None
    _purge_expired_tokens()
    sess = _tokens.get(token)
    if sess is None or sess.expires_at <= time.time():
        return None
    return sess


def _token_valid(token: str | None) -> bool:
    """判断 Bearer token 是否仍在有效期内。"""
    return _session(token) is not None


def user_id_from_token(token: str | None) -> int | None:
    """从会话 token 取出用户 id；无效或过期返回 None。"""
    sess = _session(token)
    return sess.user_id if sess else None


def current_user_id(authorization: str | None) -> int | None:
    """从 Authorization 取出当前用户 id；未登录返回 None。"""
    return user_id_from_token(_extract_bearer(authorization))


def require_user_id(authorization: str | None = Header(default=None)) -> int:
    """要求已登录，返回当前用户 id。"""
    user_id = current_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return user_id


def _extract_bearer(authorization: str | None) -> str | None:
    """从 Authorization 头解析 Bearer token。"""
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


@router.post("/gate", response_model=AdminGateOut)
def admin_gate(body: AdminGateIn):
    """仅当 path 与 config.ini login_path 完全一致时 ok=true，不泄露正确路径。"""
    settings = get_settings()
    ok = _const_eq(_normalize_path(body.path), _normalize_path(settings.login_path))
    return AdminGateOut(ok=ok)


def _ensure_admin_user(db: Session) -> AppUser:
    """取固定身份的管理员行，没有则创建；ini 账号密码只用于登录校验，不再是库内身份。"""
    row = db.query(AppUser).filter(AppUser.username == ADMIN_DB_USERNAME).first()
    if row:
        return row
    row = AppUser(username=ADMIN_DB_USERNAME, email=None)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/me", response_model=AdminMeOut)
def admin_me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """确认会话有效，返回顶栏展示名；login_path 只给管理员，不向普通用户泄露隐藏入口。"""
    token = _extract_bearer(authorization)
    user_id = user_id_from_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    settings = get_settings()
    if user and user.username == ADMIN_DB_USERNAME:
        return AdminMeOut(
            ok=True,
            name="管理员",
            login_path=_normalize_path(settings.login_path),
        )
    return AdminMeOut(
        ok=True,
        name=(user.username if user else "用户"),
        login_path="",
    )
