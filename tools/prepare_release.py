"""Create an immutable application snapshot after CI tests/build have passed."""
import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def prepare_release(root, build_number):
    if not build_number.isascii() or not build_number.isdigit():
        raise ValueError("Build number must contain ASCII digits")
    destination = root / ".deployments" / ("build-" + build_number)
    destination.mkdir(parents=True, exist_ok=False)
    for directory in ("frontend", "backend", "nginx"):
        shutil.copytree(root / directory, destination / directory,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".bind-mount-*"))
    shutil.copy2(root / "docker-compose.yml", destination / "docker-compose.yml")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-number", required=True)
    args = parser.parse_args()
    print(prepare_release(ROOT, args.build_number), flush=True)
