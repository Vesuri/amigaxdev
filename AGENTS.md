# AmigaXDev

The shared environment for the Amiga game projects: `make setup` installs `~/.local` and
`~/.local/share/amiga`, and `docs/` holds what the projects share. The projects are separate
repos next to this one.

## Rules

The playbook's §0 rules apply here (`docs/playbooks/new-game-playbook.md`), in particular:

- **Never commit Kickstart, Workbench, WHDLoad or game bytes**, or anything made from them.
  The repo holds scripts, checksums and names. Downloads and builds go in the ignored `tmp/`.
- **No local paths in the repo**: no home directories, usernames or paths into other projects.
  Name a project by its name. `~/.local` and `~/.local/share/amiga` are the allowed convention.
  The Kickstart and Workbench sources are always supplied by the user (`TOSEC=`, `AMIGA_OS=`);
  never write a mirror address into a script or doc.
- **Pin every input** in `manifest/` by sha256 or commit. Check it before installing it.
- **Setup never deletes**: a file that differs is moved to `.replaced/`. Never overwrite a
  shared file that was edited in place; `make pull-shared` brings the edit back here.
  WHDLoad developer packages are the explicit exception: retain only the latest, discard
  older installations after verifying the replacement, and do not keep `.replaced/` backups.
- **Never `pkill fs-uae` or `pkill gdb`**: other projects run emulators at the same time.
- Commits: author and committer `Vesa Halttunen <vesuri@jormas.com>`, unsigned,
  `core.hooksPath=/dev/null`, no Co-Authored-By or other trailers, one commit per coherent change.
- When creating or cloning a personal repository, explicitly set repository-local
  `commit.gpgsign=false` and `tag.gpgsign=false`. They are independent settings;
  disabling commit signing does not disable inherited tag signing. Verify both effective
  values, and never change global settings for this purpose.
- **History belongs in git.** Docs describe the current state; update them in place.
- The scripts run under macOS's `/bin/bash` 3.2 (a fresh Mac has nothing newer).

## Changing the projects

Projects are other people's work in progress: other sessions may be editing them. Before
touching one, check `git status`; leave a repo with uncommitted changes alone and report it.
Change only how a project finds shared files (its `amiga/env.sh`, path defaults), keep its
build output byte-identical, and commit that in the project's own repo with its conventions.

## Agent instructions

`AGENTS.md` holds them (this file), for every agent; here `CLAUDE.md` only imports it. Edit
`AGENTS.md`, never `CLAUDE.md`. New projects get an `AGENTS.md` and no `CLAUDE.md`
([a project's agent instructions](docs/environment.md#a-projects-agent-instructions)).

## Find guidance for the task

Start with [docs/index.md](docs/index.md), then read only the relevant sections.
Do not preload all playbooks, references, project status or open work. For an existing
project, its own `AGENTS.md` and current task take precedence; a setup playbook is not
an instruction to restart setup. Shared implementation changes also need the relevant
source, manifest and tests.

Keep this file to rules and routing. Put reusable guidance in one canonical topic and
link it from the index; keep project-specific state in the project's own docs. Add a
new index entry only when it helps an agent choose where to look.
