"""Tests for the cc-discover CLI tool."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _pytest.capture import CaptureFixture

from commoncast.cli.cc_discover import discover_devices, main
from commoncast.types import Device, DeviceID


@pytest.mark.asyncio
async def test_discover_devices_no_devices(capsys: CaptureFixture[str]) -> None:
    """Test discover_devices when no devices are found."""
    with (
        patch("commoncast.start", new_callable=AsyncMock) as mock_start,
        patch("commoncast.list_devices", return_value=[]) as mock_list,
        patch("commoncast.stop", new_callable=AsyncMock) as mock_stop,
    ):
        await discover_devices(0.1)

        mock_start.assert_called_once()
        mock_list.assert_called_once()
        mock_stop.assert_called_once()

        captured = capsys.readouterr()
        assert "Discovered 0 device(s):" in captured.out


@pytest.mark.asyncio
async def test_discover_devices_with_results(capsys: CaptureFixture[str]) -> None:
    """Test discover_devices when devices are found."""
    devices = [
        Device(
            id=DeviceID("id1"),
            name="Device 1",
            model="Model 1",
            transport="test",
            capabilities=set(),
            transport_info={},
        ),
        Device(
            id=DeviceID("id2"),
            name="Device 2",
            model=None,
            transport="test",
            capabilities=set(),
            transport_info={},
        ),
    ]

    with (
        patch("commoncast.start", new_callable=AsyncMock),
        patch("commoncast.list_devices", return_value=devices),
        patch("commoncast.stop", new_callable=AsyncMock),
    ):
        await discover_devices(0.1)

        captured = capsys.readouterr()
        assert "Discovered 2 device(s):" in captured.out
        assert "Device 1" in captured.out
        assert "Device 2" in captured.out
        assert "id1" in captured.out
        assert "id2" in captured.out
        assert "N/A" in captured.out  # for the None model


def test_main_success() -> None:
    """Test main function successful execution."""

    def _run_mock(coro: Any) -> None:
        coro.close()

    with (
        patch("argparse.ArgumentParser.parse_args") as mock_args,
        patch("asyncio.run", side_effect=_run_mock) as mock_run,
        patch("sys.exit", side_effect=SystemExit) as mock_exit,
    ):
        mock_args.return_value = MagicMock(timeout=5.0, verbose=0)

        with pytest.raises(SystemExit):
            main()

        mock_run.assert_called_once()
        mock_exit.assert_called_with(0)


def test_main_keyboard_interrupt(capsys: CaptureFixture[str]) -> None:
    """Test main function handling KeyboardInterrupt."""

    def _run_mock(coro: Any) -> None:
        coro.close()
        raise KeyboardInterrupt

    with (
        patch("argparse.ArgumentParser.parse_args") as mock_args,
        patch("asyncio.run", side_effect=_run_mock),
        patch("sys.exit", side_effect=SystemExit) as mock_exit,
    ):
        mock_args.return_value = MagicMock(timeout=5.0, verbose=0)

        with pytest.raises(SystemExit):
            main()

        mock_exit.assert_called_with(130)
        captured = capsys.readouterr()
        assert "Discovery cancelled by user." in captured.out


def test_main_exception(capsys: CaptureFixture[str]) -> None:
    """Test main function handling generic exceptions."""

    def _run_mock(coro: Any) -> None:
        coro.close()
        raise RuntimeError("something went wrong")

    with (
        patch("argparse.ArgumentParser.parse_args") as mock_args,
        patch("asyncio.run", side_effect=_run_mock),
        patch("sys.exit", side_effect=SystemExit) as mock_exit,
    ):
        mock_args.return_value = MagicMock(timeout=5.0, verbose=0)

        with pytest.raises(SystemExit):
            main()

        mock_exit.assert_called_with(1)
        captured = capsys.readouterr()
        assert "Error during discovery: something went wrong" in captured.err


@pytest.mark.parametrize(
    "verbose_count,expected_level",
    [
        (0, 50),  # CRITICAL
        (1, 20),  # INFO
        (2, 10),  # DEBUG
        (3, 10),  # DEBUG (more than 2 stays at DEBUG)
    ],
)
def test_main_verbosity(verbose_count: int, expected_level: int) -> None:
    """Test main function configures logging level based on verbosity."""

    def _run_mock(coro: Any) -> None:
        coro.close()

    with (
        patch("argparse.ArgumentParser.parse_args") as mock_args,
        patch("asyncio.run", side_effect=_run_mock),
        patch("sys.exit", side_effect=SystemExit),
        patch("logging.basicConfig") as mock_logging,
    ):
        mock_args.return_value = MagicMock(timeout=5.0, verbose=verbose_count)

        with pytest.raises(SystemExit):
            main()

        # Check that basicConfig was called with the expected level
        # kwargs is the second element of call_args
        assert mock_logging.call_args[1]["level"] == expected_level
