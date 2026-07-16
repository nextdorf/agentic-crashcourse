# OpenCode
This chapter gets OpenCode connected to a model and explains the billing, security, and policy choices hidden behind that apparently simple step.

## Getting Started
OpenCode is the coding agent, not the intelligence behind it. The CLI provides the chat interface, reads files, runs tools, and coordinates the work, but it does not ship model weights or include paid inference. Before it can do useful work, it needs a model provider.

[OpenCode supports more than 75 providers and local models](https://opencode.ai/docs/providers/). OpenCode Zen is the OpenCode team's curated provider and currently offers some free models, but it is still an optional external service rather than a model bundled into the CLI. You can instead connect OpenAI, OpenRouter, a cloud platform, or a local server such as Ollama.

The basic workflow is always the same:

1. Start OpenCode in a project with `opencode`.
2. Run `/connect` and authenticate with a provider.
3. Run `/models` and choose one of that provider's models.

The provider and access method matter. They determine which models you can use, how much they cost, where your prompts and code are processed, which limits apply, and whether a subscription may legally be used from OpenCode.

### Connect to Codex via OAuth
The workshop does not require OpenCode, Codex CLI, or any paid plan. Local models, free providers, and other coding agents can all follow the same workflows, although their commands and results will differ. **Do not buy another AI subscription just to complete this course.**

- If you already pay for Claude, use Claude Code. If you use Google's free consumer tier, Google AI Pro, or Google AI Ultra, use Antigravity CLI. Gemini CLI now serves Code Assist Standard or Enterprise organizations and users with paid Gemini API or Vertex AI access.
- If you already pay for ChatGPT, use Codex CLI or connect that subscription to OpenCode.
- If you do not have a subscription, use OpenCode with one of [Zen's free models](https://opencode.ai/docs/zen/#pricing). This is my recommended free starting point.
- OpenRouter also offers [free models](https://openrouter.ai/collections/free-models) and more choice, but choosing providers and checking their data policies requires more manual setup and oversight.
- If your computer is powerful enough, OpenCode can also connect to a local model and keep inference on your own machine.

I will demonstrate my own setup: OpenCode authenticated to OpenAI through an existing ChatGPT subscription and using a Codex model. OpenCode uses OpenAI's OAuth flow, so there is no API key to create. Requests made through this connection count against the subscription's usage limits instead of API token billing.

[OAuth](https://datatracker.ietf.org/doc/html/rfc6749) gives an application limited access to a service without giving that application your account password. In simplified form, OpenCode sends you to OpenAI, OpenAI authenticates you and asks for approval, and OpenCode receives tokens representing that approval. The password and the tokens are different secrets.

The local token is therefore still sensitive. Someone who steals it may be able to act with the access you granted until it expires or is revoked. Do not publish `auth.json`, copy it into a project, or share it as a troubleshooting artifact.

Connect an account (using OpenAI as the example):

1. Start the TUI with `opencode`.
2. Enter `/connect`.
3. Select **OpenAI**.
4. Select **ChatGPT Plus/Pro**. OpenCode opens the OpenAI login and authorization page in your browser.
5. Sign in to OpenAI and approve the request.
6. Return to OpenCode, run `/models`, and select a Codex model.

These steps follow OpenCode's [current OpenAI provider guide](https://opencode.ai/docs/providers/#openai). Provider names, supported plans, and login screens change, so use that guide as the source of truth if the interface no longer matches these screenshots or instructions.

### Bring your own key
Bring your own key (BYOK) means obtaining an API key from a provider and giving that key to OpenCode. Paid models also require billing or credits on the API account; the key does not turn a consumer subscription into API credit. For example, ChatGPT subscription billing and usage-based OpenAI API billing are separate.

Compared with subscription access, BYOK usually changes four things:

- **Billing:** API usage is normally charged for input, cached input, output, and sometimes tools or requests. Agentic coding repeatedly sends repository context and runs several model turns, so one task can consume far more tokens than one chat message. Check the provider's live pricing, such as [OpenAI's API pricing](https://developers.openai.com/api/docs/pricing), rather than estimating from the monthly subscription price.
- **Limits:** APIs commonly publish requests-per-minute and tokens-per-minute limits tied to an account tier. Subscriptions more often use rolling or weekly allowances whose exact token budgets are not disclosed. Paying per token does not mean unlimited throughput; [OpenAI's API limits](https://developers.openai.com/api/docs/guides/rate-limits), for example, still depend on usage tier and model.
- **Models:** The API and subscription catalogs are different products. A direct provider key limits you to that provider's API catalog, while gateways such as Zen and OpenRouter aggregate models from several companies. Gateways can offer greater model variety; BYOK itself does not.
- **Data controls:** Authentication method alone says nothing about privacy. Policies depend on the provider, endpoint, model, account type, and settings. OpenAI, for example, says [API data is not used for training by default](https://developers.openai.com/api/docs/guides/your-data), but default abuse-monitoring logs can retain prompts and responses for up to 30 days. Eligible API organizations can request stricter retention controls; some free model endpoints explicitly allow data collection. **Assume code leaves your machine unless you use a local model, and verify every provider in the request path.**

For this workshop I would not use a frontier-priced API key as the default coding backend. Long tool loops make the bill unpredictable, while a subscription gives us a fixed monthly cost. That is a workshop choice, not a universal rule: BYOK can be economical for occasional use, cheap models, or tightly capped workloads.

BYOK is the right mechanism when we build an AI-enabled service rather than interactively pair with an agent. A chatbot, document classifier, batch enrichment job, or embedding pipeline needs programmatic, metered access that can run without a human OAuth session. It is also useful when we need a particular low-cost model, explicit spend limits, service-account separation, or API-specific data controls.

To connect a key in OpenCode:

1. Create the key in the provider's console and, for paid models, configure billing and a spending limit where available.
2. Run `/connect` in OpenCode and select the provider.
3. Choose the manual API-key option when the provider offers several authentication methods, then paste the key.
4. Run `/models` and select a model exposed by that API account.

OpenCode stores keys entered through `/connect` alongside other provider credentials in the local [`auth.json`](https://opencode.ai/docs/providers/#credentials) file (Unix: `$HOME/.local/share/opencode/auth.json`). For a custom provider, reference an environment variable from `opencode.json` rather than writing the secret directly into a tracked configuration file. The [provider guide](https://opencode.ai/docs/providers/#custom-provider) shows the `{env:VARIABLE_NAME}` syntax.

### Backend API policies

Compatibility matrix (July 2026):

The important question is not only whether an endpoint technically works through another CLI, but whether the provider permits that authorization route. Subscription OAuth and a usage-billed API key are separate products, even when both ultimately run the same model. Antigravity CLI is Google's current consumer coding CLI; Gemini remains the name of the underlying models and paid API, while Gemini CLI continues for enterprise and paid API access.

Availability | [OpenAI Codex](https://opencode.ai/docs/providers#openai) | Anthropic Claude | [Google Antigravity](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli) | [OpenCode Zen](https://opencode.ai/docs/providers#opencode-zen) | [OpenCode Go](https://opencode.ai/docs/providers#opencode-go) | [OpenRouter](https://opencode.ai/docs/providers#openrouter) | [Hugging Face](https://opencode.ai/docs/providers/#hugging-face)
-------------|----------------|--------------------|-----------------|-----|----|------------|-------------
Subscription access | ChatGPT OAuth | Claude OAuth | Google OAuth | None | Subscription API key | None | None
CLI use of subscription access | Any CLI supporting OpenAI's OAuth flow | Claude Code only | Antigravity CLI for consumer plans; Gemini CLI for Code Assist Standard or Enterprise | Not applicable | Compatible coding clients | Not applicable | Not applicable
Separate usage-billed API | ✅ API key | ✅ API key | ✅ Gemini API key or Vertex AI credentials | ✅ API key | 🗙 | ✅ API key | ✅ API token
Paid API client support | Compatible OpenAI API clients | Compatible Anthropic API clients | Compatible Gemini API or Vertex AI clients | Compatible OpenAI or Anthropic API clients | Included above | Compatible OpenAI API clients | [Compatible OpenAI API clients](https://huggingface.co/docs/inference-providers/index#quick-setup-for-agents)
Example models | Codex 5.4, 5.5, 5.6 | Haiku, Sonnet, Opus, Fable | Gemini 3.5 Flash, 3.1 Pro, 3 Flash | GPT 5.x, Claude, Gemini 3.x, Grok, Qwen 3.x, DeepSeek V4, GLM 5.x, MiniMax M2/M3, Kimi K2.x; Big Pickle*, DeepSeek V4 Flash*, MiMo-V2.5*, North Mini Code*, Nemotron 3 Ultra* | GLM 5.1/5.2, Kimi K2.6/K2.7 Code, MiMo-V2.5/Pro, MiniMax M2.7/M3, Qwen3.6/3.7, DeepSeek V4 Pro/Flash; Zen's free models* remain available after reaching the Go limits | [Popular coding models](https://openrouter.ai/rankings?programming-language=Python#programming-languages); [models by use case](https://openrouter.ai/apps); [free models](https://openrouter.ai/collections/free-models) | [200+ models from multiple inference providers](https://huggingface.co/models?inference_provider=all)
Pricing | [Plus $20/month, Pro from $100/month; API billed separately](https://developers.openai.com/codex/pricing) | [Pro $20/month, Max from $100/month; API billed separately](https://claude.com/pricing) | Consumer Antigravity access: [Free, AI Pro €21.99/month, AI Ultra from €99.99/month](https://gemini.google/subscriptions/); API billed separately | [Pay per token](https://opencode.ai/docs/zen/#pricing) | [$5 for the first month, then $10/month](https://opencode.ai/docs/go/) | [Pay per token](https://openrouter.ai/pricing) | [Pay per use at the upstream provider's rate](https://huggingface.co/docs/inference-providers/pricing)
Usage limits | [Model-dependent five-hour and weekly limits; Pro offers 5x or 20x the Plus limits](https://developers.openai.com/codex/pricing) | [Rolling five-hour and weekly limits; Max offers 5x or 20x the Pro limits](https://support.anthropic.com/en/articles/9797557-usage-limit-best-practices) | Consumer Antigravity limits are plan-dependent; consult the [current documentation](https://antigravity.google/docs/) | Pay per token; [monthly spending limits can be configured](https://opencode.ai/docs/zen/#monthly-limits) | [$12 per 5 hours, $30 per week, $60 per month](https://opencode.ai/docs/go/#usage-limits) | Paid models have high global limits; [free models: 20 requests/minute and 50/day, or 1,000/day after purchasing at least $10 in credits](https://openrouter.ai/docs/api/reference/limits) | [Free users receive $0.10 in monthly credits; further use requires purchased credits and provider/model limits vary](https://huggingface.co/docs/inference-providers/pricing)

\* Free through Zen at the time of writing. These models may only be free temporarily and can have different data-retention rules. They remain available when the OpenCode Go usage limits are reached, but they are not part of the Go subscription endpoint itself.

OpenCode Zen, Go, OpenRouter, and Hugging Face Inference Providers are not restricted to the OpenCode CLI. They provide API keys or tokens and standard API-style endpoints usable by compatible coding clients. Go's [documented endpoints](https://opencode.ai/docs/go/#endpoints) use OpenAI-compatible or Anthropic-compatible request formats depending on the model. OpenRouter provides an OpenAI-compatible API and publishes [rankings of apps and agents using it](https://openrouter.ai/apps). Hugging Face provides an [OpenAI-compatible chat-completions endpoint](https://huggingface.co/docs/inference-providers/index#alternative-openai-compatible-chat-completions-endpoint-chat-only) and publishes setup instructions for several coding agents.

OpenAI includes Codex access in its Free and Go plans, although OpenCode's browser authentication currently supports ChatGPT Plus and Pro only. On June 18, 2026, Google's free consumer tier and Google AI Pro and Ultra users moved from Gemini CLI to Antigravity CLI. Gemini CLI remains available for Code Assist Standard or Enterprise organizations and for paid access through the Gemini API or Vertex AI.

The table, especially its pricing, changes frequently, and I probably will not keep it current forever. With the exception of OpenCode Go, AI inference providers have also often been vague about exact usage limits and the token allowances included with subscriptions.


- [Further reading on Claude Code](https://news.ycombinator.com/item?id=47444748)
- [Further reading on Gemini CLI and Antigravity CLI](https://github.com/google-gemini/gemini-cli/discussions/22970)



## Beyond the scope of this workshop
The following tools go beyond what we need for this workshop. They are included as starting points if you prefer a provider-specific agent, want a persistent personal assistant, need to serve a local model, or want a graphical document-chat application.

### Claude Code, Codex CLI, and Antigravity CLI
[Claude Code](https://code.claude.com/docs/en/overview), [Codex CLI](https://developers.openai.com/codex/cli/), and [Antigravity CLI](https://antigravity.google/docs/) are provider-native coding agents. Like OpenCode, they inspect a repository, edit files, and run terminal commands. Unlike OpenCode, each is primarily developed around its provider's own models, authentication, and product ecosystem.

**Best for:** developers who already have an eligible Claude or ChatGPT subscription, or eligible Google access, and prefer the provider's first-party experience over OpenCode's model flexibility. They are also the least surprising choice when an organization already manages that provider's enterprise accounts and policies.

For **Claude Code**, install the published package with npm or use another package manager listed in Anthropic's [setup guide](https://code.claude.com/docs/en/setup), enter a project, and start `claude`. The first run opens the login flow. Claude Code accepts eligible Claude subscriptions, Anthropic Console billing, and several cloud-provider integrations; the free Claude plan does not include it.

```bash
npm install -g @anthropic-ai/claude-code
cd path/to/project
claude
```

For **Codex CLI**, install the published package with npm or use another method from OpenAI's [installation guide](https://developers.openai.com/codex/cli/), enter a project, and start `codex`. Sign in with ChatGPT when prompted, or follow the [authentication guide](https://developers.openai.com/codex/auth) to use API billing or a headless login.

```bash
npm install -g @openai/codex
cd path/to/project
codex
```

For **Google's tooling**, check the date before following an old tutorial. On June 18, 2026, Google moved free, AI Pro, and AI Ultra users from Gemini CLI to Antigravity CLI. Install it from the official [Antigravity download page](https://antigravity.google/download) and follow the [Gemini CLI migration guide](https://antigravity.google/docs/gcli-migration) if you have existing settings. Gemini CLI remains supported for Code Assist Standard or Enterprise organizations and paid access to the Gemini API or Vertex AI; those users should use its current [installation](https://www.geminicli.com/docs/get-started/installation/) and [authentication](https://www.geminicli.com/docs/get-started/authentication/) guides.

### Hermes Agent and OpenClaw
[Hermes Agent](https://hermes-agent.nousresearch.com/docs/) and [OpenClaw](https://docs.openclaw.ai/) are persistent personal-agent platforms rather than focused coding CLIs. Both can use files and a shell, connect to several model providers, retain memory, run scheduled work, and expose an agent through messaging services. Use Claude Code, Codex CLI, Antigravity CLI, or OpenCode when you only want a repository coding loop.

**Best for:** technical users who want an always-available personal agent across the terminal, messaging apps, and automated workflows. Hermes emphasizes model flexibility, learned skills, and multiple execution backends. OpenClaw emphasizes a local-first, always-on gateway connecting messaging, devices, browser automation, memory, and scheduled jobs.

Install Hermes inside the VM from the official [Hermes Desktop download](https://hermes-agent.nousresearch.com/) on macOS or Windows. On Linux, clone the [official repository](https://github.com/NousResearch/hermes-agent) and follow its [manual installation instructions](https://hermes-agent.nousresearch.com/docs/getting-started/installation#manual--developer-installation). Then run the setup wizard and start its TUI. Choose one provider and verify a normal conversation before adding gateways, cron jobs, skills, or plugins.

```bash
hermes setup
hermes --tui
```

For OpenClaw, install it and let the [onboarding wizard](https://docs.openclaw.ai/start/wizard) configure the provider, gateway, and optional background service:

```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
openclaw dashboard
```

**Run these agents in a dedicated, disposable VM, not directly on your workstation.** They can execute commands with their user account's privileges, and their approval prompts are not security boundaries. Give the VM only the source, credentials, and network access required for the task; do not mount your home directory or reuse your everyday browser profile.

A container is a reasonable bare minimum, but it shares the host kernel and is not an escape-proof security boundary. Privileged containers, host Docker-socket mounts, broad bind mounts, and kernel vulnerabilities can all undermine the isolation. A microVM-based system such as [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) is a useful middle ground: each agent gets a separate kernel and private Docker daemon with less overhead than a traditional VM. Docker explains the design and tradeoffs in [Why MicroVMs: The Architecture Behind Docker Sandboxes](https://www.docker.com/blog/why-microvms-the-architecture-behind-docker-sandboxes/). Whichever boundary you choose, review the [Hermes security guide](https://hermes-agent.nousresearch.com/docs/user-guide/security) or [OpenClaw security guide](https://docs.openclaw.ai/gateway/security) and restrict messaging access before processing untrusted messages, web pages, plugins, or skills.

### Ollama, vLLM, and SGLang
[Ollama](https://docs.ollama.com/), [vLLM](https://docs.vllm.ai/en/stable/), and [SGLang](https://docs.sglang.io/) run model inference locally and expose HTTP APIs that OpenCode, Hermes, AnythingLLM, or your own application can call.

**Best for:** Ollama is the easiest of the three for individuals running a quantized model on a macOS, Windows, or Linux workstation. vLLM is the broad, established server for ML platform teams that prioritize model coverage and throughput. SGLang is attractive to performance-focused teams working with prefix-heavy requests, reasoning models, mixture-of-experts models, multimodal workloads, RL rollouts, or large distributed deployments.

For Ollama, use the signed installer from its [download page](https://ollama.com/download) or follow the [manual Linux installation](https://docs.ollama.com/linux) rather than piping a remote script into a shell. Download and start a model with `ollama run`; Ollama's native API listens at `http://localhost:11434/api` and its [OpenAI-compatible API](https://docs.ollama.com/api/openai-compatibility) at `http://localhost:11434/v1`. Keep it bound to a loopback interface unless you deliberately add authentication and network controls in front of it.

```bash
ollama run qwen3
```

For vLLM, create a fresh Python environment, follow the [hardware-specific installation guide](https://docs.vllm.ai/en/stable/getting_started/installation/), and serve a model. The API is then available at `http://localhost:8000/v1`.

```bash
uv venv --python 3.12 --seed
source .venv/bin/activate
uv pip install vllm --torch-backend=auto
vllm serve Qwen/Qwen2.5-1.5B-Instruct
```

For SGLang's standard NVIDIA path, follow its [installation guide](https://docs.sglang.io/get_started/install.html), then launch a model server. The API is available at `http://localhost:30000/v1`.

```bash
pip install uv
uv pip install --prerelease=allow sglang
python3 -m sglang.launch_server --model-path Qwen/Qwen2.5-0.5B-Instruct
```

Model size, precision, context length, and concurrency determine the required VRAM. CUDA, ROCm, CPU, Apple Silicon, and other backends have different support and installation paths, so do not blindly paste the NVIDIA quickstart onto another platform. An OpenAI-compatible endpoint also does not mean every OpenAI parameter behaves identically; check the [vLLM server reference](https://docs.vllm.ai/en/stable/serving/online_serving/openai_compatible_server/) or [SGLang API reference](https://docs.sglang.io/basic_usage/openai_api_completions.html) before integrating an application.

### AnythingLLM
[AnythingLLM](https://docs.anythingllm.com/introduction) is an all-in-one graphical application for chatting with local or cloud models, adding documents through retrieval-augmented generation (RAG), and using AI agents. It bundles the interface, document processing, embeddings, vector storage, workspaces, and model-provider configuration that you would otherwise have to assemble yourself.

**Best for:** individuals who want a private ChatGPT-like desktop application for their own documents, and teams that want a self-hosted multi-user RAG interface without building one. It is an application rather than a coding agent, although developers can use its API and agent features.

The easiest route is [AnythingLLM Desktop](https://docs.anythingllm.com/installation-desktop/overview): [download the official installer](https://anythingllm.com/download), start the application, and select either the built-in local model provider or a cloud provider during onboarding. Then create a workspace and upload documents. Desktop is single-user; local models require substantially more RAM or VRAM than cloud models. If you select a cloud model, the prompts and retrieved document passages sent to it leave your machine and are subject to that provider's policies.

For shared use, deploy the [Docker edition](https://docs.anythingllm.com/installation-docker/quickstart), persist `/app/server/storage`, open `http://localhost:3001`, and configure a provider under **Settings**. Enable authentication and HTTPS before exposing it beyond your machine. A provider running on the Docker host is not the container's `localhost`; follow the [Docker networking guide](https://docs.anythingllm.com/installation-docker/localhost) for the correct host address.


## OpenCode Web
## OpenCode Zen and Go



![OpenCode Web](images/01%20opencode-web.png)

![OpenCode TUI](images/01%20opencode-tui.png)
