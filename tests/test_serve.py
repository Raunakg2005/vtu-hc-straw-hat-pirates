"""The one-port server: landing page at /, dashboard proxied at /app/ (HTTP and websocket).

A small aiohttp app stands in for Streamlit, so these tests need no browser and no network.
"""

import asyncio
import gzip
import sys
from pathlib import Path

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import serve  # noqa: E402

BIG = 5 * 1024 * 1024  # above aiohttp's 4 MB default websocket message limit


def fake_dashboard() -> web.Application:
    async def hello(request):
        resp = web.Response(text="hi from the dashboard", headers={"X-Upstream": "yes"})
        resp.headers.add("Set-Cookie", "a=1; Path=/app")
        resp.headers.add("Set-Cookie", "b=2; Path=/app")
        return resp

    async def echo(request):
        return web.Response(body=await request.read(), headers={"X-Method": request.method,
                                                                "X-Host": request.headers.get("Host", "")})

    async def redirect(request):
        raise web.HTTPFound("/app/elsewhere")

    async def compressed(request):
        return web.Response(body=gzip.compress(b"x" * 10_000), headers={"Content-Encoding": "gzip",
                                                                         "Content-Type": "text/plain"})

    async def stream(request):
        ws = web.WebSocketResponse(protocols=("streamlit",), max_msg_size=0)
        await ws.prepare(request)
        await ws.send_str("origin=" + request.headers.get("Origin", ""))
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await ws.send_str("echo:" + msg.data)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                await ws.send_bytes(msg.data[::-1])
        return ws

    app = web.Application(client_max_size=BIG * 2)
    app.router.add_get("/app/hello", hello)
    app.router.add_route("*", "/app/echo", echo)
    app.router.add_get("/app/redirect", redirect)
    app.router.add_get("/app/gz", compressed)
    app.router.add_get("/app/_stcore/stream", stream)
    return app


def run(check, landing_text="<h1>landing</h1>", upstream_alive=True):
    """Start fake dashboard + proxy, then run `check(session, base_url)`."""

    async def main(tmp_landing):
        upstream = TestServer(fake_dashboard())
        await upstream.start_server()
        target = str(upstream.make_url("")).rstrip("/")
        if not upstream_alive:
            await upstream.close()
        proxy = TestServer(serve.make_app(target, tmp_landing))
        await proxy.start_server()
        try:
            async with aiohttp.ClientSession(auto_decompress=False) as session:
                return await check(session, str(proxy.make_url("")).rstrip("/"))
        finally:
            await proxy.close()
            if upstream_alive:
                await upstream.close()

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "index.html"
        page.write_text(landing_text, encoding="utf8")
        return asyncio.run(main(page))


@pytest.mark.parametrize("path", ["/", "/index.html"])
def test_landing_page_is_served_at_root(path):
    async def check(s, base):
        async with s.get(base + path) as r:
            return r.status, await r.text(), r.headers.get("Cache-Control")
    assert run(check) == (200, "<h1>landing</h1>", "no-cache")


def test_app_without_slash_redirects_to_app_slash():
    async def check(s, base):
        async with s.get(base + "/app", allow_redirects=False) as r:
            return r.status, r.headers["Location"]
    assert run(check) == (302, "/app/")


def test_get_is_proxied_with_every_cookie():
    async def check(s, base):
        async with s.get(base + "/app/hello") as r:
            return r.status, await r.text(), r.headers["X-Upstream"], r.headers.getall("Set-Cookie")
    status, body, marker, cookies = run(check)
    assert (status, body, marker) == (200, "hi from the dashboard", "yes")
    assert cookies == ["a=1; Path=/app", "b=2; Path=/app"]


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_request_body_and_method_are_forwarded(method):
    async def check(s, base):
        async with s.request(method, base + "/app/echo", data=b"payload-123") as r:
            return await r.read(), r.headers["X-Method"]
    assert run(check) == (b"payload-123", method)


def test_host_header_is_preserved_for_origin_checks():
    async def check(s, base):
        async with s.get(base + "/app/echo", headers={"Host": "quantum.example"}) as r:
            return r.headers["X-Host"]
    assert run(check) == "quantum.example"


def test_upstream_redirects_are_passed_through_not_followed():
    async def check(s, base):
        async with s.get(base + "/app/redirect", allow_redirects=False) as r:
            return r.status, r.headers["Location"]
    assert run(check) == (302, "/app/elsewhere")


def test_compressed_bodies_pass_through_intact():
    async def check(s, base):
        async with s.get(base + "/app/gz") as r:
            return r.headers.get("Content-Encoding"), await r.read()
    encoding, raw = run(check)
    assert encoding == "gzip" and gzip.decompress(raw) == b"x" * 10_000


def test_unknown_paths_are_not_proxied():
    async def check(s, base):
        statuses = []
        for path in ("/etc/passwd", "/../app.py", "/application"):
            async with s.get(base + path) as r:
                statuses.append(r.status)
        return statuses
    assert run(check) == [404, 404, 404]


def test_websocket_relays_text_binary_and_subprotocol():
    async def check(s, base):
        async with s.ws_connect(base.replace("http", "ws", 1) + "/app/_stcore/stream",
                                protocols=("streamlit", "token-xyz"), headers={"Origin": "http://localhost:8501"},
                                max_msg_size=0) as ws:
            first = await ws.receive_str()
            await ws.send_str("ping")
            text = await ws.receive_str()
            await ws.send_bytes(b"\x01\x02\x03")
            binary = await ws.receive_bytes()
            return ws.protocol, first, text, binary
    assert run(check) == ("streamlit", "origin=http://localhost:8501", "echo:ping", b"\x03\x02\x01")


def test_websocket_carries_messages_larger_than_4mb():
    async def check(s, base):
        async with s.ws_connect(base.replace("http", "ws", 1) + "/app/_stcore/stream",
                                protocols=("streamlit",), max_msg_size=0) as ws:
            await ws.receive_str()
            payload = bytes(range(256)) * (BIG // 256)
            await ws.send_bytes(payload)
            return await ws.receive_bytes() == payload[::-1]
    assert run(check) is True


def test_dashboard_down_gives_502_not_a_crash():
    async def check(s, base):
        async with s.get(base + "/app/hello") as r:
            page = await r.text()
        async with s.get(base + "/") as r:
            return r.status, page, r.status
    status_app, page, status_root = run(check, upstream_alive=False)
    assert "unavailable" in page
    assert status_root == 200  # the landing page still works


def test_cli_refuses_to_start_without_built_landing(monkeypatch, tmp_path):
    monkeypatch.setattr(serve, "LANDING", tmp_path / "missing.html")
    with pytest.raises(SystemExit, match="landing/build.py"):
        serve.main([])


def test_real_landing_links_to_the_app():
    page = (Path(serve.__file__).parent / "landing" / "index.html").read_text(encoding="utf8")
    assert page.count('href="/app/"') >= 3
    assert "collegepathshala" not in page
