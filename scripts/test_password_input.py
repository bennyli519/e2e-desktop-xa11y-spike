"""Isolated diagnostic: type the password into the focused Chrome field,
then STOP (no submit) so you can eyeball whether the characters are correct.

Prereq: Chrome is on the Auth0 'Enter your password' page.

Run:
    python scripts/test_password_input.py

Reads the password ONLY from .env.e2e (ignores any stale env var), forces a
Latin/ABC input source to defeat the Chinese IME, then types char-by-char
via xa11y InputSim (low-level CGEvent). Does NOT submit.
"""
import subprocess
import sys
import time
from pathlib import Path

import xa11y


def _force_abc_input_source() -> None:
    """Force the active keyboard input source to a Latin/ABC layout.

    A Chinese IME intercepts ASCII keystrokes (e.g. 'a1' -> '啊'). We pick the
    first available ASCII-capable Latin layout (ABC, U.S., etc.) via TIS.
    """
    swift = r'''
    import Carbon
    // Preferred IDs in order
    let preferred = [
        "com.apple.keylayout.ABC",
        "com.apple.keylayout.US",
        "com.apple.keylayout.USExtended",
        "com.apple.keylayout.British",
    ]
    guard let cf = TISCreateInputSourceList(nil, false)?.takeRetainedValue(),
          let sources = cf as? [TISInputSource] else {
        print("no input sources"); exit(0)
    }
    func id(_ s: TISInputSource) -> String? {
        guard let ptr = TISGetInputSourceProperty(s, kTISPropertyInputSourceID) else { return nil }
        return Unmanaged<CFString>.fromOpaque(ptr).takeUnretainedValue() as String
    }
    // Try preferred IDs first
    for want in preferred {
        if let s = sources.first(where: { id($0) == want }) {
            TISSelectInputSource(s)
            print("selected \(want)")
            exit(0)
        }
    }
    // Fallback: any keylayout.* (Latin layouts live under keylayout)
    if let s = sources.first(where: { (id($0) ?? "").hasPrefix("com.apple.keylayout.") }) {
        print("selected fallback \(id(s) ?? "?")")
        TISSelectInputSource(s)
        exit(0)
    }
    print("no Latin layout found")
    '''
    try:
        r = subprocess.run(["swift", "-"], input=swift, capture_output=True, text=True, timeout=25)
        out = (r.stdout.strip() + " " + r.stderr.strip()).strip()
        print(f"  input source: {out}")
    except Exception as e:
        print(f"  input source switch failed: {e}")


def load_password() -> str:
    """Read password ONLY from .env.e2e — ignore env vars to avoid stale values."""
    env_file = Path(__file__).resolve().parent.parent / ".env.e2e"
    if not env_file.exists():
        sys.exit(f"No .env.e2e at {env_file}")
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("HEIDI_E2E_PASSWORD="):
            return line.partition("=")[2].strip()
    sys.exit("HEIDI_E2E_PASSWORD not found in .env.e2e")


def main():
    password = load_password()
    print(f"Password length: {len(password)}")
    print(f"Password repr:   {password!r}")

    chrome = xa11y.App.by_name("Google Chrome", timeout=5.0)
    print(f"Chrome pid={chrome.pid}")

    sim = xa11y.input_sim()

    subprocess.run(
        ["osascript", "-e", 'tell application "Google Chrome" to activate'],
        capture_output=True,
    )
    time.sleep(1.5)

    print("Forcing Latin/ABC input source (defeat Chinese IME)...")
    _force_abc_input_source()
    time.sleep(0.5)

    print("Clearing field, then typing char-by-char (NOT submitting)...")
    print("Click the eye icon to reveal the field.")

    for _ in range(30):
        sim.press("Backspace")
        time.sleep(0.02)
    time.sleep(0.3)

    for i, ch in enumerate(password):
        sim.type_text(ch)
        print(f"  [{i}] typed {ch!r}")
        time.sleep(0.1)
    time.sleep(1.0)

    print("\nDONE. Inspect the field. Did it match the password exactly?")


if __name__ == "__main__":
    main()
