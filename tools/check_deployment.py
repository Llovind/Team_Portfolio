"""Read-only deployment check. Default URL resolves frontend through Docker DNS."""
import json
import os
from urllib.request import urlopen


def check(base_url):
    for route in ("/", "/anggota.html", "/profile.html", "/css/style.css",
                  "/js/api.js", "/js/github.js", "/js/dashboard.js", "/js/profile.js"):
        with urlopen(base_url + route, timeout=10) as response:
            if response.status != 200 or not response.read():
                raise RuntimeError(f"Failed asset check: {route}")
            content_type = response.headers.get_content_type()
            expected = ("text/css",) if route.endswith(".css") else (
                "application/javascript", "text/javascript"
            ) if route.endswith(".js") else ("text/html",)
            if content_type not in expected:
                raise RuntimeError(f"Unexpected content type for {route}: {content_type}")
        print(f"PASS {route}", flush=True)
    for route in ("/api/health", "/api/members"):
        with urlopen(base_url + route, timeout=10) as response:
            data = json.load(response)
        if route.endswith("health") and data != {"status": "ok"}:
            raise RuntimeError("Backend health is not OK")
        if route.endswith("members") and not isinstance(data, list):
            raise RuntimeError("Member response must be an array")
        print(f"PASS {route}", flush=True)


if __name__ == "__main__":
    check(os.environ.get("CHECK_BASE_URL", "http://frontend").rstrip("/"))
