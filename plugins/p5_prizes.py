"""Ground #5 — Open computational prizes.

Watches prize/bounty pages listed in config.yaml. When a page changes, an LLM
summarises what changed (new prize, prize claimed, rules changed), so you
learn about under-attacked prizes without checking pages yourself.
"""
import hashlib
import re

from core import net, store
from plugins.base import Plugin


def _text(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


class Prizes(Plugin):
    key, ground, name, pursuit = "p5", 5, "Open computational prizes", "auto compute; manual submission"

    def run(self):
        snaps = store.kv_get(self.con, "p5_snaps", {})
        for item in self.cfg.get("prize_watchlist") or []:
            if self.out_of_time():
                break
            try:
                txt = _text(net.get(item["url"]).text)[:20000]
            except Exception as e:  # noqa: BLE001
                self.notes.append(f"{item['name']}: {type(e).__name__}")
                continue
            h = hashlib.sha256(txt.encode()).hexdigest()
            prev = snaps.get(item["url"])
            snaps[item["url"]] = {"h": h, "txt": txt[:6000]}
            if not prev or prev["h"] == h:
                continue
            facts = (self.llm.ask_json(
                "Compare the OLD and NEW text of a prize/bounty page. Return JSON: "
                '{"meaningful_change": bool, "prize_usd": number|null, "still_open": bool|null, '
                '"what_changed": string}\n\nOLD:\n' + prev["txt"] + "\n\nNEW:\n" + txt[:6000])
                     if self.llm.available else {"meaningful_change": True, "what_changed": "Page content changed."}) or {}
            if not facts.get("meaningful_change"):
                continue
            self.emit(
                uid=f"prize:{item['url']}:{h[:12]}",
                title=f"Prize page changed: {item['name']}",
                summary=facts.get("what_changed", "Page changed."),
                url=item["url"], value_usd=float(facts.get("prize_usd") or 0) * 0.001,
                claimability=0.1 if facts.get("still_open") else 0.02, awareness=0.7)
        store.kv_set(self.con, "p5_snaps", snaps)
