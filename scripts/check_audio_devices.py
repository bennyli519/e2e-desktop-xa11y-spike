"""Print audio endpoints and suggest the recording E2E input-device env var."""
import os
import platform
import subprocess
from dataclasses import dataclass


VIRTUAL_INPUT_HINTS = [
    "CABLE Output",
    "BlackHole",
]
VIRTUAL_PLAYBACK_HINTS = [
    "CABLE Input",
    "CABLE In",
]


@dataclass(frozen=True)
class WindowsAudioEndpoint:
    name: str
    direction: str


def _windows_audio_endpoints() -> list[WindowsAudioEndpoint]:
    script = r"""
    Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue |
      Sort-Object FriendlyName |
      ForEach-Object {
        $direction = if ($_.InstanceId -like 'SWD\MMDEVAPI\{0.0.1.*') {
          'input'
        } elseif ($_.InstanceId -like 'SWD\MMDEVAPI\{0.0.0.*') {
          'output'
        } else {
          'unknown'
        }
        "$direction`t$($_.FriendlyName)"
      }
    """
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        print(f"Failed to query Windows audio endpoints: {exc}")
        return []

    if result.returncode != 0:
        print(result.stderr.strip() or "Get-PnpDevice failed")
        return []

    endpoints: list[WindowsAudioEndpoint] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        direction, _, name = line.partition("\t")
        endpoints.append(WindowsAudioEndpoint(name=name.strip(), direction=direction))
    return endpoints


def _matching_virtual_inputs(endpoints: list[WindowsAudioEndpoint]) -> list[str]:
    matches: list[str] = []
    for endpoint in endpoints:
        if endpoint.direction != "input":
            continue
        lowered = endpoint.name.lower()
        if any(hint.lower() in lowered for hint in VIRTUAL_INPUT_HINTS):
            matches.append(endpoint.name)
    return matches


def _matching_virtual_playbacks(endpoints: list[WindowsAudioEndpoint]) -> list[str]:
    matches: list[str] = []
    for hint in VIRTUAL_PLAYBACK_HINTS:
        for endpoint in endpoints:
            if endpoint.direction != "output":
                continue
            if hint.lower() in endpoint.name.lower() and endpoint.name not in matches:
                matches.append(endpoint.name)
    return matches


def main() -> int:
    system = platform.system()
    if system != "Windows":
        print(f"{system}: set HEIDI_E2E_RECORDING_INPUT_DEVICE to your virtual input.")
        print('macOS example: HEIDI_E2E_RECORDING_INPUT_DEVICE="BlackHole 2ch"')
        return 0

    endpoints = _windows_audio_endpoints()
    print("Windows audio endpoints:")
    if endpoints:
        for endpoint in endpoints:
            print(f"  - [{endpoint.direction}] {endpoint.name}")
    else:
        print("  <none found>")

    configured = os.environ.get("HEIDI_E2E_RECORDING_INPUT_DEVICE")
    if configured:
        found = any(
            endpoint.direction == "input"
            and configured.lower() in endpoint.name.lower()
            for endpoint in endpoints
        )
        status = "found" if found else "not found"
        print(f"\nConfigured HEIDI_E2E_RECORDING_INPUT_DEVICE={configured!r}: {status}")

    matches = _matching_virtual_inputs(endpoints)
    if not matches:
        print(
            "\nNo VB-CABLE/BlackHole-style virtual input was found. "
            "Install VB-Audio VB-CABLE, then look for a recording endpoint named "
            "'CABLE Output (VB-Audio Virtual Cable)'."
        )
        return 1

    print("\nSuggested recording E2E input device:")
    print(f'  $env:HEIDI_E2E_RECORDING_INPUT_DEVICE = "{matches[0]}"')
    playback_matches = _matching_virtual_playbacks(endpoints)
    if playback_matches:
        print("\nSuggested audio-fixture playback device:")
        print(f'  $env:HEIDI_E2E_AUDIO_PLAYBACK_DEVICE = "{playback_matches[0]}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
