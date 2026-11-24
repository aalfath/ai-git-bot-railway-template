# Changelog

## 1.32.0 (2026-11-24)

First release of the template.

- AI Git Bot 1.32.0, official image `tmseidel/ai-git-bot:1.32.0@sha256:f3ff5fde002bf0c391ab65282bba91786edaf90c9cfeb4a84883dbc68624972c`.
- Cypress removed and the image flattened (3.8 GB, under Railway's 4 GB Free/Trial limit). Playwright stays.
- Admin, AI integration, Git integration and bot created on first boot on a loopback-only instance; the service exits if no admin exists.
- JVM, Tomcat, DB pool and git memory sized from the container limits.
- Forwarded headers from Railway's proxy honoured, so redirects and cookies use https.
