"""统一登录与注册：管理员按账号名+路径识别，普通用户查库校验；复用同一套限流与会话机制。"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import ADMIN_DB_USERNAME, get_db
from app.models import AppUser
from app.routers.admin_auth import (
    _clear_gate,
    _client_ip,
    _const_eq,
    _ensure_admin_user,
    _get_gate,
    _issue_token,
    _lock_remaining,
    _locked_response,
    _normalize_path,
    _record_failure,
)
from app.schemas import AuthLoginIn, AuthRegisterIn, AuthTokenOut
from app.settings import get_settings
from app.utils import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 账号至少 3 位，只能英文字母和数字；密码正好 6 位，只能英文字母和数字
USERNAME_RE = re.compile(r"^[A-Za-z0-9]{3,}$")
PASSWORD_RE = re.compile(r"^[A-Za-z0-9]{6}$")


@router.post("/register", response_model=AuthTokenOut)
def register(body: AuthRegisterIn, db: Session = Depends(get_db)):
    """注册新账号：只校验位数和字符集，其它不限制。"""
    username = (body.username or "").strip()
    password = body.password or ""
    if not USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="账号至少 3 位，只能用英文字母和数字")
    if not PASSWORD_RE.match(password):
        raise HTTPException(status_code=400, detail="密码必须是 6 位英文字母或数字")
    if username == ADMIN_DB_USERNAME or username == get_settings().admin_username:
        raise HTTPException(status_code=400, detail="该账号不可用")
    exists = db.query(AppUser).filter(AppUser.username == username).first()
    if exists:
        raise HTTPException(status_code=400, detail="账号已被注册")
    user = AppUser(username=username, email=None, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token, expires_in = _issue_token(user.id)
    return AuthTokenOut(token=token, expires_in=expires_in, username=user.username)


@router.post("/login", response_model=AuthTokenOut)
def login(body: AuthLoginIn, request: Request, db: Session = Depends(get_db)):
    """统一登录：管理员按账号名识别，路径须与 ini login_path 一致；失败按 IP 计数，满 5 次锁 60 秒。"""
    ip = _client_ip(request)
    gate = _get_gate(ip)
    remaining = _lock_remaining(gate)
    if remaining is not None:
        return _locked_response(remaining)

    settings = get_settings()
    username = (body.username or "").strip()
    password = body.password or ""

    # 管理员账号：路径和密码都命中 ini 才发会话，报错与普通登录一致，不泄露原因
    if username == settings.admin_username:
        path_ok = _const_eq(_normalize_path(body.path), _normalize_path(settings.login_path))
        pass_ok = _const_eq(password, settings.admin_password)
        if not (path_ok and pass_ok):
            locked = _record_failure(ip)
            if locked is not None:
                return locked
            raise HTTPException(status_code=401, detail="账号或密码错误")
        _clear_gate(ip)
        # 中文：管理员在库里固定为同一身份，ini 只当登录凭据，改 ini 不再丢文件夹
        user = _ensure_admin_user(db)
        token, expires_in = _issue_token(user.id)
        return AuthTokenOut(token=token, expires_in=expires_in, username="管理员")

    # 普通用户：只查账号密码，与路径无关
    user = None
    if username:
        user = db.query(AppUser).filter(AppUser.username == username).first()
    if user is None or not verify_password(password, user.password_hash):
        locked = _record_failure(ip)
        if locked is not None:
            return locked
        raise HTTPException(status_code=401, detail="账号或密码错误")

    _clear_gate(ip)
    token, expires_in = _issue_token(user.id)
    return AuthTokenOut(token=token, expires_in=expires_in, username=user.username)


@router.get("/entry")
def entry():
    """公开登录入口路径：唯一登录/注册页在 ini 的 login_path，未登录跳转和退出回跳都用它。"""
    return {"login_path": _normalize_path(get_settings().login_path)}