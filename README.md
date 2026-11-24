[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/ai-git-bot?utm_medium=integration&utm_source=button&utm_campaign=ai-git-bot)

# AI Git Bot on Railway

One-click Railway template for [AI Git Bot](https://github.com/tmseidel/ai-git-bot) **1.32.0**: self-hosted AI pull request review, issue triage and coding agents for GitHub, GitLab, Gitea, Bitbucket and Azure DevOps.

## What it deploys

| Service | Source | What it does |
|---|---|---|
| **AI Git Bot** | this repo (`Dockerfile`) | Web UI, webhook endpoint and workflows, on Railway's `PORT`. Health check `/actuator/health`. |
| **Postgres** | Railway PostgreSQL | All configuration (admin, integrations, bots), review history and the audit log, on its volume. |

The `Dockerfile` starts from the official image `tmseidel/ai-git-bot:1.32.0@sha256:f3ff5fde002bf0c391ab65282bba91786edaf90c9cfeb4a84883dbc68624972c` and adds a small wrapper (`railway/`):

- **Image size.** The official image unpacks to 4.7 GB, over the 4 GB image limit on Railway's Free and Trial plans. The wrapper removes the Cypress test runner (796 MB; upstream marks Cypress as experimental, while Playwright, the default end-to-end runner, stays) and the npm cache, then flattens the image to about 3.8 GB.
- **No open setup page.** Upstream creates the first admin at `/setup`, which the first visitor could claim. On an empty database the start script creates the admin from `ADMIN_PASSWORD` on a loopback-only instance (through upstream's `APP_CONFIG_JSON` import), and exits with an error if no admin exists. The public port only opens once the admin exists.
- **Ready bot.** The same first boot connects your LLM (`LLM_*`) and Git provider (`GIT_*`) and creates a bot named `ai-git-bot` with a generated webhook URL and signing secret.
- **Fits small plans.** The JVM heap, GC and processor count are sized from the container's cgroup limits (Railway shows the host's CPUs), Tomcat and the DB pool are capped, and git runs with small pack and thread limits. Upstream's DEBUG logging of every AI request is set to INFO.
- `DATABASE_URL` from Railway (`postgresql://…`) is converted to JDBC settings. Any startup failure exits non-zero, so Railway restarts the service.

## Variables

| Variable | Default | Notes |
|---|---|---|
| `LLM_API_KEY` | *(you enter it)* | LLM provider API key. |
| `GIT_TOKEN` | *(you enter it)* | Access token of the bot's Git account (GitHub: fine-grained, Contents + Issues + Pull requests read/write). |
| `LLM_PROVIDER` | `OPENAI` | `OPENAI` (also any OpenAI-compatible API), `ANTHROPIC`, `GOOGLE`, `OPENROUTER`. |
| `LLM_BASE_URL` | *(provider default)* | For OpenAI-compatible endpoints, e.g. `https://api.deepseek.com`. A trailing `/v1` is removed. |
| `LLM_MODEL` | *(provider default)* | OpenAI `gpt-6.2-sol`, Anthropic `claude-sonnet-5-5`, Gemini `gemini-4-argon`, OpenRouter `openrouter/auto`. |
| `GIT_PROVIDER` | `GITHUB` | `GITHUB`, `GITLAB`, `GITEA`, `BITBUCKET`, `AZURE_DEVOPS`. |
| `GIT_URL` | *(provider default)* | Self-hosted GitLab/Gitea URL, GitHub Enterprise URL, or `https://dev.azure.com/YOUR-ORG`. |
| `ADMIN_USERNAME` | `admin` | Web UI login. |
| `ADMIN_PASSWORD` | `${{secret(24)}}` | Generated. |
| `APP_ENCRYPTION_KEY` | `${{secret(48)}}` | Generated. Encrypts stored API keys and tokens; never change it after the first deploy. |
| `BOT_WEBHOOK_SECRET` | `${{secret(32)}}` | Generated. The bot's webhook URL is `https://YOUR-DOMAIN/api/webhook/<value>`. |
| `WEBHOOK_SIGNING_SECRET` | `${{secret(32)}}` | Generated. Enter it as the webhook's secret in your Git provider. |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | Private network. |
| `APP_PUBLIC_URL` | `https://${{RAILWAY_PUBLIC_DOMAIN}}` | Used for callback links. |
| `PORT` | `8080` | |

The `LLM_*`, `GIT_*`, `BOT_WEBHOOK_SECRET` and `WEBHOOK_SIGNING_SECRET` values are applied **only on the first boot** (empty database). Change them later in the web UI. If one is missing or wrong, the admin is still created and you add the rest in the UI.

## After deploy

1. Sign in at the public URL as `admin` with `ADMIN_PASSWORD`.
2. Add a webhook in your repository or organisation: payload URL `https://YOUR-DOMAIN/api/webhook/<BOT_WEBHOOK_SECRET>`, content type `application/json`, secret `WEBHOOK_SIGNING_SECRET`. GitHub events: Pull requests, Pull request reviews, Pull request review comments, Issue comments, Issues. See upstream's guides for [GitHub](https://github.com/tmseidel/ai-git-bot/blob/1.32.0/doc/GITHUB_SETUP.md), [GitLab](https://github.com/tmseidel/ai-git-bot/blob/1.32.0/doc/GITLAB_SETUP.md), [Gitea](https://github.com/tmseidel/ai-git-bot/blob/1.32.0/doc/GITEA_SETUP.md), [Bitbucket](https://github.com/tmseidel/ai-git-bot/blob/1.32.0/doc/BITBUCKET_SETUP.md) and [Azure DevOps](https://github.com/tmseidel/ai-git-bot/blob/1.32.0/doc/AZURE_DEVOPS_SETUP.md).
3. Request a review from the bot's account on a pull request. The bot ignores pull requests that its own account opened.

## Resources

PR reviews, review replies and issue triage fit Railway's Free plan (0.5 GB RAM, 1 vCPU): about 380 MB in use after a review in our test. The coding agent and the end-to-end test workflows clone and build repositories and start Chromium, so give the service **2 GB or more** (Hobby plan) if you enable them. Code execution uses upstream's per-run sandbox users inside the container; no Docker-in-Docker or privileged mode is needed.

## Updates

The service builds from this repository's `main` branch, so Railway shows an "update available" notice when we bump the pinned version. Each bump is listed in [`CHANGELOG.md`](CHANGELOG.md), breaking changes first, together with upstream's migration notes. Postgres data is kept across updates; upstream migrates the schema on start (Flyway).
