"""device-connection: reconnect stress flow (success-rate over N cycles).

Scenario:
  disconnect -> reconnect -> disconnect -> reconnect ... repeat 10x
  and report the connect success rate.

This measures reconnect reliability over real BLE. Requires a paired device
nearby. The test asserts a minimum success rate (default 80%, override with
RECONNECT_MIN_RATE) so a flaky link is caught but a single miss doesn't fail it.

Run from Ghostty, logged in, Heidi foreground, device on:
    RECONNECT_CYCLES=10 pytest tests/device-connection/test_reconnect_stress_flow.py -v -s
"""
import os
import time

import pytest
import xa11y

from pages import DevicePage

pytestmark = [pytest.mark.device_connection, pytest.mark.needs_device,
              pytest.mark.slow, pytest.mark.timeout(900)]


def _cycles() -> int:
    return int(os.environ.get("RECONNECT_CYCLES", "10"))


def _min_rate() -> float:
    return float(os.environ.get("RECONNECT_MIN_RATE", "0.8"))


def test_reconnect_stress(devices: DevicePage, require_device):
    cycles = _cycles()
    successes = 0
    results = []

    # Ensure we start connected.
    if not devices.is_connected():
        devices.reconnect()
        if not devices.wait_connected(timeout=40):
            pytest.skip("Could not establish an initial connection (device nearby?)")

    for i in range(cycles):
        # disconnect
        if not devices.disconnect():
            results.append((i, "disconnect-click-failed"))
            continue
        if not devices.wait_disconnected(timeout=30):
            results.append((i, "did-not-disconnect"))
            continue
        time.sleep(1)

        # reconnect
        if not devices.reconnect():
            results.append((i, "reconnect-click-failed"))
            continue
        ok = devices.wait_connected(timeout=40)
        results.append((i, "connected" if ok else "connect-timeout"))
        if ok:
            successes += 1
        time.sleep(1)

    rate = successes / cycles
    print(f"\nreconnect stress: {successes}/{cycles} = {rate:.0%}")
    for i, outcome in results:
        print(f"  cycle {i+1}: {outcome}")

    assert rate >= _min_rate(), (
        f"Reconnect success rate {rate:.0%} below {_min_rate():.0%} "
        f"({successes}/{cycles}). Details: {results}"
    )
