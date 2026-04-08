"""Seed Langfuse with a dev account, organization, project, and API keys.

Runs at startup in development mode. Uses the Langfuse HTTP API (signup + trpc)
to create a deterministic dev account. API keys are written to app config if
the current keys don't work.

Credentials:
  - Email: admin@sre-triage.local
  - Password: admin123
  - Dashboard: http://localhost:3100
"""

import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

LANGFUSE_EMAIL = "admin@sre-triage.local"
LANGFUSE_PASSWORD = "admin123"
LANGFUSE_ORG_NAME = "SRE Triage Agent"
LANGFUSE_PROJECT_NAME = "SRE Triage Agent"


def seed_langfuse(langfuse_host: str) -> dict[str, str] | None:
    """Create Langfuse dev account and return API keys if needed.

    Returns {"public_key": ..., "secret_key": ...} or None if already set up.
    """
    internal_host = langfuse_host  # e.g. http://langfuse:3000

    # 1. Check if Langfuse is reachable
    try:
        resp = urllib.request.urlopen(f"{internal_host}/api/public/health", timeout=5)
        health = json.loads(resp.read())
        if health.get("status") != "OK":
            logger.warning("Langfuse health check failed")
            return None
    except Exception:
        logger.info("Langfuse not reachable at %s — skipping seed", internal_host)
        return None

    # 2. Try to create user (idempotent — 200 if new, error if exists)
    try:
        signup_data = json.dumps({
            "name": "SRE Admin",
            "email": LANGFUSE_EMAIL,
            "password": LANGFUSE_PASSWORD,
        }).encode()
        req = urllib.request.Request(
            f"{internal_host}/api/auth/signup",
            data=signup_data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req)
        logger.info("Langfuse user created: %s", LANGFUSE_EMAIL)
    except urllib.error.HTTPError:
        logger.debug("Langfuse user already exists")
    except Exception:
        logger.warning("Langfuse signup failed", exc_info=True)
        return None

    # 3. Sign in to get session
    try:
        # CSRF token
        resp = urllib.request.urlopen(f"{internal_host}/api/auth/csrf")
        csrf = json.loads(resp.read())["csrfToken"]
        cookies = resp.headers.get_all("Set-Cookie") or []
        cookie_jar = "; ".join(c.split(";")[0] for c in cookies)

        # Credentials login
        login_data = urllib.parse.urlencode({
            "csrfToken": csrf,
            "email": LANGFUSE_EMAIL,
            "password": LANGFUSE_PASSWORD,
            "json": "true",
        }).encode()
        req = urllib.request.Request(
            f"{internal_host}/api/auth/callback/credentials",
            data=login_data,
            headers={"Cookie": cookie_jar, "Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urllib.request.urlopen(req)
        new_cookies = resp.headers.get_all("Set-Cookie") or []
        session_cookie = "; ".join(c.split(";")[0] for c in new_cookies)
    except Exception:
        logger.warning("Langfuse sign-in failed", exc_info=True)
        return None

    # 4. Check if project already exists (list projects via trpc)
    projects = []
    try:
        req = urllib.request.Request(
            f"{internal_host}/api/trpc/projects.all?batch=1&input=%7B%220%22%3A%7B%22json%22%3Anull%7D%7D",
            headers={"Cookie": session_cookie},
        )
        resp = urllib.request.urlopen(req)
        projects_data = json.loads(resp.read())
        projects = projects_data[0]["result"]["data"]["json"]

        if projects:
            project_id = projects[0]["id"]
            logger.info("Langfuse project already exists: %s", project_id)

            # Check for existing API keys
            encoded = urllib.parse.quote(json.dumps({"0": {"json": {"projectId": project_id}}}))
            req = urllib.request.Request(
                f"{internal_host}/api/trpc/apiKeys.byProjectId?batch=1&input={encoded}",
                headers={"Cookie": session_cookie},
            )
            resp = urllib.request.urlopen(req)
            keys_data = json.loads(resp.read())
            existing_keys = keys_data[0]["result"]["data"]["json"]
            if existing_keys:
                logger.info("Langfuse API keys already exist — skipping")
                return None
    except Exception:
        logger.debug("Could not check existing projects", exc_info=True)

    # 5. Create project if needed
    project_id = None
    if not projects:
        try:
            payload = json.dumps({
                "0": {"json": {"name": LANGFUSE_PROJECT_NAME}}
            }).encode()
            req = urllib.request.Request(
                f"{internal_host}/api/trpc/projects.create?batch=1",
                data=payload,
                headers={"Cookie": session_cookie, "Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req)
            result = json.loads(resp.read())
            project_id = result[0]["result"]["data"]["json"]["id"]
            logger.info("Langfuse project created: %s", project_id)
        except Exception:
            logger.warning("Langfuse project creation failed", exc_info=True)
            return None
    else:
        project_id = projects[0]["id"]

    # 6. Create API keys
    try:
        payload = json.dumps({
            "0": {"json": {"projectId": project_id, "note": "auto-seeded-dev"}}
        }).encode()
        req = urllib.request.Request(
            f"{internal_host}/api/trpc/apiKeys.create?batch=1",
            data=payload,
            headers={"Cookie": session_cookie, "Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        key_data = result[0]["result"]["data"]["json"]
        public_key = key_data["publicKey"]
        secret_key = key_data["secretKey"]
        logger.info("Langfuse API keys created: pk=%s", public_key)
        return {"public_key": public_key, "secret_key": secret_key}
    except Exception:
        logger.warning("Langfuse API key creation failed", exc_info=True)
        return None
