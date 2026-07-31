# Skills and agents (Incomplete)

In the previous chapter, we extended a coding agent's capabilities with MCP servers. We discussed what they are, how to connect one to OpenCode, and how to write a small one ourselves. We went into quite some depth because MCP servers, unlike the topics in this chapter, can be useful for almost any kind of AI-driven application or workflow.

No matter whether you use a coding agent, an AI chat application, or a custom application that calls an LLM's API directly, you can theoretically expose an MCP server's tools to the AI. The application must support MCP or adapt the tools to the model's tool-calling API, and the model itself must support tool calling. You can use [OpenRouter's model search](https://openrouter.ai/models?supported_parameters=tools) to filter for models that do.

Skills and agents, however, are much more client-dependent. Many coding agents support them in one form or another, and `SKILL.md` plus a few common directories are becoming shared conventions. Invocation, permissions, and lifecycle still differ between clients, though, and best practices vary between models and change over time. Take this chapter with a grain of salt.

## Skills

At their core, skills are Markdown files with YAML metadata and instructions that an agent can load into its context. You can think of them as on-demand counterparts to `AGENTS.md`. While `AGENTS.md` provides general project instructions, OpenCode shows the agent each available skill's name and description. The agent can then load the complete skill when it is relevant. This is useful for tools or workflows the agent would not otherwise know.

### Installing skills

The Internet is full of skills. There are entire marketplaces, and many developers share their skills on GitHub. One popular site is [skills.sh](https://www.skills.sh). It also provides a CLI for finding and installing skills. You can run the CLI directly with `npx skills`; no separate installation is required. Run `npx skills --help` for an overview.

Running the CLI alone does not add a skill to your coding agent. To install `find-skills`, run `npx skills add https://github.com/vercel-labs/skills --skill find-skills`. A dropdown menu asks where the skill should be installed. Select the shared `.agents/skills` location, which OpenCode supports by default. This selection is especially relevant if you also use another coding CLI and want it to find the same skill. The following tools should support this location:

* Amp
* Antigravity
* Antigravity CLI
* Cline
* Codex
* Cursor
* Deep Agents
* Gemini CLI
* GitHub Copilot
* Kimi Code CLI
* OpenCode
* Warp
* Zed

After selecting the location, press Enter, choose a local or global installation, and confirm. Restart OpenCode so it discovers the new skill. You can then ask it to find a skill in plain language. OpenCode sees the skill's metadata and loads its complete instructions on demand. The advantage over using the CLI directly is that you can describe what you need and let the agent search the catalog, compare options, and install one if requested.

### Using skills

If you execute `/find-skills [some query]`, OpenCode loads the `find-skills` skill's `SKILL.md` into the context and appends the following:

> Base directory for this skill: /path/to/.agents/skills/find-skills
> Relative paths in this skill (e.g., scripts/, references/) are relative to this base directory.
>
> [your query]

The skill contains the following instructions:

> ```md
> ---
> name: find-skills
> description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill.
> ---
> ```
> 
> # Find Skills
> 
> This skill helps you discover and install skills from the open agent skills ecosystem.
> 
> ## When to Use This Skill
> 
> Use this skill when the user:
> 
> - Asks "how do I do X" where X might be a common task with an existing skill
> - Says "find a skill for X" or "is there a skill for X"
> - Asks "can you do X" where X is a specialized capability
> - Expresses interest in extending agent capabilities
> - Wants to search for tools, templates, or workflows
> - Mentions they wish they had help with a specific domain (design, testing, deployment, etc.)
> 
> ## What is the Skills CLI?
> 
> The Skills CLI (`npx skills`) is the package manager for the open agent skills ecosystem. Skills are modular packages that extend agent capabilities with specialized knowledge, workflows, and tools.
> 
> **Key commands:**
> 
> - `npx skills find [query] [--owner <owner>]` - Search for skills interactively or by keyword, optionally scoped to a GitHub owner
> - `npx skills add <package>` - Install a skill from GitHub or other sources
> - `npx skills update` - Update all installed skills
> 
> **Browse skills at:** https://skills.sh/
> 
> ## How to Help Users Find Skills
> 
> ### Step 1: Understand What They Need
> 
> When a user asks for help with something, identify:
> 
> 1. The domain (e.g., React, testing, design, deployment)
> 2. The specific task (e.g., writing tests, creating animations, reviewing PRs)
> 3. Whether this is a common enough task that a skill likely exists
> 
> ### Step 2: Check the Leaderboard First
> 
> Before running a CLI search, check the [skills.sh leaderboard](https://skills.sh/) to see if a well-known skill already exists for the domain. The leaderboard ranks skills by total installs, surfacing the most popular and battle-tested options.
> 
> For example, top skills for web development include:
> - `vercel-labs/agent-skills` — React, Next.js, web design (100K+ installs each)
> - `anthropics/skills` — Frontend design, document processing (100K+ installs)
> 
> ### Step 3: Search for Skills
> 
> If the leaderboard doesn't cover the user's need, run the find command:
> 
> ```bash
> npx skills find [query] [--owner <owner>]
> ```
> 
> For example:
> 
> - User asks "how do I make my React app faster?" → `npx skills find react performance`
> - User asks "can you help me with PR reviews?" → `npx skills find pr review`
> - User asks "I need to create a changelog" → `npx skills find changelog`
> 
> ### Step 4: Verify Quality Before Recommending
> 
> **Do not recommend a skill based solely on search results.** Always verify:
> 
> 1. **Install count** — Prefer skills with 1K+ installs. Be cautious with anything under 100.
> 2. **Source reputation** — Official sources (`vercel-labs`, `anthropics`, `microsoft`) are more trustworthy than unknown authors.
> 3. **GitHub stars** — Check the source repository. A skill from a repo with <100 stars should be treated with skepticism.
> 
> ### Step 5: Present Options to the User
> 
> When you find relevant skills, present them to the user with:
> 
> 1. The skill name and what it does
> 2. The install count and source
> 3. The install command they can run
> 4. A link to learn more at skills.sh
> 
> Example response:
> 
> ```
> I found a skill that might help! The "react-best-practices" skill provides
> React and Next.js performance optimization guidelines from Vercel Engineering.
> (185K installs)
> 
> To install it:
> npx skills add vercel-labs/agent-skills@react-best-practices
> 
> Learn more: https://skills.sh/vercel-labs/agent-skills/react-best-practices
> ```
> 
> ### Step 6: Offer to Install
> 
> If the user wants to proceed, you can install the skill for them:
> 
> ```bash
> npx skills add <owner/repo@skill> -g -y
> ```
> 
> The `-g` flag installs globally (user-level) and `-y` skips confirmation prompts.
> 
> ## Common Skill Categories
> 
> When searching, consider these common categories:
> 
> | Category        | Example Queries                          |
> | --------------- | ---------------------------------------- |
> | Web Development | react, nextjs, typescript, css, tailwind |
> | Testing         | testing, jest, playwright, e2e           |
> | DevOps          | deploy, docker, kubernetes, ci-cd        |
> | Documentation   | docs, readme, changelog, api-docs        |
> | Code Quality    | review, lint, refactor, best-practices   |
> | Design          | ui, ux, design-system, accessibility     |
> | Productivity    | workflow, automation, git                |
> 
> ## Tips for Effective Searches
> 
> 1. **Use specific keywords**: "react testing" is better than just "testing"
> 2. **Try alternative terms**: If "deploy" doesn't work, try "deployment" or "ci-cd"
> 3. **Check popular sources**: Many skills come from `vercel-labs/agent-skills` or `ComposioHQ/awesome-claude-skills`
> 
> ## When No Skills Are Found
> 
> If no relevant skills exist:
> 
> 1. Acknowledge that no existing skill was found
> 2. Offer to help with the task directly using your general capabilities
> 3. Suggest the user could create their own skill with `npx skills init`
> 
> Example:
> 
> ```
> I searched for skills related to "xyz" but didn't find any matches.
> I can still help you with this task directly! Would you like me to proceed?
> 
> If this is something you do often, you could create your own skill:
> npx skills init my-xyz-skill
> ```

The important part at the top is the YAML front matter:

```md
---
name: find-skills
description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill.
---
```

OpenCode includes this name and description in the list of available skills. The agent uses them to decide whether to load the complete skill. Think of this metadata as the counterpart to the tool catalog exposed by an MCP server.

Feel free to discover some interesting skills.

### Writing skills

When you type `/skills`, you will see the built-in `customize-opencode` skill. You can use it, for example, to create a custom skill:

```text
> /customize-opencode create a skill for interacting with tinybi2's mcp
```

After some exploration:

```text
Plan

Create one project-local skill at:
.opencode/skills/tinybi2/SKILL.md

The skill will:
 1. Trigger for TinyBI2, CSV dashboard analysis, and my_mcp chart-management requests.
 2. Translate the user’s input into the appropriate my_mcp workflow.
 3. Always call inspect_dataset or list_charts before mutations to obtain the current incarnation and revision.
 4. Distinguish disposable automatic analysis from persistent managed charts.
 5. Avoid passing an explicit dataset unless the user intends to replace the active dataset and clear managed charts.
 6. Support sample, project-local path, inline CSV, and active-dataset workflows.
 7. Select valid bar, line, scatter, or heatmap definitions from inspected column roles.
 8. Use exact, case-sensitive column names and valid pandas query filters.
 9. Refresh workspace state and retry safely after version conflicts.
10. Treat chart deletion and ambiguous dataset replacement as destructive operations requiring clear user intent.
11. Summarize completed analysis, filters, chart IDs, and relevant workspace changes.

No opencode.json edit is required because .opencode/skills/**/SKILL.md is automatically discovered. The existing my_mcp connection is already configured and working.

After implementation, restart OpenCode because skills are loaded only at startup.
```

You can treat that plan as a first draft and tweak it further. For now, tell it to install the skill at `.agents/skills/tinybi2/SKILL.md`, alongside `find-skills`, instead of under `.opencode/skills`:
```text
Execute but install in .agents 
```

Within 42 seconds, it produced the following:

> ```md
> ---
> name: tinybi2
> description: Use when the user asks to analyze CSV data, build a TinyBI2 dashboard, or create, update, delete, list, or reorder charts through the my_mcp TinyBI2 server.
> ---
> ```
> 
> # TinyBI2 MCP
> 
> Use the `my_mcp` tools to turn the user's request into a CSV analysis or a set of managed charts. Work from the user's stated goal rather than exposing the MCP mechanics unless they are relevant.
> 
> ## Core Rules
> 
> - Inspect before mutating. Obtain the current `workspace.incarnation`, `workspace.revision`, detected column roles, and valid options with `inspect_dataset`.
> - Pass the latest `expected_incarnation` and `expected_revision` to every mutation.
> - Treat the workspace as shared with the browser and other agents. Do not reuse a version from before another successful mutation.
> - If a mutation reports a stale version, inspect or list again, reconsider the request against the new state, and retry only if it remains safe.
> - Omit `dataset` to work with the active shared dataset. Supplying an explicit dataset to `analyze_dataset` or `create_charts` replaces the active dataset and clears all managed charts.
> - `inspect_dataset` never activates or replaces a dataset, even when given an explicit input.
> - Do not replace a dataset, clear charts, or delete charts unless the user's request clearly authorizes that effect. Ask one concise question when intent is ambiguous.
> - Use exact, case-sensitive column names returned by inspection.
> - Keep results bounded and useful. Prefer a small set of charts that directly answer the request.
> 
> ## Choose A Workflow
> 
> Use `analyze_dataset` for a broad, disposable dashboard with metrics, automatic charts, insights, or a preview.
> 
> Use managed chart tools when the user asks for specific visualizations, persistent charts, chart edits, deletion, or ordering:
> 
> - `list_charts` reads IDs, definitions, and order. Use `include_data: true` only when rendered values are needed.
> - `create_charts` atomically adds one to ten charts.
> - `update_charts` replaces complete definitions while preserving IDs and order.
> - `delete_charts` atomically removes selected IDs. Deleted IDs are not reused.
> - `reorder_charts` requires every current managed chart ID exactly once.
> 
> ## Dataset Inputs
> 
> Translate an explicitly requested source into one of these forms:
> 
> ```json
> {"source":"sample"}
> ```
> 
> ```json
> {"source":"path","path":"data/orders.csv"}
> ```
> 
> ```json
> {"source":"inline","inline_csv":"Region,Revenue\nWest,100\nEast,80\n"}
> ```
> 
> Path inputs must be CSV files inside the TinyBI2 project directory. For data outside it, use complete inline CSV content when practical. Omit the dataset argument when the user means the currently active dataset.
> 
> When replacing the active dataset:
> 
> 1. Call `inspect_dataset` with the explicit dataset.
> 2. Validate that its detected roles support the requested analysis or charts.
> 3. Use the same explicit dataset in the intended `analyze_dataset` or `create_charts` mutation.
> 
> ## Analysis Workflow
> 
> 1. Inspect the intended dataset.
> 2. Derive a valid filter and requested sections from the user's goal.
> 3. Call `analyze_dataset` with the current workspace version.
> 4. Request only needed sections when the request is narrow; otherwise return the broad dashboard.
> 5. Summarize the important metrics, trends, filters, and row counts rather than dumping the full payload.
> 
> Filters are case-sensitive pandas `DataFrame.query` expressions. Wrap columns containing spaces in backticks:
> 
> ```text
> Sales > 100 and Region == 'West'
> `Order Date` >= '2016-01-01'
> `Sub-Category` == 'Chairs'
> ```
> 
> An empty filter string clears the current filter.
> 
> ## Chart Selection
> 
> Choose chart definitions only from roles returned by `inspect_dataset`:
> 
> - Bar: compare aggregated measures across categories.
> - Line: show ordered or date-based trends.
> - Scatter: examine relationships between two detected numeric measures.
> - Heatmap: compare one measure across two grouping dimensions.
> 
> Grouped bar or line chart:
> 
> ```json
> {
>   "type": "bar",
>   "x_column": "Region",
>   "y_column": "Sales",
>   "aggregation": "sum",
>   "sort_by": "value_desc",
>   "limit": 20
> }
> ```
> 
> Scatter chart:
> 
> ```json
> {
>   "type": "scatter",
>   "x_column": "Discount",
>   "y_column": "Profit",
>   "limit": 50
> }
> ```
> 
> Heatmap:
> 
> ```json
> {
>   "type": "heatmap",
>   "x_column": "Region",
>   "y_column": "Category",
>   "value_column": "Sales",
>   "aggregation": "sum",
>   "x_limit": 10,
>   "y_limit": 10
> }
> ```
> 
> Supported aggregations are `sum`, `mean`, `median`, `min`, `max`, and `count`. Supported sort modes are `label_asc`, `label_desc`, `value_asc`, and `value_desc`. Use inspection output for current limits and valid columns instead of assuming them.
> 
> ## Chart Mutation Workflow
> 
> 1. Inspect the dataset and call `list_charts` when existing chart IDs or order matter.
> 2. Build complete, valid definitions from detected roles.
> 3. Submit related changes as one atomic batch where possible.
> 4. Use the workspace version from the most recent successful call.
> 5. After each mutation, use the returned workspace version for the next mutation.
> 6. Report affected chart IDs, titles, ordering, and any dataset replacement.
> 
> For updates, provide each chart's complete replacement definition, not a partial patch. For reorder operations, include every current ID exactly once. Never invent IDs.
> 
> ## Response Style
> 
> - State what was analyzed or changed.
> - Mention active filters and dataset replacement when applicable.
> - For managed charts, report chart IDs and concise titles.
> - Highlight useful findings from returned data, but do not claim conclusions unsupported by the tool output.
> - Surface validation failures plainly and suggest the nearest valid alternative.

## Agents

Agents are another way of extending OpenCode's capabilities. I have not explicitly mentioned this yet, but you have probably already noticed that you can cycle through different modes in the OpenCode interface. On a fresh installation, you should see `Plan` and `Build`. These are the primary agents. If you have already experimented with OpenCode, you might have seen it occasionally spawn sub-sessions or sub-agents. You can view them by pressing `Ctrl+X` and then `Down`. There, you might have seen a third mode: `Explore`, a read-only sub-agent for searching a codebase.

Each agent can add its own system prompt and permissions. This is similar to project instructions in `AGENTS.md`, but the two are not the same: `AGENTS.md` supplies repository context, while an agent definition controls that agent's role and behavior. Because OpenCode is open source, you can inspect how its built-in agents are prompted in the source code at https://github.com/anomalyco/opencode/tree/dev/packages/opencode/src/agent.

Alternatively, you can ask OpenCode to show you an agent's prompt. At the time of writing, the Explore agent's system prompt is:

```text
You are a file search specialist. You excel at thoroughly navigating and exploring codebases.

Your strengths:
- Rapidly finding files using glob patterns
- Searching code and text with powerful regex patterns
- Reading and analyzing file contents

Guidelines:
- Use Glob for broad file pattern matching
- Use Grep for searching file contents with regex
- Use Read when you know the specific file path you need to read
- Use Bash for file operations like copying, moving, or listing directory contents
- Adapt your search approach based on the thoroughness level specified by the caller
- Return file paths as absolute paths in your final response
- For clear communication, avoid using emojis
- Do not create any files, or run bash commands that modify the user's system state in any way

Complete the user's search request efficiently and report your findings clearly.
```

You can open the user-facing agent picker with `Ctrl+X` and then `A`. To list agents from the command line, run:

```bash
opencode agent list | awk '/^[^[:space:]].* \((primary|subagent)\)$/'
```

To create an agent interactively, run:

```bash
opencode agent create
```

OpenCode asks whether the agent should be global or project-specific, what it should do, and which permissions it needs. It then creates the corresponding Markdown agent definition.
