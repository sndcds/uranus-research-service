"""Bounded fixed-origin metadata transport. No inference, retries, redirects or cookie jar."""

import asyncio
from typing import Literal

import httpx

from uranus_research_service.config import Settings
from uranus_research_service.errors import DependencyError
from uranus_research_service.json_codec import decode


class InternalClient:
    def __init__(
        self, settings: Settings, dependency: Literal["planner", "encoder"], *, transport=None
    ):
        self.dependency = dependency
        self.origin = getattr(settings, dependency + "_url")
        self.key = getattr(settings, dependency + "_api_key")
        self.timeout = settings.dependency_timeout_seconds
        self.max_bytes = settings.max_response_bytes
        self.http = httpx.AsyncClient(
            timeout=self.timeout, trust_env=False, follow_redirects=False, transport=transport
        )

    async def close(self):
        await self.http.aclose()

    async def get(self, path: Literal["/ready", "/version"]):
        if path not in {"/ready", "/version"}:
            raise ValueError("fixed_metadata_path_required")
        return await self._request("GET", path)

    async def route(self, contract):
        if self.dependency != "planner" or contract not in {"v9", "v10", "v11", "v12", "v13"}:
            raise ValueError("fixed_planner_route_required")
        await self._request("OPTIONS", "/" + contract + "/plan")

    async def _request(self, method, path):
        if self.key is None:
            raise DependencyError(self.dependency, "unconfigured")
        request = httpx.Request(
            method,
            self.origin + path,
            headers={
                "Authorization": "Bearer " + self.key.get_secret_value(),
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
        )
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.http.send(request, stream=True)
                try:
                    expected_status = 405 if method == "OPTIONS" else 200
                    if response.status_code != expected_status:
                        category = (
                            "contract_unverifiable"
                            if path == "/version" and response.status_code == 404
                            else "unavailable"
                        )
                        raise DependencyError(self.dependency, category)
                    if (
                        response.headers.get("content-type", "").split(";")[0].strip().lower()
                        != "application/json"
                        or response.headers.get("content-encoding", "identity") != "identity"
                    ):
                        raise DependencyError(self.dependency, "invalid_response")
                    if method == "OPTIONS" and {
                        v.strip().upper() for v in response.headers.get("allow", "").split(",")
                    } != {"POST"}:
                        raise DependencyError(self.dependency, "incompatible")
                    body = bytearray()
                    async for part in response.aiter_bytes(chunk_size=self.max_bytes + 1):
                        if len(body) + len(part) > self.max_bytes:
                            raise DependencyError(self.dependency, "invalid_response")
                        body.extend(part)
                    result = decode(bytes(body))
                    if not isinstance(result, dict):
                        raise DependencyError(self.dependency, "invalid_response")
                    return result
                finally:
                    await response.aclose()
        except (httpx.HTTPError, TimeoutError, OSError):
            raise DependencyError(self.dependency, "unavailable") from None
        except (ValueError, TypeError, RecursionError):
            raise DependencyError(self.dependency, "invalid_response") from None
