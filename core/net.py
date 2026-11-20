"""Small HTTP helper: polite User-Agent, retries, timeouts, JSON-RPC."""
import time

import requests

UA = "SCARA-research-bot/1.0 (personal research; contact via GitHub)"
_s = requests.Session()
_s.headers["User-Agent"] = UA


def get(url, params=None, timeout=25, tries=3, headers=None):
    for i in range(tries):
        try:
            r = _s.get(url, params=params, timeout=timeout, headers=headers)
            if r.status_code == 429:
                time.sleep(3 * (i + 1))
                continue
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def get_json(url, **kw):
    return get(url, **kw).json()


def post_json(url, payload, timeout=25, tries=3, headers=None):
    for i in range(tries):
        try:
            r = _s.post(url, json=payload, timeout=timeout, headers=headers)
            if r.status_code == 429:
                time.sleep(3 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def rpc(url, method, params):
    out = post_json(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in out:
        raise RuntimeError(out["error"].get("message", "rpc error"))
    return out["result"]
