"""Embedded web server for serving media to remote devices.

This module provides a simple HTTP server using aiohttp to serve media content
(bytes and files) that can be accessed by cast devices on the local network.
"""

from __future__ import annotations

import logging
import socket
from typing import TYPE_CHECKING, cast

from aiohttp import web

if TYPE_CHECKING:
    import commoncast.types as _types

_LOGGER = logging.getLogger(__name__)


class MediaServer:
    """Embedded HTTP server for serving media content.

    The server manages a mapping of random IDs to MediaPayload objects and
    serves them over HTTP.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 0) -> None:
        """Initialize the MediaServer.

        :param host: Host interface to bind to.
        :param port: Port to bind to (0 for a free port).
        :returns: None
        """
        self._host = host
        self._port = port
        self._app = web.Application()
        self._app.add_routes([web.get("/{id}", self._handle_media)])
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._payloads: dict[str, _types.MediaPayload] = {}
        self._base_url: str | None = None

    async def start(self) -> None:
        """Start the HTTP server.

        :returns: None
        """
        if self._runner is not None:
            return

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()

        # Get the actual port if 0 was requested
        # We can find the port from the runner's addresses
        actual_port: int = self._port
        if self._runner.addresses:
            # addresses is a list of (host, port) or just host/port depending on family
            addr = self._runner.addresses[0]
            if isinstance(addr, tuple):
                actual_port = cast(int, addr[1])
            elif isinstance(addr, str):
                # Handle cases like Unix sockets or just port as string?
                # TCPSite should give us a tuple (host, port)
                pass

        # If bound to 0.0.0.0, we need a reachable IP for the base URL
        if self._host == "0.0.0.0":
            public_host = self._get_local_ip()
        else:
            public_host = self._host

        self._base_url = f"http://{public_host}:{actual_port}"
        _LOGGER.info("Media server started at %s", self._base_url)

    async def stop(self) -> None:
        """Stop the HTTP server.

        :returns: None
        """
        if self._site:
            await self._site.stop()
            self._site = None
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._payloads.clear()

    def register_payload(self, payload_id: str, payload: _types.MediaPayload) -> str:
        """Register a media payload to be served.

        :param payload_id: Unique identifier for the payload.
        :param payload: MediaPayload to serve.
        :returns: The full URL to access the payload.
        :raises RuntimeError: If the server is not started.
        """
        if self._base_url is None:
            raise RuntimeError("Media server not started")
        self._payloads[payload_id] = payload
        return f"{self._base_url}/{payload_id}"

    def unregister_payload(self, payload_id: str) -> None:
        """Unregister a media payload.

        :param payload_id: The identifier of the payload to unregister.
        :returns: None
        """
        self._payloads.pop(payload_id, None)

    async def _handle_media(self, request: web.Request) -> web.StreamResponse:
        """Handle incoming requests for media content.

        :param request: The aiohttp Request object.
        :returns: aiohttp Response or FileResponse.
        """
        payload_id = request.match_info["id"]
        payload = self._payloads.get(payload_id)

        if not payload:
            return web.Response(status=404, text="Media not found")

        if payload.url:
            # If it's already a URL, we could redirect, but usually we shouldn't
            # be serving it through here unless proxying is needed.
            # For now, let's just redirect.
            raise web.HTTPFound(payload.url)

        if payload.data:
            return web.Response(
                body=payload.data,
                content_type=payload.mime_type or "application/octet-stream",
            )

        if payload.path:
            if not payload.path.exists():
                return web.Response(status=404, text="File not found")
            return web.FileResponse(
                payload.path,
                chunk_size=256 * 1024,
            )

        return web.Response(status=400, text="Invalid media payload")

    def _get_local_ip(self) -> str:
        """Try to determine the local IP address reachable by the network.

        :returns: Local IP address as a string.
        """
        try:
            # This doesn't actually connect, just picks an interface
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return str(s.getsockname()[0])
        except Exception:
            return "127.0.0.1"
