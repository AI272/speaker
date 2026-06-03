# speaker Project Instructions

This repository contains the `speaker` project and its shared skill implementation.

Claude Code users can invoke the project skill as:

```text
/ppt-speech-writer
```

The Claude Code project-skill entry is available at:

```text
.claude/skills/ppt-speech-writer
```

The canonical skill source is:

```text
ppt-speech-writer/
```

When editing the skill, update the canonical source first, then rebuild the packaged `.skill` file for Codex and refresh any local installations.

Key behavior requirements:

- Confirm output language before drafting notes.
- Keep the entire deliverable monolingual, except canonical technical terms.
- Do not start slide notes with template phrases such as "This slide shows..." or "这一页展示了..."。
- Keep intermediate run outputs under `*-speaker-output/work/`.
- Do not commit `*-speaker-output/` generated folders.
