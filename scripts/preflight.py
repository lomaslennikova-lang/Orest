#!/usr/bin/env python3
"""Run the repository checks required before a commit or deployment."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
CRITICAL_FILES = (
    ".secrets.baseline",
    ".env.example",
    ".gitignore",
    "requirements.txt",
    "Dockerfile.render",
    "docker-compose.yml",
    "frontend/package.json",
)
TELEGRAM_TOKEN_PATTERN = re.compile(r"\b\d{8,10}:[0-9A-Za-z_-]{35}\b")


class PreflightError(RuntimeError):
    """A required preflight stage failed."""


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def resolve_command(name: str) -> str | None:
    candidates = (f"{name}.cmd", name) if name == "npm" and sys.platform == "win32" else (name,)
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate

    if name == "git" and sys.platform == "win32":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        git_executable = program_files / "Git" / "cmd" / "git.exe"
        if git_executable.is_file():
            return str(git_executable)
    return None


def run_command(
    command: Sequence[str], *, cwd: Path, check: bool = True
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=check,
        )
    except FileNotFoundError as error:
        raise PreflightError(f"Required command is not available: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        details = "\n".join(part for part in (error.stdout, error.stderr) if part).strip()
        raise PreflightError(details or f"Command failed: {' '.join(command)}") from error


def git_files(repo_root: Path, runner: CommandRunner = run_command) -> list[Path]:
    git_command = resolve_command("git")
    if git_command is None:
        raise PreflightError("Required command is not available: git")
    result = runner(
        [git_command, "ls-files", "--cached", "--others", "--exclude-standard"], cwd=repo_root
    )
    excluded_files = {".env.example", ".secrets.baseline"}
    return [Path(line) for line in result.stdout.splitlines() if line and line not in excluded_files]


def acknowledged_false_positives(repo_root: Path) -> set[tuple[str, str]]:
    baseline_path = repo_root / ".secrets.baseline"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise PreflightError("Could not read .secrets.baseline") from error

    acknowledged: set[tuple[str, str]] = set()
    for findings in baseline.get("results", {}).values():
        for finding in findings:
            if finding.get("is_secret") is False:
                acknowledged.add((finding["filename"], finding["hashed_secret"]))
    return acknowledged


def check_python_compile(repo_root: Path) -> None:
    run_command(
        [sys.executable, "-m", "compileall", "-q", "app", "alembic", "scripts", "tests"],
        cwd=repo_root,
    )


def check_frontend_build(repo_root: Path) -> None:
    npm_command = resolve_command("npm")
    if npm_command is None:
        raise PreflightError("Required command is not available: npm")
    run_command([npm_command, "run", "build"], cwd=repo_root / "frontend")


def check_docker_build(repo_root: Path) -> None:
    run_command(
        ["docker", "build", "--file", "Dockerfile.render", "--tag", "orest-render-check", "."],
        cwd=repo_root,
    )


def check_secret_scan(repo_root: Path) -> None:
    files = git_files(repo_root)
    if not files:
        return

    result = run_command(
        [sys.executable, "-m", "detect_secrets", "scan", *map(str, files)], cwd=repo_root
    )
    try:
        findings = json.loads(result.stdout).get("results", {})
    except json.JSONDecodeError as error:
        raise PreflightError("detect-secrets returned invalid JSON") from error

    acknowledged = acknowledged_false_positives(repo_root)
    unacknowledged = {
        filename: [
            finding
            for finding in file_findings
            if (finding["filename"], finding["hashed_secret"]) not in acknowledged
        ]
        for filename, file_findings in findings.items()
    }

    token_findings: list[str] = []
    for relative_path in files:
        path = repo_root / relative_path
        if not path.is_file():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if TELEGRAM_TOKEN_PATTERN.search(line):
                token_findings.append(f"{relative_path}:{line_number} - Telegram Bot Token")

    if any(unacknowledged.values()) or token_findings:
        details = [
            f"detect-secrets: {filename}:{finding['line_number']} - {finding['type']}"
            for filename, file_findings in sorted(unacknowledged.items())
            for finding in file_findings
        ]
        details.extend(token_findings)
        raise PreflightError("\n".join(details))


def check_critical_files(repo_root: Path, runner: CommandRunner = run_command) -> None:
    missing = [path for path in CRITICAL_FILES if not (repo_root / path).is_file()]
    if missing:
        raise PreflightError("Missing critical files: " + ", ".join(missing))

    git_command = resolve_command("git")
    if git_command is None:
        raise PreflightError("Required command is not available: git")
    tracked_env = runner(
        [git_command, "ls-files", "--error-unmatch", ".env"],
        cwd=repo_root,
        check=False,
    )
    if tracked_env.returncode == 0:
        raise PreflightError(".env is tracked by Git; remove it from version control before continuing")


def run_stage(name: str, check: Callable[[], None]) -> bool:
    try:
        check()
    except PreflightError as error:
        print(f"{name}: FAILED", file=sys.stderr)
        if str(error):
            print(str(error), file=sys.stderr)
        print("Preflight: FAILED", file=sys.stderr)
        return False

    print(f"{name}: OK")
    return True


def main() -> int:
    stages = (
        ("Python compile", lambda: check_python_compile(REPOSITORY_ROOT)),
        ("Frontend build", lambda: check_frontend_build(REPOSITORY_ROOT)),
        ("Docker build", lambda: check_docker_build(REPOSITORY_ROOT)),
        ("Secret scan", lambda: check_secret_scan(REPOSITORY_ROOT)),
        ("Critical files", lambda: check_critical_files(REPOSITORY_ROOT)),
    )
    for name, check in stages:
        if not run_stage(name, check):
            return 1

    print("Preflight: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
