from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from webhook_proxy import handler_for


class WebhookProxyTests(unittest.TestCase):
    def setUp(self):
        self.received = []
        received = self.received

        class JenkinsStub(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append((self.path, body, dict(self.headers)))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), JenkinsStub)
        self.proxy = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.upstream.server_port))
        for server in (self.upstream, self.proxy):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(self.stop, server, thread)
        self.base = f"http://127.0.0.1:{self.proxy.server_port}"

    def stop(self, server, thread):
        server.shutdown()
        server.server_close()
        thread.join()

    def request(self, route, method="POST", headers=None, body=b'{"test":true}'):
        request = Request(self.base + route, method=method, data=body if method == "POST" else None,
                          headers={"Content-Type": "application/json", "X-GitHub-Event": "push", **(headers or {})})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    def test_push_body_and_signature_preserved_without_forwarding_authorization(self):
        payload = b'{ "ref": "refs/heads/main" }'
        self.assertEqual(self.request("/github-webhook/", body=payload,
                                      headers={"X-Hub-Signature-256": "sha256=example", "Authorization": "Basic private"}), (200, b"ok"))
        path, body, headers = self.received[0]
        self.assertEqual(path, "/github-webhook/")
        self.assertEqual(body, payload)
        self.assertEqual(headers["X-Hub-Signature-256"], "sha256=example")
        self.assertNotIn("Authorization", headers)

    def test_dashboard_login_and_other_paths_are_not_exposed(self):
        for path in ("/", "/login", "/script", "/github-webhook/../script"):
            self.assertEqual(self.request(path)[0], 404)
            self.assertEqual(self.request(path, method="GET")[0], 404)
        self.assertEqual(self.received, [])

    def test_ping_is_allowed_and_other_events_are_rejected(self):
        self.assertEqual(self.request("/github-webhook/", headers={"X-GitHub-Event": "ping"})[0], 200)
        self.assertEqual(self.request("/github-webhook/", headers={"X-GitHub-Event": "issues"})[0], 400)
        self.assertEqual(len(self.received), 1)

    def test_wrong_content_type_is_not_forwarded(self):
        self.assertEqual(self.request("/github-webhook/", headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.received, [])


if __name__ == "__main__":
    unittest.main()
