"""Railway helper for AI Git Bot: JDBC settings and the first-boot setup.

  railway_helper.py jdbc       print shell exports for JDBC_URL/JDBC_USER/JDBC_PASSWORD
  railway_helper.py bootstrap  on an empty database, create the admin (and seed the
                               integrations and the bot) on a loopback-only instance

Never prints a password or key.
"""
import json, os, random, shlex, signal, socket, subprocess, sys, time, urllib.parse, urllib.request

import psycopg2

LOG = "[railway-setup]"
LLM_PROVIDERS = {"OPENAI", "ANTHROPIC", "GOOGLE", "OPENROUTER", "OLLAMA", "LLAMACPP"}
LLM_DEFAULT_URLS = {
    "OPENAI": "https://api.openai.com",
    "ANTHROPIC": "https://api.anthropic.com",
    "GOOGLE": "https://generativelanguage.googleapis.com",
    "OPENROUTER": "https://openrouter.ai/api",
}
GIT_PROVIDERS = {"GITHUB", "GITLAB", "GITEA", "BITBUCKET", "AZURE_DEVOPS"}
GIT_DEFAULT_URLS = {"GITHUB": "https://github.com", "GITLAB": "https://gitlab.com",
                    "BITBUCKET": "https://bitbucket.org", "AZURE_DEVOPS": "https://dev.azure.com"}


def log(msg):
    print(f"{LOG} {msg}", flush=True)


def env(name, default=""):
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


def parse_db_url():
    url = os.environ["DATABASE_URL"].strip()
    if url.startswith("jdbc:"):
        url = url[5:]
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("postgres", "postgresql") or not p.hostname:
        sys.exit(f"{LOG} DATABASE_URL must be a postgresql:// URL")
    user = urllib.parse.unquote(p.username or os.environ.get("DATABASE_USERNAME", ""))
    password = urllib.parse.unquote(p.password or os.environ.get("DATABASE_PASSWORD", ""))
    host = p.hostname
    if ":" in host:  # IPv6 literal
        host = f"[{host}]"
    port = p.port or 5432
    db = (p.path or "/").lstrip("/") or "railway"
    query = f"?{p.query}" if p.query else ""
    return {"jdbc": f"jdbc:postgresql://{host}:{port}/{db}{query}", "user": user, "password": password,
            "host": p.hostname, "port": port, "db": db, "query": dict(urllib.parse.parse_qsl(p.query))}


def cmd_jdbc():
    d = parse_db_url()
    for key, val in (("JDBC_URL", d["jdbc"]), ("JDBC_USER", d["user"]), ("JDBC_PASSWORD", d["password"])):
        print(f"{key}={shlex.quote(val)}")


def connect(d, timeout_s=240):
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            kw = {"host": d["host"], "port": d["port"], "dbname": d["db"], "user": d["user"],
                  "password": d["password"], "connect_timeout": 5}
            if "sslmode" in d["query"]:
                kw["sslmode"] = d["query"]["sslmode"]
            conn = psycopg2.connect(**kw)
            conn.autocommit = True
            return conn
        except psycopg2.OperationalError as e:
            last = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
            time.sleep(3)
    sys.exit(f"{LOG} database not reachable after {timeout_s}s ({last})")


