"""Idea Forge — daily generator of unconventional income approaches.

  python forge_run.py run      generate, evaluate, pick the best, send the PDF
  python forge_run.py check    check setup and send a Telegram test message
  python forge_run.py demo     offline dry-run with a fake LLM → sample PDF
"""
import datetime as dt
import os
import random
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import notify, store  # noqa: E402
from core.llm import LLM  # noqa: E402
from forge import pdf, signals  # noqa: E402
from forge.pipeline import Forge  # noqa: E402

ROOT = Path(__file__).resolve().parent
RUN_MINUTES = 55

SCHEMA = """CREATE TABLE IF NOT EXISTS ideas (id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT, name TEXT,
 one_liner TEXT, op TEXT, quick REAL, final REAL, winner INTEGER, data TEXT);
 CREATE INDEX IF NOT EXISTS ideas_day ON ideas(day);"""


def cfg():
    return yaml.safe_load((ROOT / "forge_config.yaml").read_text())


def open_db():
    store.configure("forge")
    con = store.load()
    con.executescript(SCHEMA)
    return con


def run(llm_override=None, sample=False):
    c = cfg()
    con = open_db()
    llm = llm_override or LLM(con, c["llm_providers"])
    if not llm.available:
        notify.ping("⚠️ Idea Forge: no LLM key found. Add GEMINI_API_KEY or GROQ_API_KEY.")
        raise SystemExit("No LLM providers configured.")
    sig, sig_err = ([], []) if sample else signals.fetch(c.get("signal_feeds") or [])
    print(f"[forge] {len(sig)} headlines; providers: {len(getattr(llm, 'providers', []))}")
    forge = Forge(con, llm, c, sig, deadline=time.time() + (20 if sample else RUN_MINUTES * 60))
    winner, rep = forge.run()
    forge.stats["llm_calls"] = llm.calls
    # Public logs: counts only.
    print("[forge] stats:", {k: v for k, v in forge.stats.items() if k != "ops"})
    if not rep:
        notify.ping("Idea Forge: today's run produced no usable ideas (LLM quotas or errors). "
                    "It will try again tomorrow.")
        store.save(con)
        return
    out = ROOT / "work" / f"IdeaForge_{dt.date.today():%Y-%m-%d}{'_SAMPLE' if sample else ''}.pdf"
    out.parent.mkdir(exist_ok=True)
    pdf.build(str(out), rep, winner, forge.stats, sample=sample)
    if not sample:
        store.save(con)
        notify.send(str(out), f"💡 Idea Forge — {dt.date.today():%d %b}\n{rep.get('title')}\n"
                              f"Worth pursuing? {rep.get('verdict')}\n"
                              f"({forge.stats['generated']} approaches explored today)")
    print("[forge] report:", out.name)
    return out


def check():
    c = cfg()
    have = [p["key_env"] for p in c["llm_providers"] if os.environ.get(p["key_env"])]
    print("LLM keys found:", ", ".join(have) or "NONE")
    print("State passphrase:", "set" if os.environ.get("STATE_PASSPHRASE") else "MISSING")
    ok = notify.ping("✅ Idea Forge is connected. Your daily idea report will arrive here every morning.")
    print("Telegram test:", "sent" if ok else "not sent (check TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")


# ── Offline demo with a fake LLM (tests the whole pipeline, no network) ──
class FakeLLM:
    available, providers = True, ["fake"]

    def __init__(self):
        self.calls = 0

    def ask_json(self, prompt, **kw):
        self.calls += 1
        import re
        if "Produce" in prompt and "approaches" in prompt:
            base = random.choice(["testnet", "settlement", "rebate", "expiry", "oracle", "launch", "grant",
                                  "odd-lot", "refund", "dataset", "points", "auction"])
            return {"ideas": [{"name": f"{base.title()} idea {random.randint(1000, 9999)} {w}",
                               "one_liner": f"Automated watcher for {base} windows variant {w} {random.random():.5f}",
                               "system": "x", "gap": "y", "mechanism": "z", "why_now": "now", "automation": "bot",
                               "start_capital_usd": random.choice([0, 20, 100, 900]),
                               "human_contact": random.choice(["none", "low", "high"]),
                               "legal_risk": random.choice(["low", "low", "medium", "high"])}
                              for w in range(8)]}
        if "Score each idea" in prompt:
            n = len(re.findall(r"^\[\d+\]", prompt, flags=re.M))
            return {"scores": [{"i": i, **{c: random.randint(2, 8) for c in
                                           ["no_edge_needed", "low_contact", "automatable", "low_capital", "timing",
                                            "upside", "durability", "plausibility", "novelty"]}} for i in range(n)]}
        if "Review this idea as a panel" in prompt:
            return {"skeptic": "Programs increasingly filter out low-effort participants, and rewards per "
                               "wallet may be tiny or paid in tokens that fall in price right after launch.",
                    "already_exploited": random.randint(3, 8), "legal": "Legal if you use one genuine wallet "
                    "and follow each program's rules.", "legal_risk": "low",
                    "engineer": "GitHub Actions job reads announcements daily; LLM extracts tasks; script performs "
                                "on-chain tasks from one wallet; Telegram reports.",
                    "economics": {"start_capital_usd": 30, "monthly_at_small_scale_usd": None, "capacity_usd": 5000,
                                  "compounding": "Reinvest rewards into gas for more programs."},
                    "cheapest_test": "Track 5 past programs: would the bot have qualified, and what did one wallet earn?",
                    "kill_criteria": "If backtest shows < $50 per program after gas.",
                    "revised": {c: random.randint(3, 8) for c in ["no_edge_needed", "low_contact", "automatable",
                                                                    "low_capital", "timing", "upside", "durability",
                                                                    "plausibility", "novelty"]},
                    "verdict": "test_first",
                    "verdict_reason": "Real but shrinking; worth a cheap backtest.", "search_keywords": "testnet rewards"}
        if "Which idea is the better bet" in prompt:
            return {"winner": random.choice("AB"), "why": "More plausible."}
        if "Write the daily report" in prompt:
            return SAMPLE_WRITEUP
        if "ONE plain sentence" in prompt:
            return {"items": [{"i": i, "name": n, "sentence": s} for i, (n, s) in enumerate(SAMPLE_MENTIONS)]}
        return None


