# Let's get our hands dirty
The purpose of this chapter is mainly to actually use the tools mentioned in the previous chapter and getting a first feel for how working with generative AI looks in praxis.

## Walks like magic, talks like magic, so it must be ...


## Prompt engineering (Maybe just in the appendix?)


## `AGENTS.md` and `opencode.json`

Before asking an agent to work inside a repo, it helps to separate two kinds of setup:

- `AGENTS.md` is instruction context for the model.
- `opencode.json` is configuration for OpenCode itself.

The short version:

- Put repo-specific guidance in `AGENTS.md`.
- Put tool behavior, permissions, MCPs, model choices, and extra instruction files in `opencode.json`.
- Keep one-off task details in the prompt.

### AGENTS.md
OpenCode can create or update `AGENTS.md` with:

```text
/init
```

According to the OpenCode docs, `/init` scans important files, asks targeted questions when the repo cannot answer something, and writes concise project-specific guidance. The actual prompt behind `/init` is stored in the OpenCode repo as [`initialize.txt`](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/command/template/initialize.txt).

The core idea from that template is: every line in `AGENTS.md` should answer the question "Would an agent likely miss this without help?" If not, leave it out.

When executing the `/init` command the following command is being executed:

```markdown
Create or update `AGENTS.md` for this repository.

The goal is a compact instruction file that helps future OpenCode sessions avoid mistakes and ramp up quickly. Every line should answer: "Would an agent likely miss this without help?" If not, leave it out.

User-provided focus or constraints (honor these):


## How to investigate

Read the highest-value sources first:
- `README*`, root manifests, workspace config, lockfiles
- build, test, lint, formatter, typecheck, and codegen config
- CI workflows and pre-commit / task runner config
- existing instruction files (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/`, `.cursorrules`, `.github/copilot-instructions.md`)
- repo-local OpenCode config such as `opencode.json`

If architecture is still unclear after reading config and docs, inspect a small number of representative code files to find the real entrypoints, package boundaries, and execution flow. Prefer reading the files that explain how the system is wired together over random leaf files.

Prefer executable sources of truth over prose. If docs conflict with config or scripts, trust the executable source and only keep what you can verify.

## What to extract

Look for the highest-signal facts for an agent working in this repo:
- exact developer commands, especially non-obvious ones
- how to run a single test, a single package, or a focused verification step
- required command order when it matters, such as `lint -> typecheck -> test`
- monorepo or multi-package boundaries, ownership of major directories, and the real app/library entrypoints
- framework or toolchain quirks: generated code, migrations, codegen, build artifacts, special env loading, dev servers, infra deploy flow
- repo-specific style or workflow conventions that differ from defaults
- testing quirks: fixtures, integration test prerequisites, snapshot workflows, required services, flaky or expensive suites
- important constraints from existing instruction files worth preserving

Good `AGENTS.md` content is usually hard-earned context that took reading multiple files to infer.

## Questions

Only ask the user questions if the repo cannot answer something important. Use the `question` tool for one short batch at most.

Good questions:
- undocumented team conventions
- branch / PR / release expectations
- missing setup or test prerequisites that are known but not written down

Do not ask about anything the repo already makes clear.

## Writing rules

Include only high-signal, repo-specific guidance such as:
- exact commands and shortcuts the agent would otherwise guess wrong
- architecture notes that are not obvious from filenames
- conventions that differ from language or framework defaults
- setup requirements, environment quirks, and operational gotchas
- references to existing instruction sources that matter

Exclude:
- generic software advice
- long tutorials or exhaustive file trees
- obvious language conventions
- speculative claims or anything you could not verify
- content better stored in another file referenced via `opencode.json` `instructions`

When in doubt, omit.

Prefer short sections and bullets. If the repo is simple, keep the file simple. If the repo is large, summarize the few structural facts that actually change how an agent should work.

If `AGENTS.md` already exists at `/path/to/agentic-crashcourse`, improve it in place rather than rewriting blindly. Preserve verified useful guidance, delete fluff or stale claims, and reconcile it with the current codebase.
```

Noticed the "User-provided focus or constraints (honor these):"-line? When adding additional instructions to the `/init` command then they will be added to the `AGENTS.md` creation request. 

A good `AGENTS.md` should mostly contain hard-earned context an agent would otherwise miss. A bad `AGENTS.md` becomes a generic style guide that burns context without changing behavior.

OpenCode reads `AGENTS.md` from a few places:

- project rules: `AGENTS.md` in the project
- global personal rules: `~/.config/opencode/AGENTS.md`
- Claude Code fallback: `CLAUDE.md` or `~/.claude/CLAUDE.md` if no OpenCode file exists

One detail that is easy to guess wrong: local rule files are not automatically merged through every parent directory. OpenCode looks upward and the first matching local file wins. Additional instruction files can be combined explicitly through `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": ["CONTRIBUTING.md", "docs/guidelines.md", ".cursor/rules/*.md"]
}
```

### opencode.json
`opencode.json` is the other half of the setup. Current OpenCode docs place project config at the repo root as `opencode.json` or `opencode.jsonc`. This is where I would configure things like:

- `mcp` servers such as Context7
- `permission` rules for read, edit, bash, task, webfetch, and websearch
- `model` and `small_model`
- `agent` definitions
- `instructions` files that should be combined with `AGENTS.md`

For example, Context7 can be added as a remote MCP server:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true
    }
  }
}
```

And permissions can make common operations low-friction while still guarding risky ones:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "read": "allow",
    "edit": "ask",
    "task": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "bash": {
      "*": "ask",
      "git status*": "allow",
      "git diff*": "allow",
      "git log*": "allow",
      "git push*": "deny",
      "rm*": "deny"
    }
  }
}
```

The practical split is:

- `AGENTS.md`: what the agent should know about this repo
- `opencode.json`: what OpenCode is allowed and configured to do
- `.opencode/agents/`: reusable specialized agents, if the workflow needs them

Source docs: [OpenCode rules docs](https://opencode.ai/docs/rules/), [rules docs source](https://github.com/anomalyco/opencode/blob/dev/packages/web/src/content/docs/rules.mdx), and [`/init` prompt source](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/command/template/initialize.txt).


## Mutimodal Input - Discussing a screenshot


## How to Generate
### AI as a search engine
### YOLO-mode
### LLM as a judge
