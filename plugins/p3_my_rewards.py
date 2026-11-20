"""Ground #3 — Rewards you already qualify for.

Checks the public wallet addresses listed in config.yaml (my_wallets) against
Merkl, a large on-chain reward distributor used by many protocols, for
rewards that are earned but not yet claimed.
"""
from core import net
from plugins.base import Plugin

CHAIN_IDS = "1,10,56,100,137,8453,42161,59144,534352,81457"


class MyRewards(Plugin):
    key, ground, name, pursuit = "p3", 3, "Rewards you already qualify for", "auto (to your own wallets)"

    def run(self):
        wallets = self.cfg.get("my_wallets") or []
        if not wallets:
            self.notes.append("No wallets listed in config.yaml (my_wallets) — ground #3 idle.")
            return
        for w in wallets:
            if self.out_of_time():
                break
            try:
                data = net.get_json(f"https://api.merkl.xyz/v4/users/{w}/rewards", params={"chainId": CHAIN_IDS})
            except Exception as e:  # noqa: BLE001
                self.notes.append(f"Merkl {w[:8]}: {type(e).__name__}")
                continue
            for chain_block in data if isinstance(data, list) else []:
                chain = (chain_block.get("chain") or {}).get("name", "?")
                for r in chain_block.get("rewards") or []:
                    tok = r.get("token") or {}
                    dec = int(tok.get("decimals") or 18)
                    unclaimed = (int(r.get("amount") or 0) - int(r.get("claimed") or 0)) / 10 ** dec
                    usd = unclaimed * float(tok.get("price") or 0)
                    if usd < 1:
                        continue
                    self.emit(
                        uid=f"merkl:{w}:{chain}:{tok.get('address')}",
                        title=f"Unclaimed {tok.get('symbol', 'token')} rewards on {chain}: ≈ ${usd:,.2f}",
                        summary=f"Wallet {w[:8]}… has {unclaimed:,.4f} {tok.get('symbol')} claimable via Merkl.",
                        url="https://app.merkl.xyz/users/" + w,
                        value_usd=usd, cost_usd=0.5, claimability=0.95, awareness=0.0,
                        status="verified", data={"wallet": w, "chain": chain, "token": tok.get("symbol")})
