"""Recover an existing local Jenkins account through its Docker container."""
import argparse
import base64
import getpass
from pathlib import PurePosixPath
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET


def registered_users(xml):
    result = {}
    for entry in ET.fromstring(xml).findall(".//idToDirectoryNameMap/entry"):
        values = entry.findall("string")
        if len(values) == 2 and values[0].text and values[1].text:
            directory = values[1].text
            if "/" in directory or "\\" in directory or directory in (".", ".."):
                raise ValueError("Invalid Jenkins user directory")
            result[values[0].text] = directory
    return result


def discover_users(execute, home):
    mapper = execute("cat", home + "/users/users.xml", check=False)
    if mapper.returncode == 0:
        return registered_users(mapper.stdout)
    # Older/migrated homes may have user config files without a mapper file.
    result = execute("find", home + "/users", "-mindepth", "2", "-maxdepth", "2",
                     "-name", "config.xml", "-type", "f")
    users = {}
    root = PurePosixPath(home) / "users"
    for filename in result.stdout.splitlines():
        path = PurePosixPath(filename)
        if path.parent.parent != root or path.name != "config.xml":
            raise ValueError("User config path is outside the Jenkins users directory")
        config = ET.fromstring(execute("cat", str(path)).stdout)
        if config.tag != "user":
            continue
        username = config.findtext("id") or path.parent.name
        if username in users:
            raise ValueError("Multiple configurations found for the same username")
        users[username] = path.parent.name
    return users


def recovery_script(username, password, filename):
    encode = lambda value: base64.b64encode(value.encode("utf-8")).decode("ascii")
    # Base64 makes arbitrary user input safe as a Groovy literal; it is not encryption.
    # This short-lived file is mode 600 in the container and removed after execution.
    return f"""import jenkins.model.Jenkins
import hudson.model.User
import hudson.security.HudsonPrivateSecurityRealm

def instance = Jenkins.get()
def hook = new File(instance.rootDir, 'init.groovy.d/{filename}.groovy')
def result = new File(instance.rootDir, 'init.groovy.d/{filename}.result')
try {{
    if (!(instance.securityRealm instanceof HudsonPrivateSecurityRealm)) {{
        throw new IllegalStateException('Recovery requires the Jenkins local user database')
    }}
    def user = User.getById(new String('{encode(username)}'.decodeBase64(), 'UTF-8'), false)
    if (user == null || user.getProperty(HudsonPrivateSecurityRealm.Details.class) == null) {{
        throw new IllegalStateException('Existing local account not found')
    }}
    user.addProperty(HudsonPrivateSecurityRealm.Details.fromPlainPassword(
        new String('{encode(password)}'.decodeBase64(), 'UTF-8')))
    user.save()
    result.setText('success', 'UTF-8')
}} catch (Exception error) {{
    result.setText('failed', 'UTF-8')
    throw error
}} finally {{
    hook.delete()
}}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="jenkins-server")
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--diagnose", action="store_true", help="Read-only container and Jenkins home diagnostics")
    args = parser.parse_args()

    def execute(*command, data=None, check=True):
        result = subprocess.run(["docker", "exec", "-i", args.container, *command],
                                input=data, text=True, encoding="utf-8", capture_output=True)
        if check and result.returncode:
            # Password material is sent through stdin, never through command arguments.
            detail = result.stderr.strip()[:800] or f"exit code {result.returncode}"
            raise RuntimeError(f"Docker exec failed during {command[0]}: {detail}")
        return result

    if args.diagnose:
        for command in [("id",), ("printenv", "JENKINS_HOME"),
                        ("ls", "-ld", "/var/jenkins_home", "/var/jenkins_home/users"),
                        ("ls", "-l", "/var/jenkins_home/users/users.xml")]:
            result = execute(*command, check=False)
            print("$ " + " ".join(command))
            print((result.stdout + result.stderr).strip() or f"exit code {result.returncode}")
        return

    home = execute("printenv", "JENKINS_HOME").stdout.strip().rstrip("/")
    if not home.startswith("/") or home in ("", "/"):
        raise RuntimeError("JENKINS_HOME is missing or invalid")
    users = discover_users(execute, home)
    if not users:
        raise RuntimeError("No registered accounts found; check whether initial Jenkins setup is complete")
    print("Username Jenkins yang terdaftar:")
    for username in users:
        print("  " + username)
    if args.list_only:
        return
    username = input("Username yang akan direset: ").strip()
    if username not in users:
        raise ValueError("Pilih username yang ada pada daftar")
    config = home + "/users/" + users[username] + "/config.xml"
    user_config = ET.fromstring(execute("cat", config).stdout)
    if user_config.find("./properties/hudson.security.HudsonPrivateSecurityRealm_-Details") is None:
        raise RuntimeError("Selected account does not use a local Jenkins password")
    print("Container Jenkins akan direstart. Job, credential, dan pengaturan otorisasi tetap dipertahankan.")
    password = getpass.getpass("Password baru (tidak ditampilkan): ")
    if not password:
        raise ValueError("Password tidak boleh kosong")
    if getpass.getpass("Ulangi password baru: ") != password:
        raise ValueError("Password tidak sama")

    identifier = "account-recovery-" + uuid.uuid4().hex
    hook = home + "/init.groovy.d/" + identifier + ".groovy"
    marker = home + "/init.groovy.d/" + identifier + ".result"
    backup = home + "/recovery-backups/" + identifier
    execute("mkdir", "-p", backup)
    execute("cp", config, backup + "/config.xml")
    try:
        execute("sh", "-c", 'umask 077; mkdir -p "$1" && test ! -e "$2" && cat > "$2"',
                "sh", home + "/init.groovy.d", hook,
                data=recovery_script(username, password, identifier))
        password = None
        subprocess.run(["docker", "restart", args.container], check=True)
        print("Menunggu Jenkins menyelesaikan pemulihan...", flush=True)
        for _ in range(90):
            result = execute("cat", marker, check=False)
            if result.returncode == 0:
                if result.stdout.strip() != "success":
                    raise RuntimeError("Jenkins could not reset the account. Inspect startup logs; backup is retained.")
                print(f"Password berhasil direset. Login ke http://localhost:8081 dengan username: {username}")
                print("Backup konfigurasi akun di container: " + backup)
                return
            time.sleep(2)
        raise RuntimeError("Timed out waiting for Jenkins. Check container logs before retrying.")
    finally:
        # Remove only the two files generated for this recovery attempt.
        cleanup = execute("rm", "-f", hook, marker, check=False)
        if cleanup.returncode:
            print("Cleanup failed. Remove these temporary files inside the container:")
            print(hook)
            print(marker)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
