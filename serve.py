"""One server, one port: the landing page at /, the dashboard at /app/.

    python serve.py                          # http://localhost:8501/  ->  "Launch the app"  ->  /app/
    python serve.py --host 0.0.0.0 --port 80 # on a server

Streamlit runs as a child process on an internal port with base path /app. This process serves the landing
page and forwards /app (plain HTTP and Streamlit's websocket) to it, so only one port is exposed.
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import aiohttp
from aiohttp import web
from multidict import CIMultiDict

ROOT = Path(__file__).resolve().parent
LANDING = ROOT / "landing" / "index.html"
APP_PATH = "/app"
# hop-by-hop headers are per connection and must not be forwarded (RFC 9110 §7.6.1)
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer",
              "transfer-encoding", "upgrade", "content-length"}
WS_HEADERS = ("Cookie", "Origin", "Host", "User-Agent", "Authorization")


def _forwardable(headers) -> CIMultiDict:
    return CIMultiDict((k, v) for k, v in headers.items() if k.lower() not in HOP_BY_HOP)


async def landing(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(request.app["landing"], headers={"Cache-Control": "no-cache"})


async def to_app(request: web.Request) -> web.StreamResponse:
    raise web.HTTPFound(APP_PATH + "/")


async def proxy(request: web.Request) -> web.StreamResponse:
    url = request.app["upstream"] + str(request.rel_url)
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await proxy_websocket(request, "ws" + url[len("http"):])
    session: aiohttp.ClientSession = request.app["client"]
    body = request.content if request.body_exists else None
    try:
        upstream = await session.request(request.method, url, headers=_forwardable(request.headers), data=body,
                                         allow_redirects=False)
    except aiohttp.ClientError:
        raise web.HTTPBadGateway(text="The dashboard is starting or unavailable. Try again in a moment.") from None
    async with upstream:
        response = web.StreamResponse(status=upstream.status, reason=upstream.reason,
                                      headers=_forwardable(upstream.headers))
        await response.prepare(request)
        async for chunk in upstream.content.iter_any():
            await response.write(chunk)
        await response.write_eof()
        return response


async def proxy_websocket(request: web.Request, url: str) -> web.StreamResponse:
    session: aiohttp.ClientSession = request.app["client"]
    protocols = [p.strip() for p in request.headers.get("Sec-WebSocket-Protocol", "").split(",") if p.strip()]
    headers = {k: request.headers[k] for k in WS_HEADERS if k in request.headers}
    try:
        upstream = await session.ws_connect(url, protocols=protocols, headers=headers, max_msg_size=0)
    except aiohttp.ClientError:
        raise web.HTTPBadGateway(text="The dashboard is starting or unavailable.") from None
    client = web.WebSocketResponse(protocols=[upstream.protocol] if upstream.protocol else (), max_msg_size=0)
    await client.prepare(request)

    async def pump(src, dst):
        async for msg in src:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await dst.send_str(msg.data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                await dst.send_bytes(msg.data)
            else:
                break

    tasks = [asyncio.create_task(pump(client, upstream)), asyncio.create_task(pump(upstream, client))]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await upstream.close()
        await client.close()
    return client


def make_app(upstream: str, landing_file: Path = LANDING) -> web.Application:
    """The web app on its own, pointed at an already running dashboard (used directly by the tests)."""
    app = web.Application(client_max_size=50 * 1024 ** 2)
    app["upstream"] = upstream.rstrip("/")
    app["landing"] = landing_file

    async def client_session(app):
        # no decompression: compressed bodies pass through untouched with their Content-Encoding
        app["client"] = aiohttp.ClientSession(auto_decompress=False, timeout=aiohttp.ClientTimeout(total=None, connect=10))
        yield
        await app["client"].close()

    app.cleanup_ctx.append(client_session)
    app.router.add_get("/", landing)
    app.router.add_get("/index.html", landing)
    app.router.add_get(APP_PATH, to_app)
    app.router.add_route("*", APP_PATH + "/{tail:.*}", proxy)
    return app


def start_dashboard(port: int) -> subprocess.Popen:
    cmd = [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
           "--server.address", "127.0.0.1", "--server.port", str(port),
           "--server.baseUrlPath", APP_PATH.strip("/"), "--server.headless", "true",
           "--browser.gatherUsageStats", "false"]
    return subprocess.Popen(cmd, cwd=ROOT, env=os.environ.copy())


def wait_until_healthy(port: int, proc: subprocess.Popen, timeout: float = 120) -> None:
    url = f"http://127.0.0.1:{port}{APP_PATH}/_stcore/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SystemExit(f"the dashboard exited with code {proc.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=2) as r:  # noqa: S310 - fixed local URL
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise SystemExit("the dashboard did not become healthy in time")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1", help="interface to listen on (0.0.0.0 on a server)")
    ap.add_argument("--port", type=int, default=8501, help="public port (default 8501)")
    ap.add_argument("--app-port", type=int, default=8502, help="internal Streamlit port (default 8502)")
    args = ap.parse_args(argv)
    if not LANDING.is_file():
        raise SystemExit(f"{LANDING} is missing; run: python landing/build.py")

    proc = start_dashboard(args.app_port)
    try:
        wait_until_healthy(args.app_port, proc)
        print(f"Q-Day Time Machine on port {args.port}: landing at /, dashboard at {APP_PATH}/", flush=True)
        web.run_app(make_app(f"http://127.0.0.1:{args.app_port}"), host=args.host, port=args.port, print=None)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
