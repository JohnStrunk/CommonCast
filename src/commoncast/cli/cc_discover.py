"""Command-line interface for CommonCast discovery.

This module provides the `cc-discover` command, which discovers and lists
available casting devices on the network using the public CommonCast API.
"""

import argparse
import asyncio
import logging
import sys
from typing import NoReturn

import commoncast

# Configure logging to show only critical errors to avoid polluting output
logging.basicConfig(level=logging.CRITICAL)


async def discover_devices(timeout: float) -> None:
    """Run discovery and print results.

    :param timeout: Time in seconds to wait for discovery.
    """
    print(f"Starting discovery... (waiting {timeout}s)")

    try:
        # Start the registry to begin background discovery tasks.
        # This initializes all enabled backend adapters (like Chromecast).
        await commoncast.start()

        # Wait for devices to respond. Discovery is asynchronous, so we need
        # to give the network time to traffic MDNS/SSDP packets.
        await asyncio.sleep(timeout)

        # Get a snapshot of currently known devices.
        # This returns a list of Device objects known at this exact moment.
        devices = commoncast.list_devices()
    finally:
        # Always stop the registry to clean up background tasks and network sockets.
        await commoncast.stop()

    print(f"\nDiscovered {len(devices)} device(s):")

    if not devices:
        return

    # Determine column widths
    headers = ["Name", "ID", "Type", "Model"]

    # Calculate max width for each column, starting with header length
    widths = [len(h) for h in headers]
    rows: list[list[str]] = []

    for d in devices:
        row = [d.name, str(d.id), d.transport, d.model or "N/A"]
        rows.append(row)
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(col))

    # Add some padding
    widths = [w + 2 for w in widths]

    # Create format string
    fmt = "".join(f"{{:<{w}}}" for w in widths)

    # Print table
    print("-" * sum(widths))
    print(fmt.format(*headers))
    print("-" * sum(widths))

    for row in rows:
        print(fmt.format(*row))
    print("-" * sum(widths))


def main() -> NoReturn:
    """Entry point for cc-discover command."""
    parser = argparse.ArgumentParser(
        description="Discover and list CommonCast devices."
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=15.0,
        help="Discovery timeout in seconds (default: 15.0)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(discover_devices(args.timeout))
    except KeyboardInterrupt:
        print("\nDiscovery cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError during discovery: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
