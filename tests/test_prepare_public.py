from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from prepare_public import (  # noqa: E402
    PreparationError,
    find_repo_root,
    prepare_candidate,
    publicignore_matches,
)


class PreparePublicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifetime = tempfile.TemporaryDirectory()
        self.base = Path(self.lifetime.name)
        self.repo = self.base / "private"
        self.repo.mkdir()
        self._write("README.md", "readme\n")
        self._write("public.txt", "public\n")
        self._write("private/notes.md", "private\n")
        self._write("docs/example.private.md", "private doc\n")
        self._write(".gitignore", ".env\nscratch.txt\n")
        self._write(".publicignore", "private/\n*.private.md\n")
        self._git("init", "-q")
        self._git("config", "user.email", "v2@example.invalid")
        self._git("config", "user.name", "V2 Test")
        self._git("add", ".")
        self._git("commit", "-qm", "initial")
        self._write(".env", "not tracked\n")
        self._write("scratch.txt", "not tracked\n")

    def tearDown(self) -> None:
        self.lifetime.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _git(self, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=self.repo, check=True, shell=False,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout

    def test_git_repository_detection(self):
        self.assertEqual(find_repo_root(self.repo / "private"), self.repo)
        self.assertEqual(find_repo_root(self.repo), self.repo)

    def test_clean_repository_is_accepted(self):
        report = prepare_candidate(self.repo, self.base / "candidate")
        self.assertEqual(report.source_root, self.repo)
        self.assertTrue(report.source_head)

    def test_dirty_repository_is_blocked(self):
        self._write("README.md", "changed\n")
        with self.assertRaisesRegex(PreparationError, "working tree is not clean"):
            prepare_candidate(self.repo, self.base / "candidate")

    def test_tracked_files_are_copied_but_untracked_files_are_not(self):
        report = prepare_candidate(self.repo, self.base / "candidate")
        candidate = report.output
        self.assertTrue((candidate / "README.md").exists())
        self.assertFalse((candidate / ".env").exists())
        self.assertFalse((candidate / "scratch.txt").exists())
        self.assertFalse((candidate / ".publicignore").exists())

    def test_private_git_directory_is_never_copied(self):
        candidate = prepare_candidate(self.repo, self.base / "candidate").output
        self.assertFalse((candidate / ".git").exists())
        self.assertFalse(any(path.name == ".git" for path in candidate.rglob("*")))

    def test_publicignore_exact_directory_and_glob_semantics(self):
        rules = ("private.txt", "private/", "*.private.md")
        self.assertTrue(publicignore_matches("private.txt", rules))
        self.assertTrue(publicignore_matches("private/notes.md", rules))
        self.assertTrue(publicignore_matches("docs/example.private.md", rules))
        self.assertFalse(publicignore_matches("public.txt", rules))

    def test_source_head_is_recorded(self):
        report = prepare_candidate(self.repo, self.base / "candidate")
        expected = self._git("rev-parse", "HEAD").strip()
        self.assertEqual(report.source_head, expected)

    def test_candidate_inventory_is_sorted_and_exact(self):
        report = prepare_candidate(self.repo, self.base / "candidate")
        self.assertEqual(report.files, tuple(sorted(report.files)))
        self.assertEqual(set(report.files), {".gitignore", "README.md", "public.txt"})
        self.assertEqual(set(report.excluded), {".publicignore", "docs/example.private.md", "private/notes.md"})

    def test_sensitive_tracked_filename_blocks_preparation(self):
        self._write("id_ed25519", "placeholder\n")
        self._git("add", "id_ed25519")
        self._git("commit", "-qm", "tracked sensitive key filename")
        with self.assertRaisesRegex(PreparationError, "sensitive-looking tracked files"):
            prepare_candidate(self.repo, self.base / "candidate")

    def test_credentials_sensitive_tracked_filename_blocks_preparation(self):
        self._write("credentials.json", "placeholder\n")
        self._git("add", "credentials.json")
        self._git("commit", "-qm", "tracked sensitive filename")
        with self.assertRaisesRegex(PreparationError, "sensitive-looking tracked files"):
            prepare_candidate(self.repo, self.base / "candidate")

    def test_executable_mode_is_preserved(self):
        self._write("scripts/run.sh", "#!/bin/sh\necho ok\n")
        (self.repo / "scripts/run.sh").chmod(0o755)
        self._git("add", "scripts/run.sh")
        self._git("commit", "-qm", "tracked executable")
        candidate = prepare_candidate(self.repo, self.base / "candidate").output
        self.assertTrue(os.stat(candidate / "scripts/run.sh").st_mode & stat.S_IXUSR)

    def test_tracked_symlink_is_rejected(self):
        (self.repo / "linked").symlink_to("README.md")
        self._git("add", "linked")
        self._git("commit", "-qm", "tracked symlink")
        with self.assertRaisesRegex(PreparationError, "not a regular file"):
            prepare_candidate(self.repo, self.base / "candidate")

    def test_existing_candidate_destination_is_rejected(self):
        destination = self.base / "candidate"
        destination.mkdir()
        with self.assertRaisesRegex(PreparationError, "already exists"):
            prepare_candidate(self.repo, destination)

    def test_missing_publicignore_is_allowed(self):
        self._git("rm", "-q", ".publicignore")
        self._git("commit", "-qm", "remove optional publicignore")
        report = prepare_candidate(self.repo, self.base / "candidate")
        self.assertIsNone(report.publicignore)
        self.assertIn("private/notes.md", report.files)

    def test_candidate_must_be_outside_source_repository(self):
        with self.assertRaisesRegex(PreparationError, "outside the source repository"):
            prepare_candidate(self.repo, self.repo / "candidate")


if __name__ == "__main__":
    unittest.main()