SAMPLE_WRITEUP = {
    "title": "Incentivised-testnet early-entry radar",
    "idea_simple": "New blockchains often pay early testers to try their network before launch. A bot watches "
                   "for these programs the day they open, joins with one wallet, does the required tasks "
                   "automatically, and collects the rewards later.",
    "worth_statement": "Worth a cheap test: rewards have been real in the past and no skill or selling is needed, "
                       "but payouts are uncertain and programs now filter out low-effort participants.",
    "how_it_works": ["Watch announcement feeds for new incentivised testnets and points programs.",
                     "An LLM reads each program's rules and extracts the tasks and deadlines.",
                     "A script performs the on-chain tasks from your single wallet on a schedule.",
                     "When rewards are distributed, ground #3 of SCARA detects and reports them."],
    "automation_plan": ["GitHub Actions job runs every 6 hours to fetch feeds.",
                        "Free LLM (Cerebras/Groq) extracts tasks into a checklist.",
                        "Python script with a testnet wallet executes tasks; faucets fund gas.",
                        "Telegram bot reports progress and new programs."],
    "limitations": ["Rewards are not guaranteed and are often paid in tokens that drop after launch.",
                    "Using many wallets ('sybil farming') breaks program rules — one wallet only.",
                    "Some programs require social tasks (posts, Discord) that need human input.",
                    "Popular programs get crowded, shrinking the reward per participant."],
    "technical": {"tools": ["Python", "web3.py", "GitHub Actions", "Telegram bot"],
                  "data_sources": ["Project blogs", "Governance forums", "Testnet explorers"],
                  "free_resources": ["Public testnet faucets", "Free RPC endpoints", "Free LLM tiers"],
                  "start_capital": "$0–30 (mainnet gas only for some programs)",
                  "time_to_first_result": "Weeks to months (rewards arrive at token launch)",
                  "cheapest_test": "Backtest 5 finished programs: would the bot have qualified, and what did a "
                                   "single wallet earn?",
                  "kill_criteria": "Average payout per program under $50, or most programs require social tasks."},
}
SAMPLE_MENTIONS = [(n, x) for n, x in zip([
    "Low-uptake rebate radar", "Already-resolved market spotter", "Odd-lot tender tracker",
    "Wind-down redemption watcher", "Forgotten staking-reward sweeper", "Open-data release front-runner"], [
    "Watches expiring government rebate programs with low uptake and alerts you to ones you qualify for; catch: most are country-specific.",
    "Flags prediction-market questions whose answer is already public in official data; catch: small amounts per market.",
    "Tracks tender offers with odd-lot priority for under-100-share holders; catch: needs a brokerage account.",
    "Monitors protocols winding down where token holders can redeem treasury value above market price; catch: rare.",
    "Collects small unclaimed staking rewards left in deprecated contracts you once used; catch: only works for your own history.",
    "Alerts when open-data feeds publish before markets react; catch: professionals often already watch the big ones.",
])]


def demo():
    os.environ.pop("STATE_PASSPHRASE", None)
    store.configure("forge_demo")
    if store.DB_PATH.exists():
        store.DB_PATH.unlink()
    c_orig = cfg

    def small_cfg():
        c = c_orig()
        c["generation_calls"] = 30
        return c
    globals()["cfg"] = small_cfg
    globals()["open_db"] = lambda: (lambda con: (con.executescript(SCHEMA), con)[1])(store.load())
    return run(llm_override=FakeLLM(), sample=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": run, "check": check, "demo": demo}.get(cmd, lambda: print(__doc__))()
