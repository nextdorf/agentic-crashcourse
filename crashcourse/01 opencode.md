# Opencode
The purpose of this chapter is to introduce the reader into opencode and generally how to get started.

## Getting Started
### Connect to Codex via OAuth
### Bring your own key

### Backend API policies

Compatibility Matrix (July 2026):

The important question is not only whether an endpoint technically works through another CLI, but whether the provider permits that use. This table shows which coding CLIs are allowed to use each endpoint under the provider's current policies. OpenCode Zen, Go, and OpenRouter allow access from all relevant coding CLIs; any remaining limitation is purely technical compatibility.

Availability | OpenAI's Codex | Anthropic's Claude | Google's Gemini | Zen | Go | OpenRouter
-------------|----------------|--------------------|-----------------|-----|----|-----------
Authentication method | OAuth | OAuth | OAuth | API key | API key | API key
CLI support | Any CLI supporting OAuth flow | Claude Code only | Gemini CLI only | All coding CLIs | All coding CLIs | All coding CLIs
Usage-based API available | ✅ | ✅ | ✅ | ✅ | 🗙 | ✅
Models | Codex 5.4, 5.5, 5.6 | Haiku, Sonnet, Opus, Fable | Gemini 3.5 Flash, 3.1 Pro, 3 Flash | GPT 5.x, Claude, Gemini 3.x, Grok, Qwen 3.x, DeepSeek V4, GLM 5.x, MiniMax M2/M3, Kimi K2.x; Big Pickle*, DeepSeek V4 Flash*, MiMo-V2.5*, North Mini Code*, Nemotron 3 Ultra* | GLM 5.1/5.2, Kimi K2.6/K2.7 Code, MiMo-V2.5/Pro, MiniMax M2.7/M3, Qwen3.6/3.7, DeepSeek V4 Pro/Flash; Zen's free models* remain available after reaching the Go limits | [Popular models for Coding](https://openrouter.ai/rankings?programming-language=Python#programming-languages); [Popular models by use case](https://openrouter.ai/apps); [free models](https://openrouter.ai/collections/free-models)
Pricing | [Plus $20/month, Pro from $100/month](https://developers.openai.com/codex/pricing) | [Pro $20/month, Max from $100/month](https://claude.com/pricing) | [AI Pro €21.99/month, AI Ultra from €99.99/month](https://gemini.google/subscriptions/) | [Pay per token](https://opencode.ai/docs/zen/#pricing) | [$5 for the first month, then $10/month](https://opencode.ai/docs/go/) | [Pay per token](https://openrouter.ai/pricing)
Usage limits | [Model-dependent five-hour and weekly limits; Pro offers 5x or 20x the Plus limits](https://developers.openai.com/codex/pricing) | [Rolling five-hour and weekly limits; Max offers 5x or 20x the Pro limits](https://support.anthropic.com/en/articles/9797557-usage-limit-best-practices) | [AI Pro: 1,500 requests/day; AI Ultra: 2,000 requests/day](https://geminicli.com/docs/resources/quota-and-pricing/) | Pay per token; [monthly spending limits can be configured](https://opencode.ai/docs/zen/#monthly-limits) | [$12 per 5 hours, $30 per week, $60 per month](https://opencode.ai/docs/go/#usage-limits) | Paid models have high global limits; [free models: 20 requests/minute and 50/day, or 1,000/day after purchasing at least $10 in credits](https://openrouter.ai/docs/api/reference/limits)

\* Free through Zen at the time of writing. These models may only be free temporarily and can have different data-retention rules. They remain available when the OpenCode Go usage limits are reached, but they are not part of the Go subscription endpoint itself.

OpenCode Zen, Go, and OpenRouter are not restricted to the OpenCode CLI. They provide API keys and standard API-style endpoints supported by all relevant coding CLIs. Go's [documented endpoints](https://opencode.ai/docs/go/#endpoints) use OpenAI-compatible or Anthropic-compatible request formats depending on the model. OpenRouter provides an OpenAI-compatible API and publishes [rankings of apps and agents using it](https://openrouter.ai/apps).

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
