"""The opportunity signature and the bandit that shares time between grounds."""
import random


def score(value_usd, cost_usd, claimability, awareness, claimants):
    """V × P(claim) / (claimants+1), boosted when few people seem to know.

    value_usd    estimated claimable value (0 if unknown)
    cost_usd     cost to claim (gas, fees)
    claimability 0..1 — how sure we are you're allowed and able to claim
    awareness    0..1 — 0 = nobody seems to know, 1 = widely known
    claimants    how many others are already claiming
    """
    net_value = max(0.0, (value_usd or 0) - (cost_usd or 0))
    return round(net_value * (claimability or 0) / ((claimants or 0) + 1) * (2 - (awareness or 0.5)), 2)


def allocate(stats: dict, plugins: list, total_seconds: float, floor=0.06):
    """Thompson sampling: grounds that produced hits recently get more time.

    stats: {plugin: {"runs": n, "hits": h}}. Every ground keeps a minimum share
    (floor) so nothing is ever starved completely.
    """
    draws = {}
    for p in plugins:
        s = stats.get(p, {"runs": 0, "hits": 0})
        draws[p] = random.betavariate(1 + s["hits"], 1 + max(0, s["runs"] - s["hits"]))
    tot = sum(draws.values()) or 1
    share = {p: floor + (1 - floor * len(plugins)) * d / tot for p, d in draws.items()}
    return {p: total_seconds * s for p, s in share.items()}
