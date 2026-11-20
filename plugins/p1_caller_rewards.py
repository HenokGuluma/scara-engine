"""Ground #1 — Unclaimed incentive functions.

Finds recently verified contracts on less-watched chains that expose public,
no-argument upkeep functions (harvest, poke, settle...). Each one is simulated
with eth_call from a random address: if it doesn't revert, anyone may call it.
Reward-revealing view functions are read and gas cost is estimated, so the
report shows whether calling it would likely pay more than it costs.
"""
import time

from core import store
from plugins import evm
from plugins.base import Plugin


class CallerRewards(Plugin):
    key, ground, name, pursuit = "p1", 1, "Unclaimed incentive functions", "auto (after search-only phase)"

    def run(self):
        fn_names = set(self.cfg["caller_reward_functions"])
        view_names = set(self.cfg["caller_reward_views"])
        seen = set(store.kv_get(self.con, "p1_seen", []))
        chains = self.cfg["chains"]
        per_chain = max(10, self.time_left() / max(1, len(chains)))
        for chain in chains:
            chain_stop = min(self.deadline, time.time() + per_chain)
            try:
                found = evm.recent_verified(chain)
            except Exception as e:  # noqa: BLE001
                self.notes.append(f"{chain['name']}: explorer unavailable ({type(e).__name__})")
                continue
            fresh = [c for c in found if f"{chain['name']}:{c['address']}" not in seen]
            evm.remember_contracts(self.con, chain["name"], [c["address"] for c in fresh])
            for c in fresh:
                if self.out_of_time() or time.time() > chain_stop:
                    break
                seen.add(f"{chain['name']}:{c['address']}")
                try:
                    self._probe(chain, c, fn_names, view_names)
                except Exception as e:  # noqa: BLE001
                    self.notes.append(f"{chain['name']} {c['address'][:10]}: {type(e).__name__}")
        store.kv_set(self.con, "p1_seen", list(seen)[-20000:])

    def _probe(self, chain, c, fn_names, view_names):
        detail = evm.contract_detail(chain, c["address"])
        abi = detail.get("abi") or []
        upkeep = [f for f in abi if f.get("type") == "function" and f.get("name") in fn_names
                  and not f.get("inputs") and f.get("stateMutability") in ("nonpayable", None)]
        if not upkeep:
            return
        views = [f for f in abi if f.get("type") == "function" and f.get("name") in view_names
                 and not f.get("inputs") and f.get("stateMutability") in ("view", "pure")
                 and len(f.get("outputs") or []) == 1 and (f["outputs"][0].get("type") or "").startswith("uint")]
        caller = evm.random_caller()
        callable_fns = []
        for f in upkeep:
            data = evm.selector(f["name"] + "()")
            try:
                evm.eth_call(chain, c["address"], data, caller)
                try:
                    gas = evm.estimate_gas(chain, c["address"], data, caller)
                except Exception:  # noqa: BLE001
                    gas = 250_000
                callable_fns.append((f["name"], gas))
            except Exception:  # noqa: BLE001 — reverted: not callable by strangers right now
                continue
        if not callable_fns:
            return
        hints = {}
        for v in views:
            try:
                raw = evm.eth_call(chain, c["address"], evm.selector(v["name"] + "()"))
                hints[v["name"]] = int(raw, 16) if raw and raw != "0x" else 0
            except Exception:  # noqa: BLE001
                pass
        gp = evm.gas_price(chain)
        usd = chain.get("native_usd_hint", 0)
        best_gas = min(g for _, g in callable_fns)
        cost_usd = best_gas * gp / 1e18 * usd
        # Crude value guess: largest reward hint read as an 18-decimals amount of
        # the native coin. Flagged as an estimate; verification happens later.
        raw_best = max(hints.values(), default=0)
        value_usd = min(raw_best / 1e18 * usd, 250_000) if raw_best else 0.0
        txs = evm.tx_count(chain, c["address"])
        awareness = min(1.0, txs / 5000)
        names = ", ".join(n for n, _ in callable_fns)
        self.emit(
            uid=f"{chain['name']}:{c['address']}",
            title=f"{c.get('name') or 'Contract'} on {chain['name']}: anyone can call {names}()",
            summary=(f"Public upkeep function(s) {names} succeed in simulation from a random address. "
                     f"Est. gas cost ≈ ${cost_usd:.4f}. Reward hints: "
                     f"{', '.join(f'{k}={v}' for k, v in hints.items()) or 'none found (check events/transfers)'}. "
                     f"Lifetime transactions: {txs}. Next step: trace a simulated call to confirm "
                     f"the caller actually receives tokens."),
            url=f"{chain['explorer'].rstrip('/')}/address/{c['address']}",
            value_usd=value_usd, cost_usd=cost_usd,
            claimability=0.5 if hints else 0.25, awareness=awareness,
            status="simulated" if hints else "needs_review",
            data={"chain": chain["name"], "address": c["address"], "functions": callable_fns, "hints": hints})
