"""Verify Docker using disposable containers, network, volume, and test records."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import uuid


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-username", help="Also require a live GitHub request to succeed")
    parser.add_argument("--config-only", action="store_true", help="Validate isolated configuration without running Docker containers")
    args = parser.parse_args()
    if not args.config_only:
        try:
            subprocess.run(["docker", "info"], check=True, stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            raise SystemExit("Docker engine is unavailable to this terminal. Run from a local account with Docker Desktop access. No containers or data were changed.")
    project = "team-test-" + uuid.uuid4().hex[:10]
    network, volume = project + "-net", project + "-data"
    env = {**os.environ, "FRONTEND_PORT": "0"}
    (ROOT / "tmp").mkdir(exist_ok=True)
    report = {"project": project, "status": "running", "checks": []}
    marker = ROOT / "frontend" / (".bind-mount-" + project + ".txt")
    with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as directory:
        override = Path(directory) / "compose.override.json"
        override.write_text(json.dumps({
            "services": {
                "backend": {"container_name": project + "-backend"},
                "frontend": {"container_name": project + "-frontend"},
            },
            "volumes": {"team-profile-data": {"name": volume}},
            "networks": {"app-net": {"name": network}},
        }), encoding="utf-8")
        command = ["docker", "compose", "-p", project, "-f", str(ROOT / "docker-compose.yml"), "-f", str(override)]

        def compose(*arguments, capture=False):
            result = subprocess.run(command + list(arguments), cwd=ROOT, env=env, check=True,
                                    text=True, stdout=subprocess.PIPE if capture else None)
            return result.stdout.strip() if capture else None

        def passed(label):
            report["checks"].append(label)
            print("PASS " + label, flush=True)

        safe_to_cleanup = False
        try:
            config = json.loads(compose("config", "--format", "json", capture=True))
            # Verify targets before any operation that can create or remove resources.
            if config["volumes"]["team-profile-data"]["name"] != volume:
                raise RuntimeError("Test volume isolation failed")
            if config["networks"]["app-net"]["name"] != network:
                raise RuntimeError("Test network isolation failed")
            if not all(service["container_name"].startswith(project + "-") for service in config["services"].values()):
                raise RuntimeError("Test container isolation failed")
            safe_to_cleanup = True
            passed("isolated test resource names")
            if args.config_only:
                report["status"] = "configuration-validated"
                return
            compose("up", "-d", "--build", "--wait", "--wait-timeout", "120")
            address = compose("port", "frontend", "80", capture=True).splitlines()[0]
            base = "http://127.0.0.1:" + address.rsplit(":", 1)[1]

            def request(method, route, data=None, image=None):
                body = image if image is not None else json.dumps(data).encode() if data is not None else None
                headers = {"Content-Type": "image/png" if image is not None else "application/json"}
                with urlopen(Request(base + route, data=body, method=method, headers=headers), timeout=12) as response:
                    content = response.read()
                    return json.loads(content) if "application/json" in response.headers.get("Content-Type", "") else content

            assert request("GET", "/api/health") == {"status": "ok"}
            assert isinstance(request("GET", "/api/members"), list)
            assert b"Team Profile Showcase" in request("GET", "/")
            passed("Nginx UI and proxy to backend through service DNS")
            backend_id = compose("ps", "-q", "backend", capture=True)
            inspect = json.loads(subprocess.check_output(["docker", "inspect", backend_id], text=True))[0]
            assert any(m["Type"] == "volume" and m["Name"] == volume
                       and m["Destination"] == "/var/lib/backend_data" for m in inspect["Mounts"])
            assert network in inspect["NetworkSettings"]["Networks"]
            driver = json.loads(subprocess.check_output(["docker", "network", "inspect", network], text=True))[0]["Driver"]
            assert driver == "bridge"
            passed("named volume mount and custom bridge network")
            for text in ("before rebuild", "edited without rebuild"):
                marker.write_text(text, encoding="utf-8")
                assert request("GET", "/" + marker.name).decode() == text
            passed("frontend bind mount updates immediately without image rebuild")
            image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
            photo = request("POST", "/api/uploads", image=image)["url"]
            member = request("POST", "/api/members", {
                "name": "Persistence Demo", "nim": str(uuid.uuid4().int)[:18],
                "role": "Test", "skills": ["Docker", "JSON"],
                "activities": [{"category": "project", "title": "Volume proof", "photo": photo}],
            })
            compose("rm", "-s", "-f", "backend")
            compose("up", "-d", "--no-deps", "--wait", "--wait-timeout", "120", "backend")
            new_id = compose("ps", "-q", "backend", capture=True)
            assert new_id != backend_id
            for attempt in range(20):
                try:
                    assert member in request("GET", "/api/members")
                    assert request("GET", photo) == image
                    break
                except (HTTPError, URLError, TimeoutError, AssertionError):
                    if attempt == 19:
                        raise
                    time.sleep(1)
            passed("profile and photo survive backend container deletion and recreation")
            if args.github_username:
                result = request("GET", "/api/github/repos?username=" + quote(args.github_username))
                assert isinstance(result["repositories"], list)
                passed("live GitHub API through backend")
            report["status"] = "passed"
        except Exception as error:
            report["status"] = "failed"
            report["error"] = str(error)
            if safe_to_cleanup:
                subprocess.run(command + ["logs", "--no-color", "--tail=80"], cwd=ROOT, env=env)
            raise
        finally:
            marker.unlink(missing_ok=True)
            if safe_to_cleanup and not args.config_only:
                # Only this randomized project's resources, including its test volume.
                cleanup = subprocess.run(command + ["down", "--volumes", "--remove-orphans"], cwd=ROOT, env=env)
                report["cleanup_exit_code"] = cleanup.returncode
            output = ROOT / "artifacts" / "docker-verification.json"
            output.parent.mkdir(exist_ok=True)
            output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Report: {output}", flush=True)
            if report.get("cleanup_exit_code", 0):
                raise RuntimeError("Test resource cleanup failed; see Docker output")


if __name__ == "__main__":
    main()
