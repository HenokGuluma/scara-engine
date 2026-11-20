"""SCARA Opportunity Engine — entry point.

  python run.py scan              run all seven hunting grounds once
  python run.py report daily      build + deliver the daily PDF
  python run.py report weekly     build + deliver the weekly PDF
  python run.py check             check your setup and send a test message
  python run.py demo              build a sample PDF with made-up data (no network)
"""
import datetime as dt
import os
import sys
import time
import traceback
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import notify, report, store  # noqa: E402
from core.llm import LLM  # noqa: E402
from core.scoring import allocate  # noqa: E402
from plugins import ALL  # noqa: E402

ROOT = Path(__file__).resolve().parent
ALERT_SCORE = 50  # instant Telegram ping when a NEW finding scores at least this


def cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def meta():
    return [{"key": p.key, "ground": p.ground, "name": p.name, "pursuit": p.pursuit} for p in ALL]


def scan():
    c = cfg()
    con = store.load()
    llm = LLM(con, c["llm_providers"])
    stats = store.kv_get(con, "bandit", {})
    budgets = allocate(stats, [p.key for p in ALL], c.get("scan_budget_minutes", 40) * 60)
    print(f"[scan] LLM providers available: {len(llm.providers)}")
    alerts = []
    for P in ALL:
        t0 = time.time()
        plugin = P(con, llm, c, budgets[P.key])
        err = ""
        try:
            plugin.run()
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:200]}"
            traceback.print_exc(limit=1)
        if plugin.notes and not err:
            err = "; ".join(plugin.notes)[:400]
        secs = time.time() - t0
        con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (time.time(), P.key, secs, plugin.items, plugin.hits, err))
        s = stats.setdefault(P.key, {"runs": 0, "hits": 0})
        s["runs"] += 1
        s["hits"] += 1 if plugin.hits else 0
        # Decay old evidence so the allocator keeps adapting.
        if s["runs"] > 60:
            s["runs"], s["hits"] = int(s["runs"] * 0.8), int(s["hits"] * 0.8)
        # Public logs show counts only — never findings.
        print(f"[scan] ground #{P.ground}: {secs:5.0f}s, {plugin.items} items, {plugin.new} new, {plugin.hits} hits")
        since = t0
        for r in con.execute("SELECT title, score FROM candidates WHERE plugin=? AND first_seen>=? AND score>=?",
                             (P.key, since, ALERT_SCORE)):
            alerts.append(f"#{P.ground} · score {r['score']:,.0f} · {r['title'][:120]}")
    store.kv_set(con, "bandit", stats)
    store.save(con)
    if alerts:
        notify.ping("🔔 SCARA: new high-score findings\n\n" + "\n".join(alerts[:8]) +
                    "\n\nFull details arrive in the next PDF report.")


def make_report(period):
    con = store.load()
    out = ROOT / "work" / f"SCARA_{period}_{dt.date.today():%Y-%m-%d}.pdf"
    out.parent.mkdir(exist_ok=True)
    r = report.build(con, meta(), str(out), period=period)
    store.save(con)
    caption = (f"SCARA {period} report — {dt.date.today():%d %b %Y}\n"
               f"{r['new']} new findings · {r['top']} worth a look · {r['errors']} run errors")
    notify.send(str(out), caption)


def check():
    c = cfg()
    print("Setup check\n-----------")
    keys = [p["key_env"] for p in c["llm_providers"]]
    have = [k for k in keys if os.environ.get(k)]
    print(f"LLM keys found: {', '.join(have) or 'NONE — add at least one (GROQ_API_KEY recommended)'}")
    print("State passphrase:", "set" if os.environ.get("STATE_PASSPHRASE") else "MISSING — add STATE_PASSPHRASE")
    tg = os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID")
    em = os.environ.get("EMAIL_USER") and os.environ.get("EMAIL_APP_PASSWORD")
    print("Delivery:", ", ".join(x for x, ok in (("Telegram", tg), ("Email", em)) if ok) or "NONE — add Telegram or email secrets")
    print("Wallets for ground #3:", len(c.get("my_wallets") or []))
    if tg:
        print("Telegram test message:", "sent" if notify.ping("✅ SCARA is connected. Reports will arrive here.") else "FAILED")


