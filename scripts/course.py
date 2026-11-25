#!/usr/bin/env python3
"""Portable commands used by students and by the course documentation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CAR_SERVICE = ROOT / "apps" / "car-rental-service"
PRICING_SERVICE = ROOT / "apps" / "pricing-service"
WORKFLOWS = ROOT / ".github" / "workflows"

# Directories that never hold project-owned workflows or Dockerfiles.
IGNORED_DIRECTORIES = {
    ".git",
    ".gradle",
    ".venv",
    "venv",
    "build",
    "node_modules",
    "__pycache__",
    "_site",
}

# `uses: owner/repo[/path]@ref`, optionally quoted, optionally in a list item.
USES_PATTERN = re.compile(r"""^\s*(?:-\s+)?uses:\s*['"]?([^\s'"#]+)""")
# `FROM [--platform=...] image[:tag][@digest] [AS stage]`.
FROM_PATTERN = re.compile(r"^\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)
FULL_COMMIT_SHA = re.compile(r"@[0-9a-f]{40}$")
IMAGE_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print(f"+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def gradle_command() -> list[str]:
    if os.name == "nt":
        return ["cmd", "/c", "gradlew.bat"]
    return ["./gradlew"]


def test_java() -> None:
    run([*gradle_command(), "clean", "test"], cwd=CAR_SERVICE)


def test_python() -> None:
    run([sys.executable, "-m", "pytest"], cwd=PRICING_SERVICE)


def test() -> None:
    test_java()
    test_python()


def lint_java() -> None:
    run([*gradle_command(), "checkstyleMain", "checkstyleTest"], cwd=CAR_SERVICE)


def lint_python() -> None:
    run([sys.executable, "-m", "ruff", "check", "app", "tests"], cwd=PRICING_SERVICE)
    run(
        [sys.executable, "-m", "ruff", "format", "--check", "app", "tests"],
        cwd=PRICING_SERVICE,
    )


def lint() -> None:
    lint_java()
    lint_python()


def action_violations(path: Path) -> list[str]:
    """Return every remote action in a workflow that is not pinned to a commit."""
    violations = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        match = USES_PATTERN.match(line)
        if match is None:
            continue
        reference = match.group(1)
        if reference.startswith("./"):
            continue  # local action or reusable workflow: versioned with this repository
        pattern = IMAGE_DIGEST if reference.startswith("docker://") else FULL_COMMIT_SHA
        if pattern.search(reference) is None:
            violations.append(
                f"{path.relative_to(ROOT)}:{number}: "
                f"action is not pinned to an immutable reference: {reference}"
            )
    return violations


def dockerfile_violations(path: Path) -> list[str]:
    """Return every FROM instruction that does not carry a SHA-256 digest."""
    violations = []
    stages: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = FROM_PATTERN.match(line)
        if match is None:
            continue
        image, alias = match.groups()
        location = f"{path.relative_to(ROOT)}:{number}"
        if image.lower() == "scratch" or image.lower() in stages:
            pass  # not a registry image: empty base or an earlier build stage
        elif "$" in image:
            violations.append(f"{location}: FROM uses a variable and cannot be verified: {image}")
        elif IMAGE_DIGEST.search(image) is None:
            violations.append(f"{location}: FROM has no sha256 digest: {image}")
        if alias:
            stages.add(alias.lower())
    return violations


def find_dockerfiles() -> list[Path]:
    found = []
    for directory, subdirectories, files in os.walk(ROOT):
        subdirectories[:] = [name for name in subdirectories if name not in IGNORED_DIRECTORIES]
        for name in files:
            if name == "Dockerfile" or name.startswith("Dockerfile.") or name.endswith(".Dockerfile"):
                found.append(Path(directory) / name)
    return sorted(found)


def supply_chain_policy() -> None:
    workflows = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    dockerfiles = find_dockerfiles()
    if not workflows or not dockerfiles:
        # A policy that scans nothing would always pass: treat it as a failure.
        raise RuntimeError("No workflow or Dockerfile found: the policy cannot be checked")

    violations = []
    for workflow in workflows:
        violations.extend(action_violations(workflow))
    for dockerfile in dockerfiles:
        violations.extend(dockerfile_violations(dockerfile))

    if violations:
        for violation in violations:
            print(f"VIOLATION {violation}", file=sys.stderr)
        raise RuntimeError(f"Supply chain policy failed: {len(violations)} violation(s)")
    print(
        f"OK supply chain policy: {len(workflows)} workflow(s) and "
        f"{len(dockerfiles)} Dockerfile(s) use immutable references"
    )


def verify() -> None:
    test()
    lint()
    supply_chain_policy()


def compose_up() -> None:
    require_command("docker")
    run(["docker", "compose", "up", "--build", "--detach"])


def compose_down() -> None:
    require_command("docker")
    run(["docker", "compose", "down"])


def wait_for(url: str, *, timeout_seconds: int = 45) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    print(f"OK {url}")
                    return
        except (URLError, TimeoutError) as error:
            last_error = error
        time.sleep(1)

    raise RuntimeError(f"Service unavailable at {url}: {last_error}")


def smoke() -> None:
    wait_for("http://localhost:8080/health")
    wait_for("http://localhost:8080/cars")
    wait_for("http://localhost:8000/health")
    request = Request(
        "http://localhost:8000/quotes",
        data=json.dumps({"category": "standard", "days": 2}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=3) as response:
        quote = json.load(response)
    if quote.get("total") != 120.0 or quote.get("currency") != "EUR":
        raise RuntimeError(f"Unexpected pricing response: {quote}")
    print("OK pricing quote")


def require_command(command: str) -> None:
    if shutil.which(command) is None:
        raise RuntimeError(f"Required command not found: {command}")


def prerequisites() -> None:
    checks = {
        "Python": sys.executable,
        "Java": shutil.which("java"),
        "Docker": shutil.which("docker"),
    }
    missing = False

    for name, location in checks.items():
        if location:
            print(f"OK {name}: {location}")
        else:
            print(f"MISSING {name}")
            missing = True

    if missing:
        raise RuntimeError("One or more prerequisites are missing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "prerequisites",
            "test",
            "test-java",
            "test-python",
            "lint",
            "lint-java",
            "lint-python",
            "supply-chain-policy",
            "verify",
            "compose-up",
            "compose-down",
            "smoke",
        ],
    )
    args = parser.parse_args()

    commands = {
        "prerequisites": prerequisites,
        "test": test,
        "test-java": test_java,
        "test-python": test_python,
        "lint": lint,
        "lint-java": lint_java,
        "lint-python": lint_python,
        "supply-chain-policy": supply_chain_policy,
        "verify": verify,
        "compose-up": compose_up,
        "compose-down": compose_down,
        "smoke": smoke,
    }

    try:
        commands[args.command]()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