def admin_count(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.admin_users') IS NOT NULL")
        if not cur.fetchone()[0]:
            return 0
        cur.execute("SELECT count(*) FROM admin_users")
        return cur.fetchone()[0]


def build_document(full):
    doc = {"adminUsers": [{"username": env("ADMIN_USERNAME", "admin"), "password": os.environ["ADMIN_PASSWORD"]}]}
    if not full:
        return doc, []
    seeded = []
    llm_key = env("LLM_API_KEY")
    provider = env("LLM_PROVIDER", "OPENAI").upper()
    ai_name = None
    if provider not in LLM_PROVIDERS:
        log(f"LLM_PROVIDER '{provider}' is not one of {sorted(LLM_PROVIDERS)}: skipping the AI integration")
    elif not llm_key and provider not in ("OLLAMA", "LLAMACPP"):
        log("LLM_API_KEY is empty: skipping the AI integration (add it in the web UI)")
    else:
        api_url = env("LLM_BASE_URL", LLM_DEFAULT_URLS.get(provider, "")).rstrip("/")
        if api_url.endswith("/v1") and provider in ("OPENAI", "OPENROUTER"):
            api_url = api_url[:-3]  # the app appends /v1/chat/completions itself
        if not api_url:
            log(f"LLM_BASE_URL is required for {provider}: skipping the AI integration")
        else:
            ai_name = "Default AI"
            ai = {"name": ai_name, "providerType": provider, "apiUrl": api_url,
                  "model": env("LLM_MODEL", "gpt-6.2-sol"), "maxTokens": 16000}
            if llm_key:
                ai["apiKey"] = llm_key
            if provider == "ANTHROPIC":
                ai["apiVersion"] = "2023-06-01"
            doc["aiIntegrations"] = [ai]
            seeded.append(f"AI integration '{ai_name}' ({provider}, model {ai['model']})")
    git_token = env("GIT_TOKEN")
    git_provider = env("GIT_PROVIDER", "GITHUB").upper()
    git_name = None
    if git_provider not in GIT_PROVIDERS:
        log(f"GIT_PROVIDER '{git_provider}' is not one of {sorted(GIT_PROVIDERS)}: skipping the Git integration")
    elif not git_token:
        log("GIT_TOKEN is empty: skipping the Git integration and the bot (add them in the web UI)")
    else:
        git_url = env("GIT_URL", GIT_DEFAULT_URLS.get(git_provider, "")).rstrip("/")
        if not git_url:
            log(f"GIT_URL is required for {git_provider}: skipping the Git integration and the bot")
        else:
            git_name = "Default Git"
            doc["gitIntegrations"] = [{"name": git_name, "providerType": git_provider, "url": git_url,
                                       "token": git_token, "transport": "HTTP", "postReviewAction": "NONE"}]
            seeded.append(f"Git integration '{git_name}' ({git_provider}, {git_url})")
    hook = env("BOT_WEBHOOK_SECRET")
    if ai_name and git_name and hook:
        bot = {"name": "ai-git-bot", "webhookSecret": hook, "enabled": True,
               "aiIntegration": {"name": ai_name}, "gitIntegration": {"name": git_name},
               "workflowConfiguration": {"name": "Default"},
               "issueWorkflowConfiguration": {"name": "Issue: Coding Agent"}}
        signing = env("WEBHOOK_SIGNING_SECRET")
        if signing:
            bot["webhookSigningSecret"] = signing
        doc["bots"] = [bot]
        seeded.append("bot 'ai-git-bot' (webhook path /api/webhook/<BOT_WEBHOOK_SECRET>)")
    return doc, seeded


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_loopback_import(document, timeout_s):
    port = free_port()
    child_env = dict(os.environ)
    child_env["APP_CONFIG_JSON"] = json.dumps(document)
    child_env["SERVER_PORT"] = str(port)
    child_env["SERVER_ADDRESS"] = "127.0.0.1"
    child_env["LOGGING_LEVEL_ORG_FLYWAYDB"] = "WARN"
    proc = subprocess.Popen(["java", "-jar", "/app/app.jar"], cwd="/app", env=child_env)
    url = f"http://127.0.0.1:{port}/actuator/health"
    deadline = time.time() + timeout_s
    healthy = False
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                log(f"setup instance exited early with code {proc.returncode}")
                return False
            try:
                with urllib.request.urlopen(url, timeout=3) as r:
                    if r.status == 200:
                        healthy = True
                        break
            except Exception:
                pass
            time.sleep(2)
        return healthy
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def cmd_bootstrap():
    if not env("ADMIN_PASSWORD"):
        sys.exit(f"{LOG} ADMIN_PASSWORD is empty: keep the generated value")
    if len(os.environ["ADMIN_PASSWORD"].strip()) < 8:
        sys.exit(f"{LOG} ADMIN_PASSWORD must be at least 8 characters")
    d = parse_db_url()
    conn = connect(d)
    if admin_count(conn) > 0:
        log("admin account exists: nothing to set up")
        return
    # Overlapping Railway deploys: only one runs the first-boot setup.
    waited = 0
    with conn.cursor() as cur:
        while True:
            cur.execute("SELECT pg_try_advisory_lock(7311700)")
            if cur.fetchone()[0]:
                break
            if waited == 0:
                log("another deploy is running the first-boot setup; waiting")
            time.sleep(3 + random.random() * 2)
            waited += 1
    try:
        if admin_count(conn) > 0:
            log("admin account was created by another deploy")
            return
        timeout_s = int(env("SETUP_TIMEOUT_SECONDS", "480"))
        document, seeded = build_document(full=True)
        log("empty database: creating the admin account on a loopback-only instance (the public port stays closed)")
        ok = run_loopback_import(document, timeout_s)
        if ok and admin_count(conn) == 0 and len(document) > 1:
            log("the configuration import failed (see the log above); retrying with the admin account only")
            seeded = []
            ok = run_loopback_import(build_document(full=False)[0], timeout_s)
        if not ok or admin_count(conn) == 0:
            sys.exit(f"{LOG} the admin account was not created; refusing to start with an open /setup page")
        log(f"admin account '{env('ADMIN_USERNAME', 'admin')}' created")
        for item in seeded:
            log(f"seeded {item}")
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(7311700)")
        conn.close()


if __name__ == "__main__":
    {"jdbc": cmd_jdbc, "bootstrap": cmd_bootstrap}[sys.argv[1]]()
