# -*- coding: utf-8 -*-
"""账号密码与登录会话：PBKDF2 哈希 + 服务端会话令牌。

密码不明文落库；令牌只保存在服务端内存，后端重启即全部失效，
家长每次启动系统都需要重新登录（与桌面软件一致）。
"""

import datetime
import hashlib
import hmac
import secrets
import threading

from database.db import SessionLocal
from database import models

_ROUNDS = 200_000
_LOCK = threading.Lock()
_SESSIONS = {}  # token -> {username, role, expires_at}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ROUNDS)
    return salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _ROUNDS)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def authenticate(username: str, password: str):
    """校验账号密码，成功返回公开用户信息，否则 None。"""
    db = SessionLocal()
    try:
        user = db.query(models.AppUser).filter_by(username=username.strip()).first()
        if not user or not user.active or not verify_password(password or "", user.password_hash):
            return None
        user.last_login_at = datetime.datetime.now()
        db.commit()
        return {"username": user.username, "role": user.role}
    finally:
        db.close()


def register(username: str, password: str):
    name = (username or "").strip()
    if len(name) < 2:
        return False, "用户名至少 2 个字符"
    if len(password or "") < 6:
        return False, "密码至少 6 位"
    db = SessionLocal()
    try:
        if db.query(models.AppUser).filter_by(username=name).first():
            return False, "该用户名已被注册"
        db.add(models.AppUser(username=name, password_hash=hash_password(password)))
        db.commit()
        return True, "注册成功"
    finally:
        db.close()


def change_password(username: str, old: str, new: str):
    if len(new or "") < 6:
        return False, "新密码至少 6 位"
    db = SessionLocal()
    try:
        user = db.query(models.AppUser).filter_by(username=username).first()
        if not user or not verify_password(old or "", user.password_hash):
            return False, "原密码不正确"
        user.password_hash = hash_password(new)
        db.commit()
        return True, "密码已更新，请重新登录"
    finally:
        db.close()


def create_session(username: str, role: str = "parent", hours: int = 12) -> str:
    token = secrets.token_urlsafe(32)
    with _LOCK:
        _SESSIONS[token] = {
            "username": username,
            "role": role,
            "expires_at": datetime.datetime.now() + datetime.timedelta(hours=hours),
        }
    return token


def verify_token(token: str | None):
    if not token:
        return None
    with _LOCK:
        session = _SESSIONS.get(token)
        if not session:
            return None
        if session["expires_at"] < datetime.datetime.now():
            _SESSIONS.pop(token, None)
            return None
        return {"username": session["username"], "role": session["role"]}


def revoke_token(token: str | None):
    if token:
        with _LOCK:
            _SESSIONS.pop(token, None)
