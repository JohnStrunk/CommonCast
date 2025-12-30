"""Unit tests for commoncast.types module."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import commoncast.types as _types


def test_media_metadata() -> None:
    """Test MediaMetadata creation.

    :returns: None
    """
    img = _types.MediaImage(url="http://example.com/art.jpg", width=100, height=100)
    meta = _types.MediaMetadata(
        title="Test Title",
        subtitle="Subtitle",
        images=[img],
        type="video",
        extra={"custom": "data"},
    )
    assert meta.title == "Test Title"
    assert meta.images[0].url == "http://example.com/art.jpg"
    assert meta.extra["custom"] == "data"


def test_media_payload_from_bytes() -> None:
    """Test creating MediaPayload from raw bytes.

    :returns: None
    """
    data = b"hello world"
    payload = _types.MediaPayload.from_bytes(data, mime_type="text/plain")
    assert payload.data == data
    assert payload.mime_type == "text/plain"
    assert payload.size == len(data)
    assert payload.path is None
    assert payload.url is None
    assert payload.metadata is None


def test_media_payload_from_path(tmp_path: Path) -> None:
    """Test creating MediaPayload from a file path.

    :param tmp_path: The tmp_path fixture.
    :returns: None
    """
    f = tmp_path / "test.txt"
    f.write_text("hello file")
    payload = _types.MediaPayload.from_path(f, mime_type="text/plain")
    assert payload.path == f
    assert payload.mime_type == "text/plain"
    assert payload.size == 10
    assert payload.data is None
    assert payload.url is None

    # Test path that doesn't exist
    payload_missing = _types.MediaPayload.from_path(
        "/tmp/non-existent-file", mime_type="text/plain"
    )
    assert payload_missing.path == Path("/tmp/non-existent-file")
    assert payload_missing.size is None


def test_media_payload_from_url() -> None:
    """Test creating MediaPayload from a URL.

    :returns: None
    """
    url = "http://example.com/movie.mp4"
    meta = _types.MediaMetadata(title="Movie")
    payload = _types.MediaPayload.from_url(url, mime_type="video/mp4", metadata=meta)
    assert payload.url == url
    assert payload.mime_type == "video/mp4"
    assert payload.size is None
    assert payload.data is None
    assert payload.path is None
    assert payload.metadata is not None
    assert payload.metadata.title == "Movie"


def test_device_creation() -> None:
    """Test Device initialization.

    :returns: None
    """
    dev = _types.Device(
        id=_types.DeviceID("dev1"),
        name="Living Room",
        model="Chromecast",
        transport="chromecast",
        capabilities={_types.Capability("video"), _types.Capability("audio")},
        transport_info={"ip": "192.168.1.10"},
    )
    assert dev.id == "dev1"
    assert dev.name == "Living Room"
    assert "video" in dev.capabilities


@pytest.mark.asyncio
async def test_device_send_media() -> None:
    """Test Device.send_media delegation and title backfilling.

    :returns: None
    """
    dev = _types.Device(
        id=_types.DeviceID("dev1"),
        name="Test",
        model=None,
        transport="test",
        capabilities=set(),
        transport_info={},
    )
    payload = _types.MediaPayload.from_url("http://url")

    with patch("commoncast.registry.default_registry.send_media") as mock_send:
        mock_send.return_value = _types.SendResult(success=True)

        # Test with legacy title and NO metadata
        await dev.send_media(payload, title="Legacy Title")
        assert payload.metadata is not None
        assert payload.metadata.title == "Legacy Title"

        # Test with legacy title and ALREADY EXISTING metadata without title
        payload.metadata = _types.MediaMetadata(subtitle="Sub")
        await dev.send_media(payload, title="New Title")
        assert payload.metadata.title == "New Title"
        assert payload.metadata.subtitle == "Sub"


def test_device_send_media_sync() -> None:
    """Test Device.send_media_sync.

    :returns: None
    """
    dev = _types.Device(
        id=_types.DeviceID("dev1"),
        name="Test",
        model=None,
        transport="test",
        capabilities=set(),
        transport_info={},
    )
    payload = _types.MediaPayload.from_url("http://url")

    def _run_mock(coro: Any) -> Any:
        coro.close()
        return _types.SendResult(success=True)

    with patch("asyncio.run", side_effect=_run_mock) as mock_run:
        res = dev.send_media_sync(payload)
        assert res.success
        assert mock_run.called


def test_send_result_init() -> None:
    """Test SendResult initialization.

    :returns: None
    """
    res = _types.SendResult(success=True, metadata={"foo": "bar"})
    assert res.success
    assert res.metadata == {"foo": "bar"}

    res2 = _types.SendResult(success=False, reason="fail")
    assert not res2.success
    assert res2.reason == "fail"
    assert res2.metadata == {}
