"""Authenticate before parsing; bound streaming input, concurrency and total work."""

import asyncio
import hmac
import re
from time import perf_counter
from uuid import uuid4

from uranus_research_service.errors import error_response
from uranus_research_service.json_codec import decode
from uranus_research_service.logging import logger

MAX_REQUEST_BYTES = 32768


class RequestBoundary:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = perf_counter()
        request_id = uuid4().hex
        status = 500
        started_response = False

        async def safe_send(message):
            nonlocal status, started_response
            if message["type"] == "http.response.start":
                started_response = True
                status = message["status"]
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"cache-control", b"x-request-id"}
                ]
                message = {
                    **message,
                    "headers": headers
                    + [(b"cache-control", b"no-store"), (b"x-request-id", request_id.encode())],
                }
            await send(message)

        async def fail(code, status_code):
            await error_response(code, status_code)(scope, receive, safe_send)

        admitted = False
        try:
            headers = scope.get("headers", [])
            if scope["path"] != "/health":
                keys = [v for k, v in headers if k.lower() == b"authorization"]
                expected = ("Bearer " + self.settings.api_key.get_secret_value()).encode()
                if len(keys) != 1 or not hmac.compare_digest(keys[0], expected):
                    await fail("unauthorized", 401)
                    return
                if scope.get("query_string") or any(
                    k.lower() in {b"cookie", b"origin"} for k, v in headers
                ):
                    await fail("invalid_request", 422)
                    return
            if scope["path"] == "/query":
                principals = [v for k, v in headers if k.lower() == b"x-research-principal"]
                if len(principals) != 1 or re.fullmatch(rb"[a-f0-9]{64}", principals[0]) is None:
                    await fail("invalid_principal", 422)
                    return
            if scope["path"] == "/health":
                await self.app(scope, receive, safe_send)
                return
            if self.active >= self.settings.max_concurrent_requests:
                await fail("capacity_exceeded", 503)
                return
            self.active += 1
            admitted = True
            if scope["method"] == "POST":
                types = [v for k, v in headers if k.lower() == b"content-type"]
                if (
                    len(types) != 1
                    or types[0].split(b";")[0].lower() != b"application/json"
                    or any(k.lower() == b"content-encoding" for k, v in headers)
                ):
                    await fail("invalid_request", 422)
                    return
                body = bytearray()
                async with asyncio.timeout(self.settings.body_timeout_seconds):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                            await fail("request_too_large", 413)
                            return
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
                decode(bytes(body))
                consumed = False

                async def bounded_receive():
                    nonlocal consumed
                    if not consumed:
                        consumed = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                inbound = bounded_receive
            else:
                inbound = receive
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                await self.app(scope, inbound, safe_send)
        except TimeoutError:
            if not started_response:
                await fail("request_timeout", 503)
        except (ValueError, TypeError, RecursionError):
            if not started_response:
                await fail("invalid_request", 422)
        except Exception:
            if not started_response:
                await fail("internal_error", 503)
        finally:
            if admitted:
                self.active -= 1
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "status_code": status,
                    "duration_ms": round((perf_counter() - start) * 1000, 2),
                },
            )
