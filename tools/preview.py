"""Local application preview without Docker; data stays in tmp/preview-data."""
import functools
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import app

app.DATA_DIR = str(ROOT / "tmp/preview-data")
app.DATA_FILE = str(Path(app.DATA_DIR) / "team_members.json")
app.UPLOAD_DIR = str(Path(app.DATA_DIR) / "uploads")


class PreviewHandler(app.Handler, SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            return app.Handler.do_GET(self)
        return SimpleHTTPRequestHandler.do_GET(self)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    handler = functools.partial(PreviewHandler, directory=str(ROOT / "frontend"))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Preview: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
