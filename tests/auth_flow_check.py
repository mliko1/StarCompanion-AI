# -*- coding: utf-8 -*-
"""登录闭环自检：未登录拦截、登录、会话、退出、修改密码、桌面端令牌。

用法：先启动后端（默认 8001 端口可用环境变量 BASE_URL 覆盖），再运行本脚本。
"""

import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8001")
jar = http.cookiejar.CookieJar()
web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
plain = urllib.request.build_opener()

results = []


def call(opener, method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Cookie"] = "xb_token=" + token
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers, method=method)
    try:
        with opener.open(req, timeout=8) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS" if ok else "FAIL"), name, detail)


def main():
    code, _ = call(plain, "GET", "/api/children")
    check("未登录访问业务接口被拦截", code == 401, f"status={code}")

    code, _ = call(web, "POST", "/api/auth/login",
                   {"username": "demo", "password": "wrong"})
    check("错误密码登录失败", code == 401, f"status={code}")

    code, data = call(web, "POST", "/api/auth/login",
                      {"username": "demo", "password": "123456"})
    check("演示账号登录成功", code == 200 and data.get("ok"), f"status={code}")

    code, data = call(web, "GET", "/api/auth/me")
    check("登录态识别", code == 200 and data.get("authenticated"), str(data))

    code, _ = call(web, "GET", "/api/children")
    check("登录后可读业务数据", code == 200, f"status={code}")

    code, _ = call(web, "POST", "/api/auth/logout")
    check("退出登录", code == 200, f"status={code}")

    code, data = call(web, "GET", "/api/auth/me")
    check("退出后无登录态", code == 200 and not data.get("authenticated"), str(data))

    code, _ = call(web, "GET", "/api/children")
    check("退出后业务接口再次拦截", code == 401, f"status={code}")

    # 修改密码：用独立账号避免污染演示账号，验证旧密码失效、新密码可用、旧会话被撤销
    name = f"pwtest_{int(time.time())}"
    old_pwd, new_pwd = "Old@123456", "New@123456"
    pw_jar = http.cookiejar.CookieJar()
    pw_web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(pw_jar))

    code, data = call(plain, "POST", "/api/auth/register",
                      {"username": name, "password": old_pwd})
    check("改密测试账号注册", code == 200 and data.get("ok"), f"status={code}")

    code, _ = call(pw_web, "POST", "/api/auth/login",
                   {"username": name, "password": "wrong"})
    check("改密前错误密码登录失败", code == 401, f"status={code}")

    code, data = call(pw_web, "POST", "/api/auth/login",
                      {"username": name, "password": old_pwd})
    check("改密前原密码登录成功", code == 200 and data.get("ok"), f"status={code}")

    code, _ = call(pw_web, "POST", "/api/auth/change-password",
                   {"old_password": "wrong", "new_password": new_pwd})
    check("原密码错误时拒绝改密", code == 400, f"status={code}")

    code, _ = call(pw_web, "POST", "/api/auth/change-password",
                   {"old_password": old_pwd, "new_password": "123"})
    check("新密码过短时拒绝改密", code == 400, f"status={code}")

    code, data = call(pw_web, "POST", "/api/auth/change-password",
                      {"old_password": old_pwd, "new_password": new_pwd})
    check("原密码正确时改密成功", code == 200 and data.get("ok"), f"status={code}")

    code, data = call(pw_web, "GET", "/api/auth/me")
    check("改密后原会话被撤销", code == 200 and not data.get("authenticated"), str(data))

    code, _ = call(plain, "POST", "/api/auth/login",
                   {"username": name, "password": old_pwd})
    check("改密后旧密码登录失败", code == 401, f"status={code}")

    code, data = call(plain, "POST", "/api/auth/login",
                      {"username": name, "password": new_pwd})
    check("改密后新密码登录成功", code == 200 and data.get("ok"), f"status={code}")

    code, data = call(pw_web, "POST", "/api/auth/change-password",
                      {"old_password": new_pwd, "new_password": new_pwd})
    check("改密接口要求登录态", code == 401, f"status={code}")

    code, data = call(plain, "POST", "/api/auth/desktop-token", {})
    token = data.get("token", "")
    check("本机桌面端令牌可获取", code == 200 and bool(token), f"status={code}")

    code, _ = call(plain, "GET", "/api/children", token=token)
    check("桌面端令牌可访问业务接口", code == 200, f"status={code}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
    if failed:
        print("失败项：", "，".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
