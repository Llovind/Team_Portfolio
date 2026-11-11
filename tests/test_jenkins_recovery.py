from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from recover_jenkins import registered_users, recovery_script, discover_users


class JenkinsRecoveryTests(unittest.TestCase):
    def test_user_mapping_lists_ids_without_password_data(self):
        xml = '<hudson.model.UserIdMapper><idToDirectoryNameMap><entry><string>owner</string><string>owner_123</string></entry></idToDirectoryNameMap></hudson.model.UserIdMapper>'
        self.assertEqual(registered_users(xml), {"owner": "owner_123"})

    def test_user_directory_cannot_escape_users(self):
        xml = '<root><idToDirectoryNameMap><entry><string>owner</string><string>../config.xml</string></entry></idToDirectoryNameMap></root>'
        with self.assertRaises(ValueError):
            registered_users(xml)

    def test_password_is_encoded_as_data_and_security_is_not_disabled(self):
        password = "quote' dollar$ newline\n"
        script = recovery_script("owner'", password, "account-recovery-test")
        self.assertNotIn(password, script)
        self.assertIn("fromPlainPassword", script)
        self.assertIn("hook.delete()", script)
        self.assertNotIn("setSecurityRealm", script)
        self.assertNotIn("setAuthorizationStrategy", script)

    def test_missing_mapper_discovers_id_from_user_config(self):
        def execute(*command, **kwargs):
            if command == ("cat", "/var/jenkins_home/users/users.xml"):
                return SimpleNamespace(returncode=1, stdout="")
            if command[0] == "find":
                return SimpleNamespace(stdout="/var/jenkins_home/users/owner_123/config.xml\n")
            self.assertEqual(command, ("cat", "/var/jenkins_home/users/owner_123/config.xml"))
            return SimpleNamespace(stdout="<user><id>actual-owner</id><fullName>Owner Name</fullName></user>")
        self.assertEqual(discover_users(execute, "/var/jenkins_home"), {"actual-owner": "owner_123"})

    def test_legacy_config_without_id_uses_directory_name(self):
        def execute(*command, **kwargs):
            if command[0] == "find":
                return SimpleNamespace(stdout="/var/jenkins_home/users/admin/config.xml\n")
            if command[1].endswith("users.xml"):
                return SimpleNamespace(returncode=1, stdout="")
            return SimpleNamespace(stdout="<user><fullName>Administrator</fullName></user>")
        self.assertEqual(discover_users(execute, "/var/jenkins_home"), {"admin": "admin"})


if __name__ == "__main__":
    unittest.main()
