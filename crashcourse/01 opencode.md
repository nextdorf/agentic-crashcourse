# OpenCode
This chapter gets OpenCode connected to a model and explains the billing, security, and policy choices hidden behind that apparently simple step.

## Getting Started
OpenCode is the coding agent, not the intelligence behind it. The CLI provides the chat interface, reads files, runs tools, and coordinates the work, but it does not ship model weights or include paid inference. Before it can do useful work, it needs a model provider.

[OpenCode supports more than 75 providers and local models](https://opencode.ai/docs/providers/). OpenCode Zen is the team's own curated provider and currently offers some free models, but it is still an optional external service rather than a model bundled into the CLI. You can instead connect OpenAI, OpenRouter, a cloud platform, or a local server such as Ollama.

The basic workflow is always the same:

1. Start OpenCode in a project with `opencode`.
2. Run `/connect` and authenticate with a provider.
3. Run `/models` and choose one of that provider's models.

The provider decision matters. It determines which models you can use, how much they cost, where your prompts and code are processed, which limits apply, and whether a subscription may legally be used from OpenCode.

### Connect to Codex via OAuth
The workshop does not require OpenCode, Codex, or any paid plan. Local models, free providers, and other coding agents can all follow the same workflows, although their commands and results will differ. **Do not buy another AI subscription just to complete this course.**

- If you already pay for Claude or Gemini, use the provider's own CLI.
- If you already pay for ChatGPT, use Codex CLI or connect that subscription to OpenCode.
- If you do not have a subscription, use OpenCode with one of [Zen's free models](https://opencode.ai/docs/zen/#pricing). This is my recommended free starting point.
- OpenRouter also offers [free models](https://openrouter.ai/collections/free-models) and more choice, but choosing providers and checking their data policies requires more manual setup and oversight.
- If your computer is powerful enough, OpenCode can also connect to a local model and keep inference on your own machine.

I will demonstrate my own setup: OpenCode connected to Codex through an existing ChatGPT subscription. OpenCode uses OpenAI's OAuth flow, so there is no API key to create. Requests made through this connection count against the subscription's usage limits instead of API token billing.

[OAuth](https://datatracker.ietf.org/doc/html/rfc6749) gives an application limited access to a service without giving that application your account password. In simplified form, OpenCode sends you to OpenAI, OpenAI authenticates you and asks for approval, and OpenCode receives tokens representing that approval. The password and the tokens are different secrets.

The local token is therefore still sensitive. Someone who steals it may be able to act with the access you granted until it expires or is revoked. Do not publish `auth.json`, copy it into a project, or share it as a troubleshooting artifact.

Connect the account (exemplary OpenAI):

1. Start the TUI with `opencode`.
2. Enter `/connect`.
3. Select **OpenAI**.
4. Select **ChatGPT Plus/Pro**. OpenCode opens the OpenAI login and authorization page in your browser.
5. Sign in to OpenAI and approve the request.
6. Return to OpenCode, run `/models`, and select a Codex model.

These steps follow OpenCode's [current OpenAI provider guide](https://opencode.ai/docs/providers/#openai). Provider names, supported plans, and login screens change, so use that guide as the source of truth if the interface no longer matches these screenshots or instructions.

### Bring your own key
Bring your own key (BYOK) means obtaining an API key from a provider and giving that key to OpenCode. Paid models also require billing or credits on the API account; the key does not turn a consumer subscription into API credit. For example, ChatGPT billing (subscription-based model) and OpenAI API billing (pay per token model) are separate.

Compared with subscription access, BYOK usually changes four things:

- **Billing:** API usage is normally charged for input, cached input, output, and sometimes tools or requests. Agentic coding repeatedly sends repository context and runs several model turns, so one task can consume far more tokens than one chat message. Check the provider's live pricing, such as [OpenAI's API pricing](https://developers.openai.com/api/docs/pricing), rather than estimating from the monthly subscription price.
- **Limits:** APIs commonly publish requests-per-minute and tokens-per-minute limits tied to an account tier. Subscriptions more often use rolling or weekly allowances whose exact token budgets are not disclosed. Paying per token does not mean unlimited throughput; [OpenAI's API limits](https://developers.openai.com/api/docs/guides/rate-limits), for example, still depend on usage tier and model.
- **Models:** The API and subscription catalogs are different products. A direct provider key limits you to that provider's API catalog, while gateways such as Zen and OpenRouter aggregate models from several companies. Usually BYOK comes with more model-variety.
- **Data controls:** Authentication method alone says nothing about privacy. Policies depend on the provider, endpoint, model, account type, and settings. OpenAI, for example, says [API data is not used for training by default](https://developers.openai.com/api/docs/guides/your-data), but default abuse-monitoring logs can retain prompts and responses for up to 30 days. Eligible API organizations can request stricter retention controls; some free model endpoints explicitly allow data collection. **Assume code leaves your machine unless you use a local model, and verify every provider in the request path.**

For this workshop I would not use a frontier-priced API key as the default coding backend. Long tool loops make the bill unpredictable, while a subscription gives us a fixed monthly cost. That is a workshop choice, not a universal rule: BYOK can be economical for occasional use, cheap models, or tightly capped workloads.

BYOK is the right mechanism when we build an AI-enabled service rather than interactively pair with an agent. A chatbot, document classifier, batch enrichment job, or embedding pipeline needs programmatic, metered access that can run without a human OAuth session. It is also useful when we need a particular low-cost model, explicit spend limits, service-account separation, or an API-only data control.

To connect a key in OpenCode:

1. Create the key in the provider's console and, for paid models, configure billing and a spending limit where available.
2. Run `/connect` in OpenCode and select the provider.
3. Choose the manual API-key option when the provider offers several authentication methods, then paste the key.
4. Run `/models` and select a model exposed by that API account.

OpenCode stores keys entered through `/connect` in the same local [`auth.json`](https://opencode.ai/docs/providers/#credentials) (Unix: `$HOME/.local/share/opencode/auth.json`) file as its other provider credentials. For a custom provider, reference an environment variable from `opencode.json` rather than writing the secret directly into a tracked configuration file. The [provider guide](https://opencode.ai/docs/providers/#custom-provider) shows the `{env:VARIABLE_NAME}` syntax.

### Backend API policies

Compatibility Matrix (July 2026):

The important question is not only whether an endpoint technically works through another CLI, but whether the provider permits that use. This table shows which coding CLIs are allowed to use each endpoint under the provider's current policies. OpenCode Zen, Go, OpenRouter, and Hugging Face Inference Providers allow access from all relevant coding CLIs; any remaining limitation is purely technical compatibility.

Availability | [OpenAI's Codex](https://opencode.ai/docs/providers#openai) | Anthropic's Claude | Google's Gemini | [Zen](https://opencode.ai/docs/providers#opencode-zen) | [Go](https://opencode.ai/docs/providers#opencode-go) | [OpenRouter](https://opencode.ai/docs/providers#openrouter) | [Hugging Face](https://opencode.ai/docs/providers/#hugging-face)
-------------|----------------|--------------------|-----------------|-----|----|------------|-------------
Authentication method | OAuth | OAuth | OAuth | API key | API key | API key | API token
CLI support | Any CLI supporting OAuth flow | Claude Code only | Gemini CLI only | All coding CLIs | All coding CLIs | All coding CLIs | [All coding CLIs](https://huggingface.co/docs/inference-providers/index#quick-setup-for-agents)
Usage-based API available | ✅ | ✅ | ✅ | ✅ | 🗙 | ✅ | ✅
Models | Codex 5.4, 5.5, 5.6 | Haiku, Sonnet, Opus, Fable | Gemini 3.5 Flash, 3.1 Pro, 3 Flash | GPT 5.x, Claude, Gemini 3.x, Grok, Qwen 3.x, DeepSeek V4, GLM 5.x, MiniMax M2/M3, Kimi K2.x; Big Pickle*, DeepSeek V4 Flash*, MiMo-V2.5*, North Mini Code*, Nemotron 3 Ultra* | GLM 5.1/5.2, Kimi K2.6/K2.7 Code, MiMo-V2.5/Pro, MiniMax M2.7/M3, Qwen3.6/3.7, DeepSeek V4 Pro/Flash; Zen's free models* remain available after reaching the Go limits | [Popular models for Coding](https://openrouter.ai/rankings?programming-language=Python#programming-languages); [Popular models by use case](https://openrouter.ai/apps); [free models](https://openrouter.ai/collections/free-models) | [200+ models from multiple inference providers](https://huggingface.co/models?inference_provider=all)
Pricing | [Plus $20/month, Pro from $100/month](https://developers.openai.com/codex/pricing) | [Pro $20/month, Max from $100/month](https://claude.com/pricing) | [AI Pro €21.99/month, AI Ultra from €99.99/month](https://gemini.google/subscriptions/) | [Pay per token](https://opencode.ai/docs/zen/#pricing) | [$5 for the first month, then $10/month](https://opencode.ai/docs/go/) | [Pay per token](https://openrouter.ai/pricing) | [Pay per use at the upstream provider's rate](https://huggingface.co/docs/inference-providers/pricing)
Usage limits | [Model-dependent five-hour and weekly limits; Pro offers 5x or 20x the Plus limits](https://developers.openai.com/codex/pricing) | [Rolling five-hour and weekly limits; Max offers 5x or 20x the Pro limits](https://support.anthropic.com/en/articles/9797557-usage-limit-best-practices) | [AI Pro: 1,500 requests/day; AI Ultra: 2,000 requests/day](https://geminicli.com/docs/resources/quota-and-pricing/) | Pay per token; [monthly spending limits can be configured](https://opencode.ai/docs/zen/#monthly-limits) | [$12 per 5 hours, $30 per week, $60 per month](https://opencode.ai/docs/go/#usage-limits) | Paid models have high global limits; [free models: 20 requests/minute and 50/day, or 1,000/day after purchasing at least $10 in credits](https://openrouter.ai/docs/api/reference/limits) | [Free users receive $0.10 in monthly credits; further use requires purchased credits and provider/model limits vary](https://huggingface.co/docs/inference-providers/pricing)

\* Free through Zen at the time of writing. These models may only be free temporarily and can have different data-retention rules. They remain available when the OpenCode Go usage limits are reached, but they are not part of the Go subscription endpoint itself.

OpenCode Zen, Go, OpenRouter, and Hugging Face Inference Providers are not restricted to the OpenCode CLI. They provide API keys or tokens and standard API-style endpoints supported by all relevant coding CLIs. Go's [documented endpoints](https://opencode.ai/docs/go/#endpoints) use OpenAI-compatible or Anthropic-compatible request formats depending on the model. OpenRouter provides an OpenAI-compatible API and publishes [rankings of apps and agents using it](https://openrouter.ai/apps). Hugging Face provides an [OpenAI-compatible chat-completions endpoint](https://huggingface.co/docs/inference-providers/index#alternative-openai-compatible-chat-completions-endpoint-chat-only) and publishes setup instructions for several coding agents.

OpenAI itself includes Codex in its Free and Go plans, but OpenCode's browser authentication currently supports ChatGPT Plus and Pro only. Google AI Plus is also not supported by Gemini CLI. That is why neither plan appears in the pricing row.

Note, that the above table (especially the pricing) is constantly changing and I will probaably not keep it up-to-date forever. Also, with the exception of Opencode Go, AI Inference-providers have been notoriously vague in the past regarding their exact usage limits and how many tokens any of the subscription options include. 


Further reading regarding Claude Code: https://news.ycombinator.com/item?id=47444748

Further reading regarding Gemini/Antigravity: https://github.com/google-gemini/gemini-cli/discussions/22970



## Alternatives
### Claude CLI, Codex, Gemini
### Hermes/Openclaw
### Anything LLM
## Opencode Web
## Zen/Go



![Opencode Web](images/01%20opencode-web.png)

![Opencode TUI](images/01%20opencode-tui.png)
