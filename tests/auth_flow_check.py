# -*- coding: utf-8 -*-
"""登录闭环自检：未登录拦截、登录、会话、退出、桌面端令牌。

用法：先启动后端（默认 8001 端口可用环境变量 BASE_URL 覆盖），再运行本脚本。
"""

import http.cookiejar
import json
import os
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
