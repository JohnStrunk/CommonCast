"""Tests for the embedded media server."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

import commoncast.server as _server
import commoncast.types as _types


@pytest.mark.asyncio
async def test_server_lifecycle() -> None:
    """Test starting and stopping the media server.

    :returns: None
    """
    server = _server.MediaServer(host="127.0.0.1", port=0)
    await server.start()
    assert server._base_url is not None  # type: ignore[reportPrivateUsage]
    assert "127.0.0.1" in server._base_url  # type: ignore[reportPrivateUsage]

    # Test starting again (should be no-op)
    await server.start()

    await server.stop()
    # Test stopping again (should be no-op)
    await server.stop()


@pytest.mark.asyncio
async def test_server_string_address() -> None:
    """Test starting the media server with a string address reported by runner.

    :returns: None
    """
    server = _server.MediaServer(host="127.0.0.1", port=0)

    # Actually, it's easier to mock just before start
    with patch("aiohttp.web.TCPSite.start", new_callable=AsyncMock):
        with patch("aiohttp.web.TCPSite.stop", new_callable=AsyncMock):
            with patch("aiohttp.web.AppRunner") as mock_runner_cls:
                mock_runner = mock_runner_cls.return_value
                mock_runner.addresses = ["some_string"]
                mock_runner.setup = AsyncMock()
                mock_runner.cleanup = AsyncMock()

                await server.start()
                # It should have passed through line 66 and used original port
                assert server._base_url is not None  # type: ignore[reportPrivateUsage]
                await server.stop()


@pytest.mark.asyncio
async def test_serve_bytes() -> None:
    """Test serving media from bytes.

    :returns: None
    """
    server = _server.MediaServer(host="127.0.0.1", port=0)
    await server.start()

    payload = _types.MediaPayload.from_bytes(b"hello world", mime_type="text/plain")
    url = server.register_payload("test1", payload)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 200
            assert await response.text() == "hello world"
            assert response.content_type == "text/plain"

    await server.stop()


@pytest.mark.asyncio
async def test_serve_file(tmp_path: Path) -> None:
    """Test serving media from a file.

    :param tmp_path: The tmp_path fixture.
    :returns: None
    """
    test_file = tmp_path / "test.txt"
    test_file.write_text("file content")

    server = _server.MediaServer(host="127.0.0.1", port=0)
    await server.start()

    payload = _types.MediaPayload.from_path(test_file, mime_type="text/plain")
    url = server.register_payload("test2", payload)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 200
            assert await response.text() == "file content"

    # Test file not found
    test_file.unlink()
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 404

    await server.stop()


@pytest.mark.asyncio
async def test_serve_url() -> None:
    """Test redirecting to a remote URL.

    :returns: None
    """
    server = _server.MediaServer(host="127.0.0.1", port=0)
    await server.start()

    payload = _types.MediaPayload.from_url("https://example.com/media.mp4")
    url = server.register_payload("test3", payload)

    async with aiohttp.ClientSession() as session:
        # allow_redirects=False to check the redirect
        async with session.get(url, allow_redirects=False) as response:
            assert response.status == 302
            assert response.headers["Location"] == "https://example.com/media.mp4"

    await server.stop()


@pytest.mark.asyncio
async def test_not_found() -> None:
    """Test 404 for unknown payload.

    :returns: None
    """
    server = _server.MediaServer(host="127.0.0.1", port=0)
    await server.start()

    url = f"{server._base_url}/unknown"  # type: ignore[reportPrivateUsage]

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 404

    await server.stop()


@pytest.mark.asyncio
async def test_unregister_payload() -> None:
    """Test unregistering a payload.

    :returns: None
    """
    server = _server.MediaServer(host="127.0.0.1", port=0)
    await server.start()

    payload = _types.MediaPayload.from_bytes(b"data")
    url = server.register_payload("test4", payload)

    server.unregister_payload("test4")

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 404

    await server.stop()


@pytest.mark.asyncio
async def test_register_not_started() -> None:
    """Test that register_payload raises RuntimeError if server not started.

    :returns: None
    """
    server = _server.MediaServer()
    payload = _types.MediaPayload.from_bytes(b"data")
    with pytest.raises(RuntimeError, match="Media server not started"):
        server.register_payload("id", payload)


@pytest.mark.asyncio
async def test_invalid_payload() -> None:
    """Test handling of an invalid payload.

    :returns: None
    """
    server = _server.MediaServer(host="127.0.0.1", port=0)
    await server.start()

    # Manually create a payload with nothing set
    payload = _types.MediaPayload()
    url = server.register_payload("invalid", payload)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 400

    await server.stop()


@pytest.mark.asyncio
async def test_server_bind_any() -> None:
    """Test starting the media server bound to 0.0.0.0.

    :returns: None
    """
    server = _server.MediaServer(host="0.0.0.0", port=0)
    with patch.object(server, "_get_local_ip", return_value="1.2.3.4") as mock_get_ip:
        await server.start()
        assert server._base_url is not None  # type: ignore[reportPrivateUsage]
        assert "1.2.3.4" in server._base_url  # type: ignore[reportPrivateUsage]
        mock_get_ip.assert_called_once()
        await server.stop()


def test_get_local_ip_fallback() -> None:
    """Test local IP fallback when socket fails.

    :returns: None
    """
    server = _server.MediaServer()
    with patch("socket.socket") as mock_socket:
        mock_socket.side_effect = Exception("test")
        ip = server._get_local_ip()  # type: ignore[reportPrivateUsage]
        assert ip == "127.0.0.1"
