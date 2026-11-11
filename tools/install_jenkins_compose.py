"""Install Compose in the existing Jenkins container from the official Docker CLI image."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="jenkins-server")
    args = parser.parse_args()

    def run(*command, capture=False):
        return subprocess.run(["docker", *command], check=True, text=True,
                              stdout=subprocess.PIPE if capture else None)

    existing = subprocess.run(["docker", "exec", args.container, "docker", "compose", "version"])
    if existing.returncode == 0:
        print("Compose already works; no changes needed.")
        return
    # Copy a Linux plugin from an official image; do not depend on the custom image's apt repositories.
    image = "docker:28.3.2-cli"
    run("pull", image)
    plugin = run("run", "--rm", "--entrypoint", "sh", image, "-c",
                 "find /usr/local/libexec/docker /usr/local/lib/docker /usr/libexec/docker /usr/lib/docker -type f -name docker-compose 2>/dev/null || true",
                 capture=True).stdout.strip().splitlines()
    if len(plugin) != 1 or not plugin[0].startswith("/usr/"):
        raise RuntimeError("Cannot identify a unique Compose plugin in the official image")
    donor = "jenkins-compose-install-" + uuid.uuid4().hex[:10]
    run("create", "--name", donor, image)
    try:
        with tempfile.TemporaryDirectory(prefix="jenkins-compose-") as directory:
            local = Path(directory) / "docker-compose"
            run("cp", donor + ":" + plugin[0], str(local))
            destination = "/usr/local/lib/docker/cli-plugins"
            run("exec", "--user", "0", args.container, "mkdir", "-p", destination)
            run("cp", str(local), args.container + ":" + destination + "/docker-compose")
            run("exec", "--user", "0", args.container, "chmod", "755", destination + "/docker-compose")
            run("exec", args.container, "docker", "compose", "version")
            run("exec", args.container, "docker", "compose", "up", "--help")
            print("Compose installed and verified inside Jenkins. Run Build Now again; no Jenkins restart required.")
    finally:
        run("rm", donor)


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError) as error:
        raise SystemExit("Compose installation failed: " + str(error))
