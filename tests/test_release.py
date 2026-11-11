from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_release import prepare_release


class ReleaseTests(unittest.TestCase):
    def test_checkout_changes_do_not_change_release_and_existing_release_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("frontend", "backend", "nginx"):
                (root / name).mkdir()
                (root / name / "source.txt").write_text("tested", encoding="utf-8")
            (root / "docker-compose.yml").write_text("name: test", encoding="utf-8")
            release = prepare_release(root, "42")
            (root / "frontend/source.txt").write_text("untested checkout", encoding="utf-8")
            self.assertEqual((release / "frontend/source.txt").read_text(), "tested")
            with self.assertRaises(FileExistsError):
                prepare_release(root, "42")
            self.assertEqual((release / "frontend/source.txt").read_text(), "tested")

    def test_invalid_build_number_cannot_escape_release_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for number in ("../outside", "", "１２"):
                with self.assertRaises(ValueError):
                    prepare_release(Path(directory), number)


if __name__ == "__main__":
    unittest.main()
