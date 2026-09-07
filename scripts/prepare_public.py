#!/usr/bin/env python3
"""Prepare a clean public candidate from a private Git repository."""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "credentials.json",
    "credentials.*",
    "*.p12",
    "*.pfx",
)
SENSITIVE_DIRECTORIES = ("secrets", "secret")


class PreparationError(RuntimeError):
    """Raised when a candidate cannot be prepared safely."""


@dataclass(frozen=True)
class CandidateReport:
    source_root: Path
    source_head: str
    output: Path
    files: tuple[str, ...]
    excluded: tuple[str, ...]
    publicignore: Path | None


def _run_git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=repo, shell=False, check=False,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
    except OSError as exc:
        raise PreparationError(f"cannot run Git: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or "unknown Git error"
        raise PreparationError(detail)
    return result.stdout


def find_repo_root(start: Path) -> Path:
    start = start.expanduser().resolve()
    if not start.exists():
        raise PreparationError(f"repository path does not exist: {start}")
    try:
        return Path(_run_git(start, "rev-parse", "--show-toplevel").strip()).resolve()
    except PreparationError as exc:
        raise PreparationError(f"not a Git repository: {start}") from exc


def require_clean_worktree(repo: Path) -> None:
    if _run_git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise PreparationError(
            "working tree is not clean; commit, stash, or discard changes before preparing a public candidate"
        )


def source_head(repo: Path) -> str:
    return _run_git(repo, "rev-parse", "HEAD").strip()


def tracked_files(repo: Path) -> tuple[str, ...]:
    records = _run_git(repo, "ls-files", "-s", "-z").split("\0")
    paths: list[str] = []
    for record in records:
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode = metadata.split(" ", 1)[0]
        if mode not in {"100644", "100755"}:
            raise PreparationError(f"tracked file is not a regular file: {path}")
        if path == ".git" or path.startswith(".git/"):
            continue
        paths.append(path)
    return tuple(sorted(paths))


def load_publicignore(path: Path) -> tuple[str, ...]:
    if not path.exists():
        return ()
    if not path.is_file() or path.is_symlink():
        raise PreparationError(f".publicignore is not a regular file: {path}")
    rules: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        rule = raw.strip()
        if rule and not rule.startswith("#"):
            rules.append(rule)
    return tuple(rules)


def publicignore_matches(path: str, rules: tuple[str, ...]) -> bool:
    for rule in rules:
        if rule.endswith("/"):
            directory = rule.rstrip("/")
            if path == directory or path.startswith(directory + "/"):
                return True
        elif fnmatch.fnmatchcase(path, rule):
            return True
    return False


def _sensitive(path: str) -> bool:
    name = Path(path).name
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in SENSITIVE_PATTERNS):
        return True
    parts = Path(path).parts
    return any(part in SENSITIVE_DIRECTORIES for part in parts)


def _check_output(output: Path, repo: Path) -> None:
    if output.exists() or output.is_symlink():
        raise PreparationError(f"candidate destination already exists: {output}")
    if repo == output or repo in output.parents:
        raise PreparationError("candidate destination must be outside the source repository")
    parent = output.parent
    while parent != parent.parent:
        if parent.exists():
            if parent.is_symlink():
                raise PreparationError("candidate destination has a symlinked parent")
            return
        parent = parent.parent


def prepare_candidate(repo_path: Path, output: Path, publicignore: Path | None = None) -> CandidateReport:
    repo = find_repo_root(repo_path)
    require_clean_worktree(repo)
    head = source_head(repo)
    files = tracked_files(repo)
    ignore_path = (publicignore or (repo / ".publicignore")).expanduser()
    if not ignore_path.is_absolute():
        ignore_path = (repo / ignore_path).resolve()
    rules = load_publicignore(ignore_path)
    selected = tuple(path for path in files if path != ".publicignore" and not publicignore_matches(path, rules))
    sensitive = tuple(path for path in selected if _sensitive(path))
    if sensitive:
        raise PreparationError("sensitive-looking tracked files must be excluded before publication: " + ", ".join(sensitive))
    destination = output.expanduser().resolve(strict=False)
    _check_output(destination, repo)
    destination.mkdir(parents=True)
    try:
        for relative in selected:
            source = repo / relative
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink() or not source.is_file():
                raise PreparationError(f"tracked source is not a regular file: {relative}")
            shutil.copyfile(source, target)
            shutil.copymode(source, target)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return CandidateReport(repo, head, destination, selected, tuple(path for path in files if path not in selected), ignore_path if ignore_path.exists() else None)


def print_report(report: CandidateReport) -> None:
    print(f"SOURCE_ROOT = {report.source_root}")
    print(f"SOURCE_HEAD = {report.source_head}")
    print(f"CANDIDATE = {report.output}")
    print(f"PUBLICIGNORE = {report.publicignore or 'not present'}")
    print(f"FILES = {len(report.files)}")
    print("CANDIDATE_FILES:")
    for path in report.files:
        print(f"- {path}")
    if report.excluded:
        print("EXCLUDED_FILES:")
        for path in report.excluded:
            print(f"- {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="private Git repository (default: current directory)")
    parser.add_argument("--output", type=Path, required=True, help="new candidate directory; it must not already exist")
    parser.add_argument("--publicignore", type=Path, help="optional .publicignore path; default: REPO/.publicignore")
    args = parser.parse_args(argv)
    try:
        print_report(prepare_candidate(args.repo, args.output, args.publicignore))
    except PreparationError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
