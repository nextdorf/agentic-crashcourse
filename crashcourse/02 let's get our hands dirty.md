# Let's get our hands dirty
The purpose of this chapter is mainly to actually use the tools mentioned in the previous chapter and getting a first feel for how working with generative AI looks in praxis.

## Walks like magic, talks like magic, so it must be ...

We start with the fun version first: one large prompt, no careful step-by-step planning, and a complete generated app at the end.

The prompt is in [`prompts/zeroshot-tinybi.md`](../prompts/zeroshot-tinybi.md). It asks the agent to build **TinyBI**, a small local FastAPI dashboard for CSV files. The generated reference project lives in [`tinybi-reference/`](../tinybi-reference/).

The live demo is intentionally simple:

1. Show the prompt.
2. Point out that it asks for a complete project, not just a code snippet.
3. Run the generated app.
4. Upload or load sample CSV data.
5. Use the resulting UI as material for the next topics.

Run the reference app:

```bash
cd tinybi-reference
make serve
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

From the outside this looks like magic. One prompt produced a project with:

- a FastAPI backend
- a plain HTML/CSS/JavaScript frontend
- pandas CSV parsing
- Chart.js visualizations
- sample data support
- a README
- a Makefile
- a `.gitignore`
- an `AGENTS.md`
- basic verification before stopping

The important lesson is not that the generated app is perfect. The important lesson is that the prompt gives the model enough structure to make many small decisions without asking us every time.

The prompt works because it describes more than the desired output. It also describes the working conditions:

- goal: build a small polished CSV analytics dashboard
- stack: FastAPI, pandas, plain frontend code, Chart.js, `uv`
- project shape: expected files and directories
- user flow: open page, upload CSV, see dashboard
- data assumptions: date, numeric, categorical, missing values, encodings
- non-goals: no database, no authentication, no external backend services
- operations: include `make serve`, `uv sync`, and run basic checks
- finish line: create the files, verify the app, and summarize how to run it

This is a useful pattern for prototypes, internal tools, learning projects, and throwaway demos. If the task is bounded and the prompt is concrete, zero-shot generation can get you surprisingly far.

But this is also where the trap starts. After the magic moment, the generated code is now your code. If you do not understand the project structure, dependencies, endpoints, assumptions, and failure modes, you can end up with an app that works once but is hard to change or debug.

For the workshop, TinyBI becomes our reference object. We can use it to ask the questions that matter after the first impressive generation:

- What made the prompt work?
- What parts of the prompt were probably over-specified?
- What did the agent decide on its own?
- What would we need to inspect before trusting the result?
- How would we improve the UI from a screenshot?
- How would we add a feature without losing control of the codebase?
- How would we compare this output to another generated version?

That is the reason for starting with the magic trick. It creates motivation first, then gives us something concrete to analyze for the rest of the chapter.

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


## Multimodal Input - Discussing a screenshot

One very practical use of multimodal input is UI feedback. Instead of trying to describe a layout problem from memory, we can show the agent a screenshot and talk about the visible problem directly.

Here is the first TinyBI version after the zero-shot build:

![TinyBI before visual feedback](images/02%20tinybi%20a.png)

The right side of the hero section had a large empty card. I did not need a carefully polished design brief to point that out. The screenshot made the problem obvious.

```text
[Image 1] 

Check out that right blob. It looks stupid with that empty space. Fix it.

...

Can you maybe give the entire page a visual refactor and make it all look just better. For example, having to scroll so much between the interesting stuff (like the input and the plots) sucks. Increase the general information density per area
```

The result after the agent applied the request:

![TinyBI after visual feedback](images/02%20tinybi%20b.png)

This is not magic in the sense that the model suddenly became a designer. It is useful because the screenshot removes ambiguity. The model can see what we mean by:

- "that right blob"
- too much empty space
- too much scrolling before charts appear
- low information density
- the important parts being too far apart

This is often faster than writing a long verbal UI critique. It also lets us be casual. The prompt above is not especially professional, but it is grounded in a concrete image, so the agent has enough context to make a reasonable edit.

Good screenshot feedback usually combines three things:

- the image itself
- a direct observation about what looks wrong
- a concrete direction for the change

For example:

```text
[Screenshot]

