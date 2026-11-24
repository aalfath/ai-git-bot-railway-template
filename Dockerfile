# AI Git Bot on Railway: the official image, pinned by version and digest,
# made to fit Railway's 4 GB Free/Trial image cap and started by a small wrapper.
FROM tmseidel/ai-git-bot:1.32.0@sha256:f3ff5fde002bf0c391ab65282bba91786edaf90c9cfeb4a84883dbc68624972c AS upstream

USER root
# - Cypress (796 MB binary + npm package) is an experimental E2E runner upstream
#   ("Only playwright is well-tested"); dropping it brings the unpacked image from
#   4.7 GB to about 3.8 GB. Playwright, the default E2E runner, stays.
# - psycopg2 lets the start script check the database before the app boots.
RUN set -eux; \
    npm uninstall -g cypress; \
    rm -r /home/appuser/.cache/Cypress /root/.npm; \
    pip3 install --no-cache-dir psycopg2-binary==2.9.11; \
    java -version
COPY railway/railway-start.sh /usr/local/bin/railway-start.sh
COPY railway/railway_helper.py /usr/local/lib/railway/railway_helper.py
# git wrapper first in PATH: caps clone/fetch memory for the agents' git calls.
COPY railway/git /usr/local/bin/git
RUN chmod 0755 /usr/local/bin/railway-start.sh /usr/local/bin/git && chmod 0644 /usr/local/lib/railway/railway_helper.py

# Flatten, so the deleted layers no longer count towards the image size.
FROM scratch
COPY --from=upstream / /
ENV PATH=/home/appuser/go/bin:/usr/lib/go/bin:/opt/java/openjdk/bin:/home/appuser/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    JAVA_HOME=/opt/java/openjdk \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    JAVA_VERSION=jdk-21.0.13.1+2 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/home/appuser/.cache/ms-playwright \
    NPM_CONFIG_PREFIX=/usr/local \
    NODE_PATH=/usr/local/lib/node_modules \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
    COREPACK_ENABLE_AUTO_PIN=0 \
    GOPATH=/home/appuser/go \
    SPRING_PROFILES_ACTIVE=docker
USER appuser
WORKDIR /app
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/railway-start.sh"]
