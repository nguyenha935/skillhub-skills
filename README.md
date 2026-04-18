# skillhub-skills

Public catalog of built-in skills for SkillHub.

This repository is the source of truth for skills that SkillHub can discover,
index, package, and distribute to GoClaw or other compatible Claw runtimes in
the future.

## Repository layout

```text
skillhub-skills/
  index.json
  skills/
    <slug>/
      skillhub.manifest.json
      SKILL.md
      assets/
      scripts/
      references/
      video-summarize.zip
```

## Catalog contract

- `index.json` lists every published skill and the relative path to its machine
  readable manifest.
- `skillhub.manifest.json` is the canonical metadata file that SkillHub should
  read.
- `SKILL.md` remains the human-facing skill documentation.
- `*.zip` package files are the installable artifacts that operators can upload
  into GoClaw.

## Current skills

### video-summarize

- Slug: `video-summarize`
- Inputs: `youtube_url`, `url`, `upload`, `file_path`
- Default provider: Gemini native video
- Package: `skills/video-summarize/video-summarize.zip`

## Install into GoClaw

Unzip `video-summarize.zip` and copy its contents into:

```text
/app/data/skills-store/video-summarize/1/
```

Or from a local checkout:

```bash
docker cp ./skills/video-summarize/. goclaw-goclaw-1:/app/data/skills-store/video-summarize/1/
```
