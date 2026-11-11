import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer


spec = importlib.util.spec_from_file_location("app", Path(__file__).resolve().parents[1] / "backend/app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class ApiTests(unittest.TestCase):
    def setUp(self):
        app.github_cache.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        app.DATA_DIR = self.temp.name
        app.DATA_FILE = str(Path(self.temp.name) / "team_members.json")
        app.UPLOAD_DIR = str(Path(self.temp.name) / "uploads")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, data=None, headers=None, raw=None):
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        request = Request(self.base + path, data=body, method=method,
                          headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            content = response.read()
            result = json.loads(content) if "application/json" in response.headers.get("Content-Type", "") else content
            return response.status, result

    def create(self, nim="123", **fields):
        data = {"name": "Test Member", "nim": nim, "role": "Backend", "skills": ["Python"], **fields}
        status, member = self.request("POST", "/api/members", data)
        self.assertEqual(status, 201, member)
        return member

    def match(self, member):
        return {"If-Match": f'"{member["_version"]}"'}

    def test_crud_and_error_contract(self):
        self.assertEqual(self.request("GET", "/members"), (200, []))
        member = self.create()
        self.assertEqual(self.request("GET", "/api/members")[1], [member])
        self.assertEqual(self.request("POST", "/members", member)[0], 400)
        self.assertEqual(self.request("POST", "/members", raw=b"{")[0], 400)
        self.assertEqual(self.request("GET", "/unknown")[0], 404)
        for query, expected in [("", 400), ("?index=x", 400), ("?index=-1", 404), ("?index=99", 404)]:
            self.assertEqual(self.request("DELETE", "/members" + query)[0], expected)
        status, edited = self.request("PUT", "/members?index=0", {**member, "name": "Edited"}, self.match(member))
        self.assertEqual(status, 200)
        self.assertNotEqual(member["_version"], edited["_version"])
        self.assertEqual(self.request("DELETE", "/members?index=0", headers=self.match(edited))[0], 200)
        self.assertEqual(self.request("GET", "/members")[1], [])

    def test_invalid_types_and_limits(self):
        valid = {"name": "Test", "nim": "123", "role": "Backend", "skills": ["Python"]}
        cases = [{"name": None}, {"role": False}, {"nim": 123}, {"nim": "１２３"},
                 {"skills": [None]}, {"soft_skills": [4]}, {"soft_skills": {}},
                 {"bio": {}}, {"email": "invalid"}, {"github": "javascript:alert(1)"},
                 {"name": "x" * 81}, {"skills": ["x" * 201]},
                 {"activities": [{"category": "project", "title": {}}]},
                 {"activities": [{"category": "project", "title": "x", "photo": "../secret"}]}]
        for fields in cases:
            with self.subTest(fields=fields):
                self.assertEqual(self.request("POST", "/members", {**valid, **fields})[0], 400)
        self.assertEqual(self.request("POST", "/members", raw=b"",
                                      headers={"Content-Length": str(256 * 1024 + 1)})[0], 400)
        self.assertEqual(self.request("GET", "/members")[1], [])

    def test_corrupt_storage_never_overwritten(self):
        invalid_version = json.dumps([{"name": "Test", "nim": "1", "role": "R", "skills": ["P"], "_version": []}]).encode()
        for content in [b"{broken", b"{}", b"[null]", b"\xff", invalid_version]:
            with self.subTest(content=content):
                Path(app.DATA_FILE).write_bytes(content)
                for method, route, data in [("GET", "/members", None), ("GET", "/health", None),
                                             ("POST", "/members", {"name": "T", "nim": "1", "role": "R", "skills": ["P"]}),
                                             ("DELETE", "/members?index=0", None)]:
                    self.assertEqual(self.request(method, route, data)[0], 503)
                    self.assertEqual(Path(app.DATA_FILE).read_bytes(), content)

    def test_failed_write_keeps_original(self):
        member = self.create()
        before = Path(app.DATA_FILE).read_bytes()
        with patch.object(app.os, "replace", side_effect=PermissionError("test")):
            self.assertEqual(self.request("DELETE", "/members?index=0")[0], 503)
        self.assertEqual(Path(app.DATA_FILE).read_bytes(), before)
        self.assertEqual(self.request("GET", "/members")[1], [member])

    def test_stale_updates_and_deletes_rejected(self):
        original = self.create()
        updated = {**original, "bio": "New data from another browser"}
        self.assertEqual(self.request("PUT", "/members?nim=123", updated, self.match(original))[0], 200)
        self.assertEqual(self.request("PUT", "/members?nim=123", original, self.match(original))[0], 409)
        self.assertEqual(self.request("DELETE", "/members?nim=123", headers=self.match(original))[0], 409)
        self.assertEqual(self.request("GET", "/members")[1][0]["bio"], updated["bio"])

    def test_simultaneous_edits_only_one_succeeds(self):
        from concurrent.futures import ThreadPoolExecutor
        member = self.create()
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.request, "PUT", "/members?nim=123",
                                       {**member, "bio": bio}, self.match(member)) for bio in ("First", "Second")]
            self.assertEqual(sorted(f.result()[0] for f in futures), [200, 409])

    def test_data_survives_server_recreation(self):
        member = self.create()
        self.stop_server()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("GET", "/members")[1], [member])

    def test_index_shift_cannot_delete_wrong_member(self):
        first, second = self.create("1"), self.create("2")
        self.request("DELETE", "/members?index=0")
        self.assertEqual(self.request("DELETE", "/members?index=0", headers=self.match(first))[0], 409)
        self.assertEqual(self.request("DELETE", "/members?nim=1", headers=self.match(first))[0], 404)
        self.assertEqual(self.request("GET", "/members")[1], [second])

    def test_legacy_storage_gets_version_without_rewrite(self):
        legacy = {"name": "Legacy", "nim": "1", "role": "R", "skills": ["P"]}
        Path(app.DATA_FILE).write_text(json.dumps([legacy]), encoding="utf-8")
        before = Path(app.DATA_FILE).read_bytes()
        member = self.request("GET", "/members")[1][0]
        self.assertIn("_version", member)
        self.assertEqual(Path(app.DATA_FILE).read_bytes(), before)
        self.assertEqual(self.request("PUT", "/members?nim=1", member, self.match(member))[0], 200)

    def test_photos_and_shared_reference_cleanup(self):
        # A small valid PNG fixture; no external packages required.
        import base64
        image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
        status, upload = self.request("POST", "/uploads", raw=image, headers={"Content-Type": "image/png"})
        self.assertEqual(status, 201)
        url = upload["url"]
        self.assertEqual(self.request("GET", url), (200, image))
        activity = {"category": "project", "title": "Demo", "photo": url}
        self.create("1", activities=[activity])
        self.create("2", activities=[activity])
        self.assertEqual(self.request("DELETE", url)[0], 409)
        self.request("DELETE", "/members?nim=1")
        self.assertEqual(self.request("GET", url)[0], 200)
        self.request("DELETE", "/members?nim=2")
        self.assertEqual(self.request("GET", url)[0], 404)
        self.assertEqual(self.request("POST", "/uploads", raw=b"fake", headers={"Content-Type": "image/png"})[0], 400)

    def github_response(self, data, link=""):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(data).encode()
        response.headers = {"Link": link}
        return response

    def test_github_projects_cache_pagination_and_safe_urls(self):
        response = self.github_response([{"full_name": "demo/project", "html_url": "javascript:alert(1)",
                                         "description": "A project", "language": "Python", "fork": True}],
                                        '<https://api.github.com/next>; rel="next"')
        with patch.object(app, "urlopen", return_value=response) as remote:
            status, data = self.request("GET", "/api/github/repos?username=demo")
            self.assertEqual(status, 200)
            self.assertEqual(data["repositories"][0]["url"], "https://github.com/demo/project")
            self.assertTrue(data["has_next"])
            self.assertTrue(data["repositories"][0]["fork"])
            self.request("GET", "/github/repos?username=DEMO")
            self.assertEqual(remote.call_count, 1)
            self.request("GET", "/github/repos?username=demo&page=2")
            self.assertEqual(remote.call_count, 2)
            self.assertIn("page=2", remote.call_args.args[0].full_url)
            self.assertEqual(remote.call_args.kwargs["timeout"], 8)

    def test_github_invalid_parameters_do_not_call_remote(self):
        with patch.object(app, "urlopen") as remote:
            for query in ["username=../etc", "username=", "username=demo&page=0", "username=demo&page=abc"]:
                self.assertEqual(self.request("GET", "/github/repos?" + query)[0], 400)
            remote.assert_not_called()

    def test_github_errors_and_retry(self):
        for upstream, expected in [(404, 404), (403, 429), (429, 429), (500, 502)]:
            with self.subTest(upstream=upstream):
                error = HTTPError("https://api.github.com", upstream, "Error", {}, None)
                with patch.object(app, "urlopen", side_effect=error):
                    self.assertEqual(self.request("GET", "/github/repos?username=demo")[0], expected)
        with patch.object(app, "urlopen", side_effect=TimeoutError):
            self.assertEqual(self.request("GET", "/github/repos?username=demo")[0], 502)
        with patch.object(app, "urlopen", return_value=self.github_response([])):
            self.assertEqual(self.request("GET", "/github/repos?username=demo")[1]["repositories"], [])

    def test_github_malformed_response_is_not_cached(self):
        for data in [{"message": "unexpected"}, [None], [{"full_name": "../malicious"}]]:
            with patch.object(app, "urlopen", return_value=self.github_response(data)):
                self.assertEqual(self.request("GET", "/github/repos?username=demo")[0], 502)
        self.assertEqual(app.github_cache, {})

    def test_github_cache_expires(self):
        with patch.object(app, "urlopen", return_value=self.github_response([])) as remote:
            with patch.object(app.time, "monotonic", return_value=0):
                self.request("GET", "/github/repos?username=demo")
            with patch.object(app.time, "monotonic", return_value=301):
                self.request("GET", "/github/repos?username=demo")
            self.assertEqual(remote.call_count, 2)


if __name__ == "__main__":
    unittest.main()
