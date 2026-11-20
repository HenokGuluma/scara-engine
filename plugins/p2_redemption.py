"""Ground #2 — Assets trading below what they can be redeemed for.

A) Crypto: compares each DAO's liquid treasury (excluding its own token) with
   its market cap using free DefiLlama data. Treasury ≥ market cap suggests the
   token may be worth more than its price if holders can redeem or a wind-down
   happens.
B) Traditional: SEC EDGAR full-text search for issuer tender offers with an
   "odd lot" clause (holders of <100 shares are bought out first, in full).
"""
import datetime as dt
import re

from core import net, store
from plugins.base import Plugin


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\(?treasury\)?", "", (s or "").lower()))


class Redemption(Plugin):
    key, ground, name, pursuit = "p2", 2, "Assets below redeemable value", "auto with hard caps"

    def run(self):
        try:
            self._treasuries()
        except Exception as e:  # noqa: BLE001
            self.notes.append(f"DefiLlama: {type(e).__name__}")
        if not self.out_of_time():
            try:
                self._odd_lots()
            except Exception as e:  # noqa: BLE001
                self.notes.append(f"EDGAR: {type(e).__name__}")

    def _treasuries(self):
        treas = net.get_json("https://api.llama.fi/treasuries")
        protos = net.get_json("https://api.llama.fi/protocols")
        mcap_by = {}
        for p in protos:
            if p.get("mcap"):
                for k in (p.get("gecko_id"), _norm(p.get("name")), p.get("slug")):
                    if k:
                        mcap_by[k] = (p["mcap"], p.get("name"), p.get("slug"))
        for t in treas:
            total = t.get("tvl") or 0
            own = 0
            tb = t.get("tokenBreakdowns") or {}
            if isinstance(tb, dict):
                own = tb.get("ownTokens") or 0
            liquid = total - own
            if liquid < 250_000:
                continue
            m = mcap_by.get(t.get("gecko_id")) or mcap_by.get(_norm(t.get("name"))) or mcap_by.get(t.get("slug"))
            if not m:
                continue
            mcap, pname, slug = m
            ratio = liquid / mcap if mcap else 0
            if ratio < 0.8:
                continue
            upside = max(0.0, ratio - 1)
            self.emit(
                uid=f"treasury:{pname}",
                title=f"{pname}: liquid treasury is {ratio:.2f}× its market cap",
                summary=(f"Liquid treasury ≈ ${liquid:,.0f} (excluding own token ${own:,.0f}) vs market cap "
                         f"≈ ${mcap:,.0f}. Next step: check whether holders can redeem against the treasury, "
                         f"or whether a wind-down / buyback is proposed (ground #4 watches governance)."),
                url=f"https://defillama.com/protocol/{slug}" if slug else "https://defillama.com/treasuries",
                value_usd=500 * upside,  # gain on a nominal $500 position if it closed to treasury value
                claimability=0.2, awareness=0.6,
                data={"ratio": ratio, "liquid": liquid, "mcap": mcap})
            if self.out_of_time():
                return

    def _odd_lots(self):
        start = (dt.date.today() - dt.timedelta(days=21)).isoformat()
        q = net.get_json("https://efts.sec.gov/LATEST/search-index",
                         params={"q": '"odd lot"', "forms": "SC TO-I", "dateRange": "custom",
                                 "startdt": start, "enddt": dt.date.today().isoformat()})
        hits = (q.get("hits") or {}).get("hits") or []
        done = set(store.kv_get(self.con, "p2_oddlot_seen", []))
        for h in hits[:25]:
            src = h.get("_source") or {}
            adsh = (h.get("_id") or "").split(":")[0]
            if not adsh or adsh in done:
                continue
            done.add(adsh)
            name = (src.get("display_names") or ["Unknown issuer"])[0]
            cik = (src.get("ciks") or [""])[0].lstrip("0")
            fname = (h.get("_id") or ":").split(":")[1]
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fname}"
            facts = None
            if self.llm.available and not self.out_of_time(20):
                try:
                    text = re.sub(r"<[^>]+>", " ", net.get(url).text)
                    text = re.sub(r"\s+", " ", text)[:14000]
                    facts = self.llm.ask_json(
                        "From this SEC tender-offer filing, extract JSON: "
                        '{"offer_price_low": number|null, "offer_price_high": number|null, '
                        '"expiration_date": "YYYY-MM-DD"|null, "has_odd_lot_priority": bool, '
                        '"ticker": string|null, "one_line": string}.\n\n' + text)
                except Exception:  # noqa: BLE001
                    facts = None
            facts = facts or {}
            self.emit(
                uid=f"oddlot:{adsh}",
                title=f"Tender offer with odd-lot clause: {name}",
                summary=(facts.get("one_line") or "Issuer tender offer mentioning odd-lot priority.") +
                        (f" Offer range ${facts.get('offer_price_low')}–${facts.get('offer_price_high')}."
                         if facts.get("offer_price_low") else "") +
                        " Next step: compare offer price with market price; holders of <100 shares are "
                        "usually bought first and in full.",
                url=url, value_usd=0, claimability=0.6 if facts.get("has_odd_lot_priority") else 0.3,
                awareness=0.4, deadline=facts.get("expiration_date"), data=facts)
        store.kv_set(self.con, "p2_oddlot_seen", list(done)[-2000:])
