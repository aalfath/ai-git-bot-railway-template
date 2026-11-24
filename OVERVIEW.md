# Deploy and Host AI Git Bot on Railway

AI Git Bot is a self-hosted, MIT-licensed AI workflow platform for Git repositories. It reviews pull requests, answers questions in review threads, triages issues and can turn issues into pull requests on GitHub, GitLab, Gitea, Bitbucket and Azure DevOps, using the LLM provider you choose (OpenAI-compatible, Anthropic, Gemini, OpenRouter, Ollama).

## About Hosting AI Git Bot

This template runs AI Git Bot 1.32.0 (official image, pinned by digest) with Railway PostgreSQL. You supply an LLM API key and a Git access token for the bot's account. Everything else is generated: the admin password, the encryption key for stored credentials, the secret webhook URL and its signing secret. On first boot, the start script creates the admin account and connects your LLM, your Git provider and a ready bot before the public port opens, so nobody can take over the `/setup` page. All configuration is stored in Postgres, so it survives redeploys. To go live, add one webhook in your Git provider.

## Common Use Cases

* Automatic AI review of every pull request a reviewer assigns to the bot
* Follow-up questions to the bot in review threads with `@bot-name`
* Issue triage, issue clean-up and coding-agent pull requests created from issues

## Dependencies for AI Git Bot Hosting

* An LLM API key (OpenAI by default; Anthropic, Google Gemini, OpenRouter or any OpenAI-compatible endpoint)
* A Git account for the bot with an access token (GitHub by default; GitLab, Gitea, Bitbucket and Azure DevOps also work)

### Deployment Dependencies

* AI Git Bot: https://github.com/tmseidel/ai-git-bot
* Template source: https://github.com/aalfath/ai-git-bot-railway-template
* GitHub token setup: https://github.com/tmseidel/ai-git-bot/blob/1.32.0/doc/GITHUB_SETUP.md
* LLM keys: https://platform.openai.com/api-keys, https://console.anthropic.com, https://openrouter.ai/keys

### Implementation Details

**Services:** `AI Git Bot` (web UI, webhooks and workflows; health check `/actuator/health`) and `Postgres` (all configuration, review history and audit log, on its volume).

**Variables you fill in:**

* `LLM_API_KEY`: your LLM provider's API key.
* `GIT_TOKEN`: an access token for the bot's Git account. On GitHub, a fine-grained token with Contents, Issues and Pull requests set to read and write.
* Optional: `LLM_PROVIDER` (`OPENAI`, `ANTHROPIC`, `GOOGLE`, `OPENROUTER`), `LLM_BASE_URL` for any OpenAI-compatible endpoint, `LLM_MODEL`, `GIT_PROVIDER` (`GITHUB`, `GITLAB`, `GITEA`, `BITBUCKET`, `AZURE_DEVOPS`) and `GIT_URL` for self-hosted GitLab or Gitea or your Azure DevOps organisation.

**After deploy:**

1. Open the public URL and sign in as `admin` with the `ADMIN_PASSWORD` shown in the service's Variables tab.
2. In your repository (or organisation) settings, add a webhook with the payload URL `https://YOUR-DOMAIN/api/webhook/YOUR-BOT_WEBHOOK_SECRET`, content type `application/json`, and the secret set to the value of `WEBHOOK_SIGNING_SECRET`. On GitHub, select the events Pull requests, Pull request reviews, Pull request review comments, Issue comments and Issues.
3. Add the bot's Git account as a reviewer on a pull request. The review appears as a comment in a minute or so.

The LLM and Git variables are read only on the first boot. To change them later, edit the integrations in the web UI under **AI Integrations** and **Git Integrations**.

**Resources:** PR reviews, comment replies and triage run within Railway's Free-plan 0.5 GB. The coding agent and the end-to-end test workflows build repositories and start Chromium, and need about 2 GB or more (Hobby plan). Code execution runs in a per-run sandbox user inside the container, with no Docker-in-Docker.

**Updates:** the service builds from the template's GitHub repository, so Railway shows an update notice when the pinned version is bumped. Read `CHANGELOG.md` before you apply one.

## Why Deploy AI Git Bot on Railway?

<!-- Recommended: Keep this section as shown below -->
Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying AI Git Bot on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.
<!-- End recommended section -->
