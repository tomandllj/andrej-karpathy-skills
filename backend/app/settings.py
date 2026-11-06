"""从项目根目录（或 exe 同目录）读取旁路 config.ini。"""

from __future__ import annotations

import secrets
import sys
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

CONFIG_FILENAME = "config.ini"


@dataclass(frozen=True)
class AppSettings:
    """管理员相关配置（明文旁路文件，供后续登录使用）。"""

    admin_username: str
    admin_password: str
    login_path: str
    # [features] 开关：1/on/true/yes 为开，缺省开
    oncursor_enabled: bool = True
    online_enabled: bool = True


_settings: AppSettings | None = None


def app_base_dir() -> Path:
    """返回配置文件所在目录：打包 exe 旁，或开发时仓库根目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # backend/app/settings.py → 上两级即仓库根（与 run.py 同级）
    return Path(__file__).resolve().parent.parent.parent


def config_path() -> Path:
    """返回 config.ini 的完整路径。"""
    return app_base_dir() / CONFIG_FILENAME


def _normalize_login_path(raw: str) -> str:
    """把登录路径规范成以 / 开头。"""
    path = (raw or "").strip()
    if not path:
        raise ValueError("config.ini [admin] login_path 不能为空")
    if not path.startswith("/"):
        path = "/" + path
    return path


def _generate_random_config() -> ConfigParser:
    """生成一份长随机管理员凭据。"""
    cfg = ConfigParser()
    cfg["admin"] = {
        "username": secrets.token_urlsafe(18),
        "password": secrets.token_urlsafe(32),
        "login_path": "/" + secrets.token_urlsafe(24),
    }
    return cfg


def _write_config(path: Path, cfg: ConfigParser) -> None:
    """把配置写到磁盘。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def _parse_settings(cfg: ConfigParser) -> AppSettings:
    """从 ConfigParser 取出并校验管理员字段。"""
    if not cfg.has_section("admin"):
        raise ValueError("config.ini 缺少 [admin] 段")
    username = cfg.get("admin", "username", fallback="").strip()
    password = cfg.get("admin", "password", fallback="").strip()
    login_path = _normalize_login_path(cfg.get("admin", "login_path", fallback=""))
    if not username:
        raise ValueError("config.ini [admin] username 不能为空")
    if not password:
        raise ValueError("config.ini [admin] password 不能为空")
    return AppSettings(
        admin_username=username,
        admin_password=password,
        login_path=login_path,
        oncursor_enabled=cfg.getboolean("features", "oncursor", fallback=True),
        online_enabled=cfg.getboolean("features", "online", fallback=True),
    )


def load_settings(*, force_reload: bool = False) -> AppSettings:
    """加载 config.ini；不存在则自动生成长随机凭据后再读。"""
    global _settings
    if _settings is not None and not force_reload:
        return _settings

    path = config_path()
    if not path.is_file():
        _write_config(path, _generate_random_config())

    cfg = ConfigParser()
    read_ok = cfg.read(path, encoding="utf-8")
    if not read_ok:
        raise FileNotFoundError(f"无法读取配置文件：{path}")

    _settings = _parse_settings(cfg)
    return _settings


def get_settings() -> AppSettings:
    """返回已加载的配置；尚未加载则先 load。"""
    if _settings is None:
        return load_settings()
    return _settings


# 模块级别名，方便 `from app.settings import ADMIN_USERNAME` 这类用法（懒加载属性）
def __getattr__(name: str):
    """按需暴露 ADMIN_USERNAME / ADMIN_PASSWORD / LOGIN_PATH。"""
    mapping = {
        "ADMIN_USERNAME": "admin_username",
        "ADMIN_PASSWORD": "admin_password",
        "LOGIN_PATH": "login_path",
        "ONCURSOR_ENABLED": "oncursor_enabled",
        "ONLINE_ENABLED": "online_enabled",
    }
    attr = mapping.get(name)
    if attr is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(get_settings(), attr)
