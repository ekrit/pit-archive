"""Shared HTTP session with sane defaults and light retry."""
import time

import requests

from . import config


def make_session(user_agent: str | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": user_agent or config.HTTP_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    )
    return session


def get_json(session: requests.Session, url: str, *, params: dict | None = None, retries: int = 3):
    """GET returning parsed JSON, or None on repeated failure. Never raises."""
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=config.REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                return resp.json()
            # 429/403 -> back off and retry
            if resp.status_code in (429, 403, 503):
                time.sleep(2 ** attempt)
                continue
            return None
        except (requests.RequestException, ValueError):
            time.sleep(2 ** attempt)
    return None
