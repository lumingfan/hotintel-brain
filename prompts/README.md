# Prompts

Prompt templates for HotIntel Brain. Versioning rules:

- Each prompt has its own file: `<task>_v<major>.<minor>.md`
- Bumping any non-trivial change requires a new version file (don't overwrite)
- Runtime source order is:
  1. Langfuse prompt management (when `LANGFUSE_*` keys are configured and fetch succeeds)
  2. Local markdown prompt file fallback

Each prompt file should contain:

1. A YAML front-matter block with `version`, `task`, `created`, `notes`
2. A "System" section
3. A "User template" section with `{{var}}` placeholders matching the
   Pydantic input model
4. An "Examples" section (optional but recommended)
5. A "Changelog" section listing what changed vs the prior version

V1 prompts (skeletons live alongside this README):

- `judge_v1.md` — single-shot relevance / isReal / importance / summary
- `summarize_v1.md` — event detail / report / digest summarisation

V2 prompts (added later, listed for reference):

- `expand_v1.md`
- `aggregate_hint_v1.md`
- `triage_hint_v1.md`

Do NOT inline prompt strings in chain code. Always load from file (or, batch
2 onward, via Langfuse `langfuse.get_prompt(name, version)`).
