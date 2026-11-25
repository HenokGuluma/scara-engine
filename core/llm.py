"""Free-tier LLM router.

Tries providers in the order listed in config.yaml, skips any without a key,
respects a per-provider daily call budget, and caches every answer so the same
question never costs quota twice. LLMs only extract and summarise — all numbers
and verdicts come from code.
"""
import datetime as dt
import hashlib
import json
import os
import re
import time

from . import net

_SYSTEM = ("You are a precise research extraction engine. Answer ONLY with valid JSON "
           "matching the requested schema. If information is missing, use null. Never invent numbers.")


class LLM:
    def __init__(self, con, providers):
        self.con = con
        self.providers = [p for p in providers if os.environ.get(p["key_env"])]
        self.calls = 0

    @property
    def available(self):
        return bool(self.providers)

    def _used(self, name):
        day = dt.date.today().isoformat()
        r = self.con.execute("SELECT calls FROM llm_usage WHERE day=? AND provider=?", (day, name)).fetchone()
        return r["calls"] if r else 0

    def _bump(self, name):
        day = dt.date.today().isoformat()
        self.con.execute(
            "INSERT INTO llm_usage VALUES (?,?,1) ON CONFLICT(day,provider) DO UPDATE SET calls=calls+1",
            (day, name))

    def ask_json(self, prompt: str, max_tokens=800, temperature=0.0, tier="fast", system=None, cache=None):
        """tier='smart' uses each provider's model_smart (if set). Answers are cached
        when temperature is 0 (deterministic questions) unless cache= says otherwise."""
        cache = (temperature == 0) if cache is None else cache
        h = hashlib.sha256(f"{tier}|{system}|{prompt}".encode()).hexdigest()
        if cache:
            hit = self.con.execute("SELECT out FROM llm_cache WHERE h=?", (h,)).fetchone()
            if hit:
                return json.loads(hit["out"])
        for p in self.providers:
            if self._used(p["name"]) >= p.get("daily_calls", 100):
                continue
            gap = p.get("min_interval_s", 0) - (time.time() - p.get("_last", 0))
            if gap > 0:
                time.sleep(gap)
            p["_last"] = time.time()
            model = p.get("model_smart", p["model"]) if tier == "smart" else p["model"]
            try:
                out = net.post_json(
                    p["base_url"].rstrip("/") + "/chat/completions",
                    {"model": model, "temperature": temperature, "max_tokens": max_tokens,
                     "messages": [{"role": "system", "content": system or _SYSTEM},
                                  {"role": "user", "content": prompt}], **p.get("extra", {})},
                    headers={"Authorization": f"Bearer {os.environ[p['key_env']]}"},
                    timeout=60, tries=2)
                self._bump(p["name"])
                self.calls += 1
                text = out["choices"][0]["message"]["content"] or ""
                data = _parse_json(text)
                if data is not None and cache:
                    self.con.execute("INSERT OR REPLACE INTO llm_cache VALUES (?,?,?)",
                                     (h, json.dumps(data), time.time()))
                if data is not None:
                    return data
            except Exception as e:  # noqa: BLE001 — fall through to next provider
                print(f"[llm] {p['name']} failed: {type(e).__name__}")
                continue
        return None


def _parse_json(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        return None
    try:
        return json.loads(text[start:])
    except json.JSONDecodeError:
        end = max(text.rfind("}"), text.rfind("]"))
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
