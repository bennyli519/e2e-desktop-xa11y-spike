"""Cross-platform helpers so the suite runs on macOS and Windows.

xa11y itself is cross-platform (macOS AXUIElement / Windows UIA). The friction is
the OS glue around it: bringing the app to the foreground, audio injection, screen
recording. This module isolates the per-OS bits so specs and Page Objects stay
platform-agnostic.

- macOS: needs the app frontmost (a backgrounded WKWebView blanks its AX tree),
  done via `osascript ... activate`.
- Windows: UI Automation reads background windows too, so activation is best-effort
  (SetForegroundWindow via PowerShell) and usually unnecessary.
"""
import subprocess
import sys

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"


def activate_app(app_name: str = "Heidi") -> None:
    """Bring the named app to the foreground. No-op-safe on any platform.

    On macOS this is REQUIRED before reading the AX tree (backgrounded WKWebview
    stops publishing it). On Windows UIA reads background windows, so this is a
    best-effort nicety.
    """
    if IS_MAC:
        subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            capture_output=True,
        )
    elif IS_WINDOWS:
        # Best-effort: focus the first window whose title contains app_name.
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "$p=Get-Process | Where-Object {$_.MainWindowTitle -like '*"
            + app_name
            + "*'} | Select-Object -First 1;"
            "if ($p) {"
            "  Add-Type 'using System;using System.Runtime.InteropServices;"
            "public class W{[DllImport(\"user32.dll\")]public static extern bool "
            "SetForegroundWindow(IntPtr h);}';"
            "  [W]::SetForegroundWindow($p.MainWindowHandle) | Out-Null }"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True)
    # other platforms: no-op


def quit_app(app_name: str = "Heidi") -> None:
    """Quit the named app (used by the startup-autoconnect flow)."""
    if IS_MAC:
        subprocess.run(["osascript", "-e", f'quit app "{app_name}"'],
                       capture_output=True)
    elif IS_WINDOWS:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-Process | Where-Object {{$_.MainWindowTitle -like '*{app_name}*'}} "
             f"| Stop-Process -Force"],
            capture_output=True,
        )


def launch_app(app_name: str = "Heidi") -> None:
    """Launch the named app (portable, no hard-coded path on macOS)."""
    if IS_MAC:
        subprocess.run(["open", "-a", app_name], capture_output=True)
    elif IS_WINDOWS:
        # Windows: rely on the app already running, or start via Start Menu name.
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Start-Process '{app_name}'"], capture_output=True)
