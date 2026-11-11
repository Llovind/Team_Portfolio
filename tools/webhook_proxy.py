"""Expose only Jenkins' GitHub webhook endpoint through a local tunnel."""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


MAX_BODY = 10 * 1024 * 1024
FORWARDED_HEADERS = (
    "Content-Type", "User-Agent", "X-GitHub-Event", "X-GitHub-Delivery",
    "X-Hub-Signature", "X-Hub-Signature-256", "X-GitHub-Hook-ID",
)


def handler_for(jenkins_port):
    class WebhookProxy(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_error(404)

        def do_POST(self):
            if self.path != "/github-webhook/":
                return self.send_error(404)
            if self.headers.get("Transfer-Encoding"):
                return self.send_error(400, "Transfer-Encoding is not supported")
            if self.headers.get("X-GitHub-Event") not in ("ping", "push"):
                return self.send_error(400, "Only GitHub ping/push events are supported")
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.send_error(415, "Use application/json")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.send_error(400, "Invalid Content-Length")
            if not 0 < length <= MAX_BODY:
                return self.send_error(413, "Payload must be between 1 byte and 10 MiB")
            self.connection.settimeout(15)
            upstream = http.client.HTTPConnection("127.0.0.1", jenkins_port, timeout=15)
            try:
                body = self.rfile.read(length)
                if len(body) != length:
                    return self.send_error(400, "Incomplete payload")
                headers = {name: self.headers[name] for name in FORWARDED_HEADERS if self.headers.get(name)}
                upstream.request("POST", "/github-webhook/", body=body, headers=headers)
                response = upstream.getresponse()
                content = response.read(1024 * 1024)
                self.send_response(response.status)
                self.send_header("Content-Type", response.getheader("Content-Type", "text/plain"))
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except (OSError, http.client.HTTPException):
                self.send_error(502, "Cannot reach the local Jenkins webhook")
            finally:
                upstream.close()

    return WebhookProxy


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--jenkins-port", type=int, default=8081)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(args.jenkins_port))
    print(f"Webhook proxy: http://127.0.0.1:{server.server_port}/github-webhook/", flush=True)
    print("Only POST ping/push webhooks are forwarded. Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