The upload area and the charts are too far apart. Reduce vertical spacing, make the first dashboard results visible above the fold, and keep the page readable on a laptop screen.
```

Or:

```text
[Screenshot]

The top-right card looks decorative but does not communicate anything. Either remove it or turn it into a useful summary card with real dashboard information.
```

The main trap is that visual feedback can make the agent optimize for the screenshot instead of the product. Text is still where LLMs are strongest. Even powerful multimodal models are usually much further away from human-level understanding of images than they are from human-level understanding of text, so expectations should be adjusted accordingly.

There is also a tooling problem. While editing files, the model usually does not see the page changing live. It reads the code, changes the code, and has to "imagine" the visual result from those edits. A more advanced setup can close this loop with browser automation, MCPs, screenshots, or custom skills, but the default workflow is still much more limited than a human looking at the page while changing CSS.

The same is true for UX and visual taste. An LLM has no real sense of style, taste, or tastefully navigating a page like a human does. It has seen many examples of nice interfaces and can imitate patterns from them, but it does not feel whether a page is elegant, cramped, boring, confusing, cheap-looking, or pleasant to use. In my experience so far, asking for "good UI/UX" without clear direction often produces generic design slop: technically cleaner than before, but not necessarily actually good. Clear instructions about what matters on the page are still necessary.

After a visual refactor, still check the actual app:

- Does it work at different screen sizes?
- Did any interaction break?
- Are charts, forms, and error states still readable?
- Did the agent only improve the visible viewport while ignoring the rest of the page?
- Did it add unnecessary complexity just to make the screenshot prettier?

For frontend work, screenshots are best used as feedback loops: generate, inspect, screenshot, critique, edit, and verify again.


## Prompt engineering (More in the appendix)

This is not meant to be a full prompt engineering guide. For this workshop, prompt engineering mostly means: shape the task enough that the model can make useful decisions without constantly stopping, guessing wildly, or overengineering the result.

The TinyBI demo already used several practical prompting tricks.

### Prompt engineering can mean prompting for a prompt

The large zero-shot prompt in [`prompts/zeroshot-tinybi.md`](../prompts/zeroshot-tinybi.md) did not appear fully formed. It started from a much smaller meta-prompt:

```text
give me a prompt for my agent (opencode with gpt 5.5) which attempts to build it all with a single request from start to finish - no user questions
```

That is also prompt engineering. Instead of writing the final prompt completely by hand, you can ask a model to draft a prompt for another model or agent. The useful part is not blindly trusting that generated prompt. The useful part is using it as a scaffold and then editing it.

In this case, the final TinyBI prompt was tweaked to be more realistic. The original idea said "no user questions", but the final version allows exactly two setup questions: where to create the project and what to call the app. After that, the agent should make reasonable assumptions and continue.

That tradeoff is important. "Never ask questions" sounds efficient, but can force the agent to guess things that are cheap and useful to ask once. A better version is often:

```text
Ask only these setup questions. After that, make reasonable assumptions and finish the task.
```

### Tricks used in the TinyBI prompt

- Start with the deliverable:

  ```text
  Build a complete FastAPI project from scratch in a user-specified directory.
  ```

  This tells the agent that the task is not a discussion, not a plan, and not a code snippet. The expected output is a working project.

- Give the goal and scope:

  ```text
  Create a small but polished data analytics dashboard app that can be built and run locally within minutes.
  ```

  This sets the size of the solution. "Small", "polished", "locally", and "within minutes" all push against unnecessary complexity.

- Control questions and assumptions:

  ```text
  Limit follow-up questions strictly to these initial setup questions only.
  Make reasonable assumptions after the initial questions.
  ```

  This keeps the workflow moving while still collecting the few details that matter.

- Prefer working simplicity:

  ```text
  Prefer a simple, working, polished app over complexity.
  ```

  This is one of the highest-value instructions in the prompt. It gives the model a way to resolve tradeoffs.

- Specify the stack:

  ```text
  Use FastAPI for the backend.
  Use plain HTML/CSS/JavaScript for the frontend.
  Use Chart.js via CDN for charts.
  Use pandas for CSV parsing.
  Use uv for dependency management instead of pip.
  ```

  This prevents the agent from inventing a heavier or unfamiliar stack.

- Specify non-goals:

  ```text
  No database.
  No authentication.
  No external backend services.
  ```

  Non-goals are as important as goals. They cut off common overengineering paths.

- Give the file structure:

  ```text
  main.py
  pyproject.toml
  .gitignore
  Makefile
  README.md
  AGENTS.md
  templates/index.html
  static/styles.css
  static/app.js
  sample_data.csv
  ```

  This makes the result easier to inspect and keeps the generated project close to what we expect.

- Describe the user flow:

  ```text
  1. User opens the homepage.
  2. User sees a beautiful landing/dashboard page.
  3. User uploads a CSV file and it is automatically analyzed.
  ```

  User flow is often more useful than describing individual functions. It tells the model what behavior the files must create together.

- List visible outputs:

  ```text
  total rows
  total columns
  numeric columns detected
  categorical columns detected
  CSV preview table
  chart of values over time
  3 to 5 plain-English insight cards
  ```

  This gives the frontend and backend concrete targets.

- Name assumptions and edge cases:

  ```text
  Handle missing values gracefully.
  Return useful errors for invalid files or empty CSVs.
  Do not assume uploaded CSV files or the Kaggle sample CSV are UTF-8 encoded.
  ```

  This pushes the agent beyond the happy path, but only for cases that matter for the demo.

- Give fallback behavior:

  ```text
  If the download fails, create a small realistic fallback sample_data.csv and clearly mention the fallback in the final summary.
  ```

  This is better than letting an external download failure break the whole task.

- Ask for developer ergonomics:

  ```text
  Include a Makefile with common commands.
  make serve -> runs uv run uvicorn main:app --reload
  ```

  For a workshop, this matters. The app should not only exist; it should be easy to run.

- Ask for verification before stopping:

  ```text
  Run basic checks.
  Verify imports work.
  Make sure the app can run with uv run uvicorn main:app --reload or make serve.
  Fix any obvious bugs before finishing.
  ```

  This changes the request from "write files" to "deliver something plausibly working".

- End with a clear finish line:

  ```text
  A complete working local FastAPI app in the user-specified directory. Do not stop after planning. Create the files, implement the app, and provide a concise final summary with run instructions.
  ```

  This is an anti-stalling instruction. It tells the agent to execute, not just outline.

### Tricks used after generation

The screenshot feedback used a different kind of prompting. It was rough, but grounded:

```text
[Image 1]

Check out that right blob. It looks stupid with that empty space. Fix it.
```

Then it added direction:

```text
Increase the general information density per area
```

This worked because the screenshot carried context that the text did not need to explain. The prompt did not need to politely describe every pixel. It only needed to point at the visible problem and say what kind of improvement was wanted.

We also used another practical trick in this chapter work: point the agent at existing files instead of restating everything.

```text
check @local/ideas.md, and @prompts/zeroshot-tinybi.md
```

That keeps the prompt short while still grounding the response in real project context.

### The pattern

The pattern so far is simple:

- use a small prompt to draft a bigger prompt when useful
- edit the generated prompt instead of trusting it blindly
- state the deliverable clearly
- give constraints and non-goals
- describe the user flow and visible outputs
- include edge cases only when they matter
- ask the agent to verify before stopping
- use screenshots when visual context is easier than words
- point to existing files instead of pasting context again

More general prompt engineering belongs in the appendix. For the main workshop, these are the tricks we have actually used.

## How to Generate
### AI as a search engine
### YOLO-mode
### LLM as a judge
