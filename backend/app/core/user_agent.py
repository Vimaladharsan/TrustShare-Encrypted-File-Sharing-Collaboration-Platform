"""A readable device name from a browser's User-Agent header, e.g. "Chrome on Windows".

Deliberately simple (no third-party database): good enough to recognise your own devices in the
Devices list. The order matters – Edge and Opera also say "Chrome", and Chrome also says "Safari".
"""

BROWSERS = [
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
]
SYSTEMS = [
    ("Windows", "Windows"),
    ("Android", "Android"),
    ("iPhone", "iOS"),
    ("iPad", "iPadOS"),
    ("Mac OS X", "macOS"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
]


def describe_device(user_agent: str) -> dict[str, str]:
    """{"browser", "os", "kind"} – kind is "mobile" or "desktop"."""
    ua = user_agent or ""
    browser = next((name for marker, name in BROWSERS if marker in ua), "Unknown browser")
    system = next((name for marker, name in SYSTEMS if marker in ua), "Unknown system")
    mobile = any(marker in ua for marker in ("Mobile", "Android", "iPhone", "iPad"))
    return {"browser": browser, "os": system, "kind": "mobile" if mobile else "desktop"}
