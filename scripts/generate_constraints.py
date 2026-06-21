import argparse
import importlib.metadata
import re
from pathlib import Path


def normalize_name(name):
    return re.sub(r"[-_.]+", "-", str(name).strip()).lower()


def requirement_names(lines):
    names = []
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        value = value.split(";", 1)[0].strip()
        name = re.split(r"[<>=!~@\[]", value, maxsplit=1)[0].strip()
        if name:
            names.append(normalize_name(name))
    return names


def installed_versions():
    versions = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            versions[normalize_name(name)] = distribution.version
    return versions


def build_constraints(requirement_lines, versions):
    normalized_versions = {
        normalize_name(name): version for name, version in versions.items()
    }
    constraints = []
    missing = []
    for name in requirement_names(requirement_lines):
        version = normalized_versions.get(name)
        if version:
            constraints.append(f"{name}=={version}")
        else:
            missing.append(name)
    return sorted(set(constraints)), sorted(set(missing))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--output", default="constraints-py312.txt")
    args = parser.parse_args()
    lines = Path(args.requirements).read_text(encoding="utf-8").splitlines()
    constraints, missing = build_constraints(lines, installed_versions())
    output = [
        "# Generated from the active Python 3.12 environment.",
        "# Regenerate with: python scripts/generate_constraints.py",
        *constraints,
    ]
    if missing:
        output.extend(
            ["", "# Not installed in the snapshot environment:"]
            + [f"# {name}" for name in missing]
        )
    Path(args.output).write_text("\n".join(output) + "\n", encoding="utf-8")
    print(f"Pinned {len(constraints)} installed top-level dependencies; {len(missing)} missing.")


if __name__ == "__main__":
    main()
