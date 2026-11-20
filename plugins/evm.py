"""Shared EVM helpers: contract discovery via Blockscout, ABI/source fetch, eth_call."""
import random

from Crypto.Hash import keccak

from core import net, store


def selector(sig: str) -> str:
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return "0x" + k.hexdigest()[:8]


def random_caller():
    return "0x" + "".join(random.choice("0123456789abcdef") for _ in range(40))


def recent_verified(chain, pages=2):
    """Recently verified contracts on a Blockscout explorer (no key needed)."""
    out, params = [], {}
    for _ in range(pages):
        data = net.get_json(chain["explorer"].rstrip("/") + "/api/v2/smart-contracts", params=params)
        for it in data.get("items", []):
            addr = (it.get("address") or {}).get("hash") if isinstance(it.get("address"), dict) else it.get("address_hash")
            if addr:
                out.append({"address": addr, "name": it.get("name") or (it.get("address") or {}).get("name"),
                            "verified_at": it.get("verified_at"), "tx_count": it.get("transaction_count") or it.get("tx_count")})
        params = data.get("next_page_params") or None
        if not params:
            break
    return out


def contract_detail(chain, address):
    return net.get_json(chain["explorer"].rstrip("/") + f"/api/v2/smart-contracts/{address}")


def tx_count(chain, address):
    try:
        c = net.get_json(chain["explorer"].rstrip("/") + f"/api/v2/addresses/{address}/counters")
        return int(c.get("transactions_count") or 0)
    except Exception:  # noqa: BLE001
        return 0


def eth_call(chain, to, data, frm=None):
    return net.rpc(chain["rpc"], "eth_call", [{"from": frm or random_caller(), "to": to, "data": data}, "latest"])


def estimate_gas(chain, to, data, frm):
    return int(net.rpc(chain["rpc"], "eth_estimateGas", [{"from": frm, "to": to, "data": data}]), 16)


def gas_price(chain):
    return int(net.rpc(chain["rpc"], "eth_gasPrice", []), 16)


def balance(chain, address):
    return int(net.rpc(chain["rpc"], "eth_getBalance", [address, "latest"]), 16)


def remember_contracts(con, chain_name, addrs, keep=600):
    q = store.kv_get(con, "recent_contracts", [])
    q.extend([[chain_name, a] for a in addrs])
    store.kv_set(con, "recent_contracts", q[-keep:])
