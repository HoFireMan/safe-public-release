# safe-public-release-skill

Safe Public Release is a lightweight Pi Skill for preparing clean public releases from private Git repositories. It targets personal projects, not enterprise release governance. It keeps private Git history out of the public repository and uses `.publicignore` for tracked-but-private files; publication still requires explicit user approval.

## Workflow

```text
private Git repository
    -> clean working tree
    -> tracked files minus .publicignore
    -> temporary candidate
    -> inspect the candidate inventory
    -> run project tests when practical
    -> ask for explicit publication approval
    -> create fresh public Git history
```

The candidate never includes private Git history. An authorized publication initializes a new repository in the candidate directory rather than changing the private repository's remote or visibility.

## Pi Skill

`SKILL.md` is the Pi agent instruction entry point. The Global Skill name is `safe-public-release`, installed at:

```text
~/.pi/agent/skills/safe-public-release
```

The GitHub project is named `safe-public-release-skill` so visitors can identify it as a Skill. The internal Pi Skill name and installation path intentionally remain `safe-public-release` for compatibility.

## `.gitignore` and `.publicignore`

`.gitignore` controls what enters the private repository. Because V2 starts with `git ls-files`, ignored untracked files are naturally excluded.

`.publicignore` controls files that are tracked privately but should stay out of the public candidate. It supports blank lines and `#` comments, exact relative paths, directory rules ending in `/`, and simple Python-style filename/path globs. It is not full Git-ignore syntax. The private `.publicignore` file itself is not copied.

Start with the example:

```sh
cp .publicignore.example .publicignore
```

## Prepare a candidate

```sh
python scripts/prepare_public.py --output /tmp/my-project-public
```

The command requires a clean working tree, records and prints `SOURCE_HEAD`, rejects an existing destination, copies selected tracked regular files, prints the final inventory, and blocks obvious sensitive filenames such as `.env`, `*.pem`, `*.key`, credentials files, and secret directories.

Run the project's tests from the candidate when practical. Before any later public repository is created, pushed, or exposed, show the candidate inventory, test result, and source HEAD, then obtain explicit user approval for that publication action. A prepared candidate and passing tests are not approval.

If the requested public target already exists, stop and ask the user. Never overwrite, adopt unknown history, delete, or force-push it automatically.

## License

MIT License. Copyright (c) 2026 HoFireMan.

## Limitations

V2 does not automatically create repositories, push, change visibility, publish releases, or install itself globally. It does not implement a provider API, a publication state machine, a secret-management framework, or a full Git-ignore parser.
