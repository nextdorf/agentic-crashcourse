# Introduction

We are going to let an AI agent read a repository, run commands, edit files, and occasionally make a confident mess. This chapter explains why the workshop uses VS Code, OpenCode, and OpenAI's Codex, and places coding agents in the short history that produced them.

## A history from autocomplete to agents

Coding agents appeared suddenly if you only look at the polished products. The underlying progression was more gradual:

- **2021:** GitHub Copilot's technical preview made large-model code completion visible to mainstream developers. Autocomplete could now produce a whole function rather than the next word.
- **2022:** ChatGPT made conversational interaction with a language model ordinary. Developers pasted in errors and code, but still had to provide the context and apply changes themselves.
- **2023:** Editor-native assistants and tools such as [Aider](https://aider.chat/) moved from answering questions toward editing real files and reviewing diffs. "Chat with your codebase" became a product category.
- **2024:** Tool use and agent loops became central. Models could search repositories, run tests, inspect failures, and try again. Benchmarks such as [SWE-bench](https://www.swebench.com/) shifted attention from plausible snippets to resolving issues in real repositories.
- **2025:** Terminal agents such as Claude Code, Codex CLI, and OpenCode made that loop feel normal. The request changed from "write me a function" to "investigate this problem, modify the project, and verify the result."
- **2026:** Coding-specialized models advanced alongside the agents using them. OpenAI's Sol and Anthropic's Fable represent the shift from general chat models that can write code toward models optimized for long-running software-engineering work and tool use.

This is a simplified history rather than a claim that each phase neatly replaced the last. Research prototypes came before the commercial tools, autocomplete remains useful, and current agents still fail at simple tasks. The important trend is the expansion of the loop: from predicting text, to discussing code, to acting inside a development environment.

### Attention, but not the whole story

The 2017 paper [*Attention Is All You Need*](https://arxiv.org/abs/1706.03762) introduced the Transformer architecture. Its central move was to use attention so a model could relate different positions in a sequence without relying on the recurrent structures common at the time. Transformers scaled extraordinarily well and became the foundation for the large language models behind current coding assistants.

That history brings us to the practical question for this workshop: which tools do we need to work with a coding agent ourselves?

## Setup

Install OpenCode and `uv` before the workshop, and make sure you have a code editor available. We will connect OpenCode to a model in Chapter 1 and use `uv` to manage the Python project in Chapter 2.

### OpenCode

Use a package manager appropriate for your system:

```bash
# macOS or Linux with Homebrew
brew install anomalyco/tap/opencode

# Windows with Chocolatey
choco install opencode

# Windows with Scoop
scoop install opencode

# Arch Linux
sudo pacman -S opencode
```

Other installation options and release binaries are listed in the [official OpenCode documentation](https://opencode.ai/docs/). Verify the installation, then start OpenCode from the repository root:

```bash
opencode --version
opencode
```

You do not need to choose or purchase a model yet. Chapter 1 walks through the provider options before connecting one.

### uv

[`uv`](https://docs.astral.sh/uv/) manages the Python version, virtual environment, and dependencies used later in the workshop. Install it with a package manager where possible:

```bash
# Windows
winget install --id=astral-sh.uv -e

# macOS with Homebrew
brew install uv

# Any system with pipx already available
pipx install uv

# Any system with a compatible Rust toolchain
cargo install --locked uv
```

The Rust route compiles `uv` from source and is mainly useful if you already have the toolchain. If none of these package managers are available, download a binary from the project's [GitHub releases](https://github.com/astral-sh/uv/releases); we deliberately do not pipe remote installation scripts into a shell.

Restart the terminal if the installation changed `PATH`, then verify `uv` and install a managed Python version for the later project:

```bash
uv --version
uv python install 3.14 # or alternatively version 3.13
```

### VS Code (Optional)

You should have an IDE or code editor for inspecting the project and reviewing the agent's changes, but the workshop does not depend on a particular one. Keep using PyCharm, Zed, Vim, or another editor if it already works for you; VS Code is the documented default because it is familiar to many learners and integrates directly with OpenCode.

Download the installer for Windows, macOS, or Linux from the [official VS Code download page](https://code.visualstudio.com/Download) and follow the platform instructions. On Debian or Ubuntu, you can install a downloaded `.deb` package with:

```bash
sudo apt install ./code_*.deb
```

Open this repository as a folder from **File > Open Folder**, or open a terminal in the repository and run:

```bash
code .
```

On macOS, run **Shell Command: Install 'code' command in PATH** from the VS Code Command Palette first if the `code` command is unavailable. The [official setup guides](https://code.visualstudio.com/docs/setup/setup-overview) cover each operating system.

## Why this stack

The setup above is a practical default, not a claim that everyone should use the same editor, agent, or model.

"Free software" describes the freedom to run, study, modify, and share software, not merely software with a price of zero. "Open source" comes from a different movement and emphasizes development around inspectable source code and licenses that permit reuse and modification. Both helped create the shared technical foundations of modern data engineering, including Linux, Python, PostgreSQL, and Git.

VS Code is approachable, capable, widely supported, and already familiar to many learners. Its upstream source is available in Microsoft's [`vscode`](https://github.com/microsoft/vscode) repository, while Microsoft's Visual Studio Code distribution adds its own branding, license terms, and service integrations. [VSCodium](https://vscodium.com/) provides community-built binaries without Microsoft's branding and telemetry defaults.

OpenCode is the coding agent: it provides the interface, reads files, runs tools, and coordinates work. It is open source and provider-independent, so the model behind it can be changed without replacing the whole workflow. Codex is a proprietary model served by OpenAI; I cannot inspect its weights or reproduce its training, but it currently performs well on the coding tasks I care about.

For this workshop, I connect OpenCode to Codex through an existing ChatGPT subscription. Chapter 1 covers alternative providers, local models, costs, authentication, and privacy so that this choice does not become a hidden requirement.
