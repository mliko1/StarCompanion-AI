# -*- coding: utf-8 -*-
"""后端启动入口：python -m server.run

监听 0.0.0.0:8000，局域网内手机/平板通过「电脑局域网 IP:8000」访问。
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000)
