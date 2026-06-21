import re
import subprocess
import sys
from pathlib import Path


API_TOKEN_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
COOKIE_PATH_RE = re.compile(r"^\s*cookies_path\s*:\s*([^#\r\n]+)", re.MULTILINE)
LOCAL_SECRET_RE = re.compile(
    r"^\s*VIDEOLINGO_[A-Z0-9_]+\s*=\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".toml", ".env"}


def scan_text(path, text):
    path = Path(path)
    findings = []
    if API_TOKEN_RE.search(text):
        findings.append("probable API token")
    if path.suffix.lower() in CONFIG_SUFFIXES or path.name.startswith(".env"):
        cookie_match = COOKIE_PATH_RE.search(text)
        if cookie_match:
            value = cookie_match.group(1).strip().strip("'\"")
            if value and value not in {"YOUR_COOKIE_PATH", "your-cookie-path"}:
                findings.append("non-placeholder cookie path")
    if path.suffix.lower() == ".toml" or path.name.startswith(".env"):
        if LOCAL_SECRET_RE.search(text):
            findings.append("local secret assignment")
    return findings


def tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def main():
    findings = []
    for path in tracked_files():
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for reason in scan_text(path, text):
            findings.append((str(path), reason))
    for path, reason in findings:
        print(f"{path}: {reason}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
