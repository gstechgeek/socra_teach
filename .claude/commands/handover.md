---
description: Update docs/HANDOVER.md with a session handover summary
---

Update `docs/HANDOVER.md` with a session handover summary.

## Instructions

1. Review the current git status, staged/unstaged changes, and recent commits to understand what was done this session.
2. Read the existing `docs/HANDOVER.md` to understand current state.
3. Update the file with the following structure:

```
# Handover — socra_teach (YYYY-MM-DD)

## What's Done
### Phases Complete
(Update the phase status table)

### Recent Changes (this session)
(Numbered list of what was accomplished — be specific, reference files)

### Test & Build Status
(Backend test count, frontend build status, lint status)

### Committed Work
(List recent commits on the current branch)

## Known Issues
### Must Fix
### Should Fix
(Update or add issues discovered this session)

## What's Left
(Update remaining work by phase)

## Key Architecture Decisions to Remember
(Add any new decisions made this session)

## Files Changed (uncommitted)
(List uncommitted files with one-line descriptions)
```

4. Keep previous session entries as a log — add a `---` separator and an "## Previous Session" heading before the old content when the date changes.
5. Be concise. Each bullet should be one sentence.
6. Only include sections that have meaningful updates — don't repeat unchanged content verbatim.
