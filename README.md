# Agentic Crash Course

A small introductory workshop on generative AI for Data Engineers, presented as part of a course.

## AI involvement in writing the workshop

This workshop itself has largely been written with the help of AI, using OpenCode, Codex, and VS Code. In [Chapter 2's car-seat metaphor](crashcourse/02%20let%27s%20get%20our%20hands%20dirty.md#who-is-driving), I describe three levels of a developer's involvement: the driver's seat, the passenger's seat, and the spectator seat. I developed this workshop by switching between the driver's seat and the passenger's seat. I believe this is the most appropriate way to produce high-quality work quickly while still taking full ownership of the code and tutorial text.

## Table Of Contents

- [0) Setup](crashcourse/00%20setup.md)
- [1) Opencode](crashcourse/01%20opencode.md)
- [2) Let's get our hands dirty](crashcourse/02%20let%27s%20get%20our%20hands%20dirty.md)
- [3) MCP Servers](crashcourse/03%20MCP%20servers.md)
- [4) Skills and agents](crashcourse/04%20skills%20and%20agents.md)

## What this workshop covers

We start by setting up a coding agent and connecting it to a model. This also means discussing providers, subscriptions, API keys, local models, privacy, and where your code is actually sent. You do not need a paid AI subscription to follow the workshop.

After that, we generate a complete CSV dashboard from one large prompt. The result looks impressive, but instead of stopping there we inspect the generated project, discuss prompt engineering, and look at different ways of working with an agent. Sometimes you want to stay in the driver's seat, sometimes the passenger's seat is more efficient, and sometimes it is fine to watch from the back.

The later chapters cover ways of extending a coding agent. We connect an existing MCP server, build a small one ourselves, install and write skills, and look at the difference between primary agents and sub-agents.

## Projects in this repository

The repository contains the workshop text as well as the projects used throughout it:

- [`tinybi-reference`](tinybi-reference/) is the result of the first large TinyBI prompt. It is a small FastAPI dashboard for exploring CSV files.
- [`tictactoe-mcp`](tictactoe-mcp/) is a Tic-Tac-Toe game exposed through a browser, a normal HTTP API, and MCP tools.
- [`tinybi2-reference`](tinybi2-reference/) is a more advanced CSV dashboard with a purpose-built MCP server.
- [`prompts`](prompts/) contains the original prompts used to generate the TinyBI examples.
- [`.agents/skills`](.agents/skills/) contains the skills used in Chapter 4.

Each project has its own README with the corresponding setup and run commands.

## Following the workshop

The chapters are intended to be read in order, starting with [Chapter 0](crashcourse/00%20setup.md). You will need a code editor, a coding agent, `uv`, and Node.js with `npx`. I use VS Code and OpenCode in the examples, but most of the concepts also apply to other editors and coding agents.

The AeroDataBox example in Chapter 3 requires a RapidAPI account and API key. The remaining examples can be run locally. Do not commit API keys or other credentials to this repository.

## License

This repository is available under the [MIT License](LICENSE).
