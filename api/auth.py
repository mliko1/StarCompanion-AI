# -*- coding: utf-8 -*-
"""登录与会话接口。浏览器用 HttpOnly Cookie 保存令牌，桌面端用 Authorization 头。"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE = "xb_token"


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class PasswordRequest(BaseModel):
    old_password: str
    new_password: str


def token_of(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get(COOKIE)


def _set_cookie(response: JSONResponse, token: str, hours: int):
    response.set_cookie(
        COOKIE, token, max_age=hours * 3600,
        httponly=True, samesite="lax", path="/",
    )


@router.get("/me")
def me(request: Request):
    session = auth_service.verify_token(token_of(request))
    if not session:
        return {"authenticated": False}
    return {"authenticated": True, "user": session["username"], "role": session["role"]}


@router.post("/login")
def login(req: LoginRequest):
    user = auth_service.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码不正确")
    token = auth_service.create_session(user["username"], user["role"], hours=12)
    response = JSONResponse({"ok": True, "user": user["username"], "role": user["role"]})
    _set_cookie(response, token, 12)
    return response


@router.post("/logout")
def logout(request: Request):
    auth_service.revoke_token(token_of(request))
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE, path="/")
    return response


@router.post("/register")
def register(req: RegisterRequest):
    ok, msg = auth_service.register(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "msg": msg}


@router.post("/change-password")
def change_password(req: PasswordRequest, request: Request):
    session = auth_service.verify_token(token_of(request))
    if not session:
        raise HTTPException(status_code=401, detail="请先登录")
    ok, msg = auth_service.change_password(
        session["username"], req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    auth_service.revoke_token(token_of(request))
    response = JSONResponse({"ok": True, "msg": msg})
    response.delete_cookie(COOKIE, path="/")
    return response


@router.post("/desktop-token")
def desktop_token(request: Request):
    """本机桌面端专用令牌（仅 127.0.0.1 / ::1 可获取，无需交互登录）。"""
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="仅允许本机桌面端获取")
    token = auth_service.create_session("desktop", role="desktop", hours=24 * 7)
    response = JSONResponse({"ok": True, "token": token})
    _set_cookie(response, token, 24 * 7)
    return response