def demo():
    """Sample report with made-up findings so you can see the format."""
    os.environ.pop("STATE_PASSPHRASE", None)
    store.DB_PATH = ROOT / "work" / "demo.db"
    if store.DB_PATH.exists():
        store.DB_PATH.unlink()
    con = store.load()
    from plugins.base import Plugin
    samples = [
        ("p3", "Unclaimed ARB rewards on Arbitrum: ≈ $212.40", "Wallet 0x3fa1… has 401.2 ARB claimable via Merkl.",
         212.4, 0.5, 0.95, 0.0, "verified", False),
        ("p1", "FeeVault on gnosis: anyone can call harvest()", "Public upkeep function harvest succeeds in simulation "
         "from a random address. Est. gas cost ≈ $0.0021. Reward hints: callerReward=38200000000000000000. "
         "Lifetime transactions: 41.", 38.2, 0.002, 0.5, 0.01, "simulated", False),
        ("p2", "ExampleDAO: liquid treasury is 1.34× its market cap", "Liquid treasury ≈ $8,410,000 vs market cap "
         "≈ $6,270,000. Next step: check whether holders can redeem against the treasury.", 170, 0, 0.2, 0.6,
         "needs_review", False),
        ("p4", "[ExampleSwap] Liquidity incentives for the new stable pool", "Distributes 2M tokens (≈ $400k) to LPs "
         "of the new pool over 8 weeks. Who: anyone providing liquidity. Status: closed.", 400, 0, 0.5, 0.08,
         "needs_review", False),
        ("p6", "Federal Register: Example rule on tender-offer odd lots", "Rule clarifies odd-lot priority in issuer "
         "tender offers; window for small holders.", 40, 0, 0.4, 0.5, "needs_review", False),
        ("p5", "Prize page changed: EFF Cooperative Computing Awards", "Page updated; prize for a 100M-digit prime "
         "still open.", 150, 0, 0.1, 0.7, "needs_review", False),
        ("p7", "PRIVATE · possible high issue in StakingPool (base)", "Initializer can be called by anyone after "
         "deployment, allowing ownership takeover. Value held ≈ $12,000. Route: disclose to the project.",
         720, 0, 0.3, 0.1, "disclosure_draft", True),
    ]
    by = {p.key: p for p in ALL}
    for i, (k, t, sm, v, cst, cl, aw, st, pv) in enumerate(samples):
        pl = by[k](con, None, {"min_score_for_top": 1.0}, 60)
        Plugin.emit(pl, uid=f"demo{i}", title=t, summary=sm, url="https://example.org", value_usd=v,
                    cost_usd=cst, claimability=cl, awareness=aw, status=st, private=pv,
                    deadline="2026-12-15" if k == "p4" else None,
                    data={"draft": "Hello team — while reviewing StakingPool we noticed initialize() is "
                                   "unguarded… (sample)"} if pv else {})
        con.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (time.time(), k, 300 + 60 * i, 40 + 10 * i, 1, ""))
    con.execute("INSERT INTO llm_usage VALUES (?,?,?)", (dt.date.today().isoformat(), "groq", 214))
    con.execute("INSERT INTO llm_usage VALUES (?,?,?)", (dt.date.today().isoformat(), "cerebras", 37))
    con.commit()
    out = ROOT / "work" / "SCARA_sample_report.pdf"
    report.build(con, meta(), str(out), period="daily", sample=True)
    print("Sample report:", out)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "scan":
        scan()
    elif cmd == "report":
        make_report(sys.argv[2] if len(sys.argv) > 2 else "daily")
    elif cmd == "check":
        check()
    elif cmd == "demo":
        demo()
    else:
        print(__doc__)
