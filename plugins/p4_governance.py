"""Ground #4 — New incentive programs approved in DAO governance.

Pulls recent Snapshot proposals (free GraphQL API), keeps ones mentioning
rewards, incentives, distributions or wind-downs, and has an LLM extract
whether newly claimable value is being created, for whom, and when.
"""
import re
import time

from core import net, store
from plugins.base import Plugin

KEYWORDS = re.compile(r"incentiv|reward|airdrop|retroactive|liquidity mining|emission|points|"
                      r"distribut|wind[- ]?down|sunset|redemption|buyback|treasury return|refund|rebate",
                      re.I)

QUERY = """query($ts:Int!){proposals(first:100, skip:0, where:{created_gte:$ts},
 orderBy:"created", orderDirection:desc){id title body state end created link
 space{id name followersCount}}}"""


class Governance(Plugin):
    key, ground, name, pursuit = "p4", 4, "New incentive programs (governance)", "auto with hard caps"

    def run(self):
        since = int(store.kv_get(self.con, "p4_since", time.time() - 3 * 86400))
        try:
            res = net.post_json("https://hub.snapshot.org/graphql", {"query": QUERY, "variables": {"ts": since}})
        except Exception as e:  # noqa: BLE001
            self.notes.append(f"Snapshot: {type(e).__name__}")
            return
        props = ((res or {}).get("data") or {}).get("proposals") or []
        store.kv_set(self.con, "p4_since", int(time.time()) - 3600)
        relevant = [p for p in props if KEYWORDS.search((p.get("title") or "") + " " + (p.get("body") or "")[:3000])]
        for p in relevant:
            if self.out_of_time(15):
                break
            space = p.get("space") or {}
            followers = int(space.get("followersCount") or 0)
            facts = {}
            if self.llm.available:
                facts = self.llm.ask_json(
                    "Read this DAO governance proposal. Return JSON: "
                    '{"creates_claimable_value": bool, "kind": "incentive|airdrop|wind_down|redemption|buyback|grant|other", '
                    '"total_value_usd": number|null, "who_can_claim": string, "how_to_participate": string, '
                    '"starts": "YYYY-MM-DD"|null, "ends": "YYYY-MM-DD"|null, '
                    '"needs_human_interaction": bool, "one_line": string}\n\n'
                    f"Title: {p.get('title')}\n\n{(p.get('body') or '')[:9000]}") or {}
                if facts and not facts.get("creates_claimable_value"):
                    continue
            if facts.get("needs_human_interaction"):
                continue
            pool = float(facts.get("total_value_usd") or 0)
            # Assume a newcomer could capture ~0.1% of a pool; awareness from space size.
            self.emit(
                uid=f"snapshot:{p['id']}",
                title=f"[{space.get('name', '?')}] {p.get('title', '')}",
                summary=(facts.get("one_line") or "Proposal mentions incentives/distribution.") +
                        (f" Who: {facts.get('who_can_claim')}." if facts.get("who_can_claim") else "") +
                        (f" How: {facts.get('how_to_participate')}." if facts.get("how_to_participate") else "") +
                        f" Status: {p.get('state')}.",
                url=p.get("link") or f"https://snapshot.org/#/{space.get('id')}/proposal/{p['id']}",
                value_usd=pool * 0.001, claimability=0.5 if p.get("state") == "closed" else 0.3,
                awareness=min(1.0, followers / 50_000), deadline=facts.get("ends"),
                data={"space": space.get("id"), "kind": facts.get("kind"), "state": p.get("state")})
