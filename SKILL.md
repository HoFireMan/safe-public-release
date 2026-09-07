---
name: safe-public-release
description: Prepare a clean public candidate from a private Git repository for an individual developer.
---

# Safe Public Release V2

Use this Skill for a simple private-to-public workflow:

1. inspect the private Git repository;
2. require a clean working tree;
3. use Git tracked files as the source set;
4. apply the project's optional `.publicignore`;
5. prepare a new temporary candidate;
6. show its source HEAD and complete file inventory;
7. run the project's tests when practical;
8. warn or stop on obvious sensitive filenames;
9. ask the user for explicit approval before any public mutation;
10. create a fresh public Git history rather than changing the private repository's remote or visibility.

Prepare a candidate with:

```sh
python scripts/prepare_public.py --output /tmp/project-public
```

`.gitignore` controls what enters the private repository. `.publicignore` excludes tracked files from the public candidate. V2 supports blank lines, `#` comments, exact relative paths, directory rules ending in `/`, and simple Python `fnmatch`-style globs. It is not a full Git-ignore implementation. The private `.publicignore` file itself is not copied.

Before creating, pushing, or exposing a public repository, show the candidate inventory, test result, and `SOURCE_HEAD`, then obtain explicit user approval for that publication action. A candidate and passing tests do not authorize publication.

If the requested public target already exists, stop and ask the user. Never overwrite it, adopt unknown history, delete it, or force-push it automatically. Never force-push by default.

V2 is a preparation tool, not a provider API, secret-management system, release state machine, or automatic publisher. Its public distribution is MIT-licensed, Copyright (c) 2026 HoFireMan.
