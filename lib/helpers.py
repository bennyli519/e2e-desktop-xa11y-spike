"""Shared low-level helpers for Page Objects."""
import xa11y


def click_first_match(app: xa11y.App, selectors: list[str]) -> bool:
    """Try each selector in order; press the first that exists.

    Returns True if something was clicked. Used by Page Objects so a single
    logical action can survive role/label differences (the official xa11y
    portable-selector pattern, applied as a fallback chain).
    """
    for sel in selectors:
        try:
            loc = app.locator(sel)
            if loc.exists():
                loc.press()
                return True
        except Exception:
            continue
    return False
