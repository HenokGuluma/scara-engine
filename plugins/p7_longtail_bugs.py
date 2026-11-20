"""Ground #7 — Bugs in long-tail contracts (DISCLOSURE ONLY).

Scans the source of newly verified contracts (discovered by ground #1) for
risky patterns, has an LLM triage the worst ones, and drafts a private
disclosure note. Findings are marked PRIVATE: they appear only in the PDF sent
to you, never in public logs. This plugin has no wallet access and never acts.
"""
import re

from core import store
from plugins import evm
from plugins.base import Plugin

PATTERNS = [
    ("tx.origin used for authorisation", r"require\s*\(\s*tx\.origin\s*==", 3),
    ("delegatecall to a variable target", r"\.delegatecall\s*\(", 2),
    ("selfdestruct present", r"\bselfdestruct\s*\(", 2),
    ("unchecked low-level call", r"\.call\{?[^;]*\)\s*;(?!\s*require)", 1),
    ("public initializer without guard", r"function\s+initiali[sz]e\s*\([^)]*\)\s*(public|external)(?![^{]*initializer)", 3),
    ("transferFrom with caller-supplied 'from'", r"transferFrom\s*\(\s*(from|_from|sender|owner)\b", 1),
    ("unprotected sensitive function",
     r"function\s+(set\w*|withdraw\w*|mint\w*|setOwner|upgradeTo\w*)\s*\([^)]*\)\s*(public|external)"
     r"(?![^{]*\b(only\w+|auth|whenNotPaused|requiresAuth)\b)[^{]*\{(?![^}]*(msg\.sender|_checkOwner|_checkRole|hasRole))", 3),
]


class LongTailBugs(Plugin):
    key, ground, name, pursuit = "p7", 7, "Bugs in long-tail contracts", "never — disclosure only"

    def run(self):
        queue = store.kv_get(self.con, "recent_contracts", [])
        done = set(store.kv_get(self.con, "p7_done", []))
        chains = {c["name"]: c for c in self.cfg["chains"]}
        todo = [q for q in queue if f"{q[0]}:{q[1]}" not in done and q[0] in chains]
        for chain_name, addr in todo:
            if self.out_of_time(20):
                break
            done.add(f"{chain_name}:{addr}")
            chain = chains[chain_name]
            try:
                d = evm.contract_detail(chain, addr)
            except Exception:  # noqa: BLE001
                continue
            src = d.get("source_code") or ""
            for extra in d.get("additional_sources") or []:
                src += "\n" + (extra.get("source_code") or "")
            if not src or len(src) > 400_000:
                continue
            flags = [(label, w) for label, rx, w in PATTERNS if re.search(rx, src, flags=re.S)]
            weight = sum(w for _, w in flags)
            if weight < 3:
                continue
            try:
                bal = evm.balance(chain, addr) / 1e18 * chain.get("native_usd_hint", 0)
            except Exception:  # noqa: BLE001
                bal = 0
            triage = {}
            if self.llm.available:
                triage = self.llm.ask_json(
                    "You are a smart-contract security reviewer. Static scan flags: "
                    f"{[f for f, _ in flags]}. Review the code and return JSON: "
                    '{"likely_real": bool, "severity": "critical|high|medium|low|none", '
                    '"explanation": string, "disclosure_draft": string}. Be sceptical: most flags are '
                    "false positives. The draft must be a responsible-disclosure note to the project.\n\n"
                    + src[:24000], max_tokens=1200) or {}
                if triage and not triage.get("likely_real"):
                    continue
            sev = (triage.get("severity") or "unknown").lower()
            sev_w = {"critical": 1.0, "high": 0.6, "medium": 0.25, "low": 0.05}.get(sev, 0.1)
            self.emit(
                uid=f"bug:{chain_name}:{addr}",
                title=f"PRIVATE · possible {sev} issue in {d.get('name') or addr[:10]} ({chain_name})",
                summary=(triage.get("explanation") or "Static flags: " + ", ".join(f for f, _ in flags)) +
                        f" Value held by contract ≈ ${bal:,.0f}. Route: find the project's bug bounty or "
                        "security contact and disclose. Never interact with the contract.",
                url=f"{chain['explorer'].rstrip('/')}/address/{addr}",
                value_usd=min(bal * 0.1, 1_000_000) * sev_w, claimability=0.3, awareness=0.1,
                status="disclosure_draft" if triage else "needs_review", private=True,
                data={"flags": [f for f, _ in flags], "draft": triage.get("disclosure_draft")})
        store.kv_set(self.con, "p7_done", list(done)[-20000:])
