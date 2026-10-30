---
name: update
description: Update the coach's code to the latest version from GitHub without touching memory. Use when the SETUP or UPDATE line says an update is available, or when the user asks to update the coach.
---

# Update

The coach's code (`CLAUDE.md`, skills, subagents, scripts, hooks) comes from GitHub. Memory lives in `memory/`, which git ignores, so updating never touches it.

1. Run `git fetch origin` and `git log --oneline HEAD..@{upstream}`. Tell the user in plain words what's new, based on the commit messages. If there's nothing new, say so and stop.
2. Ask before updating.
3. Run `git pull --ff-only`.
   - If it fails because files were changed locally, run `git status --short` and show the user which files. Don't discard their changes without asking.
4. If `templates/memory/` gained files that `memory/` doesn't have, they're created automatically the next time a script runs. Existing memory files are never replaced.
5. Tell the user: changes to skills apply right away; changes to `CLAUDE.md` and hooks apply the next time this session starts or resumes.
