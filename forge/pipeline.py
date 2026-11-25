"""Idea Forge pipeline: generate → filter → dedupe → quick screen → deep panel →
reality check → tournament → write-up.

Design principles
- Many cheap ideas, few expensive evaluations (funnel), so ~100 LLM calls/day
  can explore hundreds of approaches.
- Diversity is forced: every generation call gets a different random persona,
  operator and set of building blocks; a memory of past ideas blocks repeats.
- Scores come from structured sub-scores combined in code; the final pick comes
  from head-to-head comparisons, which LLMs judge far more reliably than
  absolute 1–10 scores.
- "No" is an allowed — and common — verdict. The best idea of the day is still
  reported even when it isn't worth pursuing.
"""
import datetime as dt
import json
import math
import os
import random
import re
import time

from core import net
from forge import lenses

GEN_SYSTEM = (
    "You are an idea-generation agent in a research sandbox. You explore unconventional, LEGITIMATE ways "
    "for one individual to earn money by being positioned at the right place at the right time inside a "
    "system — not by out-competing skilled people, selling, networking or building slow reputation. "
    "The person has at most $500, no network, no special skills, and can use free LLM APIs, free scheduled "
    "cloud jobs (GitHub Actions), scripts and a Telegram bot. HARD RULES: legal only; no deception, fraud, "
    "scams, fake reviews or accounts, impersonation, spam, market manipulation, unauthorised hacking or "
    "exploiting bugs (disclosure via bounties is fine), abusing other people's accounts, or harming anyone. "
    "Answer ONLY with JSON.")

JUDGE_SYSTEM = (
    "You are a rigorous, sceptical evaluation panel for unconventional income ideas. You reward specific, "
    "plausible, automatable ideas that need no competitive edge, skills, network or sales, and little capital. "
    "You penalise vagueness, crowded or well-known schemes, hidden skill/sales requirements, and anything "
    "illegal or deceptive. Calibrate hard: most ideas are mediocre. Answer ONLY with JSON.")

CLICHES = ("dropshipping, affiliate marketing, blogging/content creation, freelancing, print-on-demand stores, "
           "generic trading bots, generic crypto arbitrage, selling courses, social media influencing, "
           "reselling on eBay, generic SaaS, newsletters")

IDEA_SCHEMA = ('{"ideas": [{"name": "≤8 words", "one_liner": "≤30 words", "system": "which system", '
               '"gap": "the exact inefficiency", "mechanism": "how money is made, ≤40 words", '
               '"why_now": "≤25 words", "automation": "how it runs with free tools, ≤30 words", '
               '"start_capital_usd": number, "human_contact": "none|low|medium|high", '
               '"legal_risk": "low|medium|high"}]}')

CRITERIA = ["no_edge_needed", "low_contact", "automatable", "low_capital", "timing",
            "upside", "durability", "plausibility", "novelty"]
WEIGHTS = {"plausibility": 2.0, "upside": 1.5, "no_edge_needed": 1.2, "novelty": 1.2, "automatable": 1.0,
           "low_contact": 1.0, "timing": 0.8, "low_capital": 0.8, "durability": 0.7}

STOP = set("a an the and or of to for in on with by from via using into your their its is are be as at "
           "that this these those it new free daily auto automated bot".split())


def weighted(sc: dict) -> float:
    if not sc:
        return 0.0
    tot = sum(WEIGHTS.values())
    v = sum(WEIGHTS[k] * float(sc.get(k) or 0) for k in WEIGHTS) / tot
    if float(sc.get("plausibility") or 0) < 3:
        v *= 0.5
    return round(v, 2)


def tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in STOP and len(w) > 2}


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))


class Forge:
    def __init__(self, con, llm, cfg, signals, deadline):
        self.con, self.llm, self.cfg, self.signals = con, llm, cfg, signals
        self.deadline = deadline
        self.stats = {"generated": 0, "after_filters": 0, "unique": 0, "screened": 0, "deep": 0,
                      "tournament": 0, "ops": {}, "signals": len(signals)}

    def time_left(self):
        return self.deadline - time.time()

    # ── 1. Generate ────────────────────────────────────────────────
    def generate(self):
        n_calls = self.cfg.get("generation_calls", 40)
        k = self.cfg.get("ideas_per_call", 8)
        past = self._past_top(12)
        mix = (["combinator"] * 30 + ["wildcard"] * 15 + ["analogy"] * 15 + ["inversion"] * 10 +
               (["signal"] * 20 if self.signals else []) + (["evolve"] * 10 if past else []))
        ideas = []
        for i in range(n_calls):
            if self.time_left() < 0.55 * (self.deadline - self.start):
                break  # keep >half the time for evaluation
            op = random.choice(mix)
            persona, pdesc = random.choice(lenses.PERSONAS)
            blocks = ""
            if op == "combinator":
                blocks = ("Building blocks (use them as seeds, combine freely):\n"
                          f"- Systems: {'; '.join(random.sample(lenses.SYSTEMS, 3))}\n"
                          f"- Gaps: {'; '.join(random.sample(lenses.GAPS, 2))}\n"
                          f"- Triggers: {'; '.join(random.sample(lenses.TRIGGERS, 2))}\n"
                          f"- Automation: {'; '.join(random.sample(lenses.AUTOMATIONS, 2))}")
            elif op == "signal":
                blocks = "Today's real headlines:\n" + "\n".join(f"- {s}" for s in random.sample(
                    self.signals, min(8, len(self.signals))))
            elif op == "analogy":
                blocks = f"Historical gap: {random.choice(lenses.HISTORICAL_GAPS)}\n" \
                         f"Look for its structure in: {'; '.join(random.sample(lenses.SYSTEMS, 3))}"
            elif op == "inversion":
                blocks = f"Consider these systems: {'; '.join(random.sample(lenses.SYSTEMS, 3))}\n" \
                         f"and this gap type: {random.choice(lenses.GAPS)}"
            elif op == "evolve":
                blocks = "Previous strong ideas:\n" + "\n".join(
                    f"- {p['name']}: {p['one_liner']}" for p in random.sample(past, min(4, len(past))))
            else:
                blocks = f"Random sparks: {random.choice(lenses.SYSTEMS)} × {random.choice(lenses.GAPS)} × " \
                         f"{random.choice(lenses.TRIGGERS)}"
            prompt = (f"You are the {persona}: you {pdesc}.\nTask: {lenses.OPERATORS[op]}\n\n{blocks}\n\n"
                      f"Produce {k} distinct, SPECIFIC approaches. Name the kind of system, the exact gap and "
                      f"the money mechanism. Avoid clichés: {CLICHES}.\nReturn JSON: {IDEA_SCHEMA}")
            out = self.llm.ask_json(prompt, max_tokens=4000, temperature=1.1 if op == "wildcard" else 1.0,
                                    system=GEN_SYSTEM)
            got = (out or {}).get("ideas") if isinstance(out, dict) else (out if isinstance(out, list) else None)
            for idea in got or []:
                if isinstance(idea, dict) and idea.get("name") and idea.get("one_liner"):
                    idea["op"], idea["persona"] = op, persona
                    ideas.append(idea)
            self.stats["ops"][op] = self.stats["ops"].get(op, 0) + 1
        self.stats["generated"] = len(ideas)
        return ideas

    # ── 2. Hard filters + dedupe against today and memory ─────────
    def filter_dedupe(self, ideas):
        cap = self.cfg.get("max_start_capital_usd", 500)
        bad_contact = set(self.cfg.get("drop_if_human_contact", ["high"]))
        bad_legal = set(self.cfg.get("drop_if_legal_risk", ["high"]))
        kept = []
        for i in ideas:
            try:
                capital = float(i.get("start_capital_usd") or 0)
            except (TypeError, ValueError):
                capital = 0
            if capital > cap or str(i.get("human_contact")).lower() in bad_contact \
                    or str(i.get("legal_risk")).lower() in bad_legal:
                continue
            kept.append(i)
        self.stats["after_filters"] = len(kept)
        since = (dt.date.today() - dt.timedelta(days=self.cfg.get("memory_days", 45))).isoformat()
        memory = [tokens(r["name"] + " " + r["one_liner"]) for r in
                  self.con.execute("SELECT name, one_liner FROM ideas WHERE day>=?", (since,))]
        unique, seen = [], []
        for i in kept:
            t = tokens(i["name"] + " " + i["one_liner"])
            if any(jaccard(t, m) >= 0.5 for m in memory) or any(jaccard(t, s) >= 0.5 for s in seen):
                continue
            seen.append(t)
            unique.append(i)
        self.stats["unique"] = len(unique)
        return unique

    # ── 3. Quick screen (batched, cheap) ──────────────────────────
    def quick_screen(self, ideas):
        for b in range(0, len(ideas), 15):
            if self.time_left() < 0.35 * (self.deadline - self.start):
                break
            batch = ideas[b:b + 15]
            listing = "\n".join(f"[{j}] {x['name']} — {x['one_liner']} | Mechanism: {x.get('mechanism', '')}"
                                for j, x in enumerate(batch))
            out = self.llm.ask_json(
                "Score each idea 0-10 on: " + ", ".join(CRITERIA) +
                ". (no_edge_needed: works without skills/network/advantage; low_contact: little human "
                "interaction; durability: how long before the gap closes; novelty: not widely known.) "
                "Most ideas deserve 2-5; 8+ is rare. Return JSON: "
                '{"scores": [{"i": int, ' + ", ".join(f'"{c}": int' for c in CRITERIA) + "}]}\n\n" + listing,
                max_tokens=2200, system=JUDGE_SYSTEM)
            for s in (out or {}).get("scores") or []:
                try:
                    idea = batch[int(s["i"])]
                except (KeyError, ValueError, IndexError, TypeError):
                    continue
                idea["quick_scores"] = {c: s.get(c) for c in CRITERIA}
                idea["quick"] = weighted(idea["quick_scores"])
                self.stats["screened"] += 1
        scored = [i for i in ideas if "quick" in i]
        scored.sort(key=lambda x: -x["quick"])
        return scored[: self.cfg.get("quick_screen_keep", 12)], scored

    # ── 4. Deep panel review ──────────────────────────────────────
    def deep_panel(self, finalists):
        for f in finalists:
            if self.time_left() < 0.12 * (self.deadline - self.start):
                break
            out = self.llm.ask_json(
                "Review this idea as a panel (Skeptic, Lawyer, Engineer, Economist, Judge) for a person with "
                "≤$500, no network, no special skills, using only free tools. Return JSON: "
                '{"skeptic": "strongest reasons it fails, ≤60 words", '
                '"already_exploited": 0-10 (10 = crowded/well known), '
                '"legal": "≤40 words", "legal_risk": "low|medium|high", '
                '"engineer": "how to automate it with free tools, ≤60 words", '
                '"economics": {"start_capital_usd": number, "monthly_at_small_scale_usd": number|null, '
                '"capacity_usd": number|null, "compounding": "how gains are reinvested, ≤30 words"}, '
                '"cheapest_test": "a ≤1-day, ≤$20 experiment that proves or disproves it", '
                '"kill_criteria": "≤30 words", '
                '"revised": {' + ", ".join(f'"{c}": int' for c in CRITERIA) + "}, "
                '"verdict": "pursue|test_first|no", "verdict_reason": "≤30 words", '
                '"search_keywords": "3-4 words to search for existing discussion"}\n\n'
                + json.dumps({k: f.get(k) for k in ("name", "one_liner", "system", "gap", "mechanism",
                                                     "why_now", "automation", "start_capital_usd")}),
                max_tokens=1800, tier="smart", system=JUDGE_SYSTEM)
            if not out:
                continue
            f["panel"] = out
            if str(out.get("legal_risk")).lower() == "high":
                f["dropped"] = "legal risk"
                continue
            f["attention"] = self.reality_check(out.get("search_keywords") or f["name"])
            rev = weighted(out.get("revised") or {})
            crowd = float(out.get("already_exploited") or 5)
            bonus = {"pursue": 1.0, "test_first": 0.3, "no": -1.0}.get(str(out.get("verdict")).lower(), 0)
            att = f["attention"]["level"]
            f["final"] = round(0.6 * rev + 0.4 * f["quick"] + bonus - 0.15 * crowd - 0.8 * att, 2)
            self.stats["deep"] += 1
        return sorted([f for f in finalists if "final" in f], key=lambda x: -x["final"])

    # ── 5. Reality check: how much public attention already exists? ─
    def reality_check(self, keywords):
        q = " ".join(list(tokens(keywords))[:4]) or keywords
        hn = gh = None
        try:
            hn = net.get_json("https://hn.algolia.com/api/v1/search",
                              params={"query": q, "tags": "story"}, timeout=15, tries=2).get("nbHits")
        except Exception:  # noqa: BLE001
            pass
        try:
            hdr = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else None
            gh = net.get_json("https://api.github.com/search/repositories", params={"q": q},
                              timeout=15, tries=2, headers=hdr).get("total_count")
        except Exception:  # noqa: BLE001
            pass
        known = [math.log10(1 + x) / 4 for x in (hn, gh) if x is not None]
        level = min(1.0, sum(known) / len(known)) if known else 0.5
        return {"query": q, "hn_stories": hn, "github_repos": gh, "level": round(level, 2)}

    # ── 6. Tournament (head-to-head) ──────────────────────────────
    def tournament(self, ranked):
        n = self.cfg.get("tournament_size", 4)
        pool = ranked[:n]
        self.stats["tournament"] = len(pool)
        for p in pool:
            p["wins"], p["matches"] = 0, 0
        for a in range(len(pool)):
            for b in range(a + 1, len(pool)):
                if self.time_left() < 60:
                    break
                x, y = (pool[a], pool[b]) if random.random() < 0.5 else (pool[b], pool[a])
                out = self.llm.ask_json(
                    "Which idea is the better bet for one person with ≤$500, no network, no special skills, "
                    "using free automation? Judge plausibility first, then upside, then automation and timing. "
                    'Return JSON: {"winner": "A" or "B", "why": "≤25 words"}\n\n'
                    f"A: {x['name']} — {x['one_liner']} | Skeptic: {x['panel'].get('skeptic', '')}\n"
                    f"B: {y['name']} — {y['one_liner']} | Skeptic: {y['panel'].get('skeptic', '')}",
                    max_tokens=400, tier="smart", system=JUDGE_SYSTEM)
                w = str((out or {}).get("winner", "")).strip().upper()[:1]
                x["matches"] += 1
                y["matches"] += 1
                if w == "A":
                    x["wins"] += 1
                elif w == "B":
                    y["wins"] += 1
        pool.sort(key=lambda p: (-p["wins"], -p["final"]))
        return pool + ranked[n:]

    # ── 7. Write-up for the PDF ───────────────────────────────────
    def writeup(self, winner, mentions):
        p = winner.get("panel", {})
        out = self.llm.ask_json(
            "Write the daily report for this idea in plain, simple language (no jargon). Return JSON: "
            '{"title": "≤8 words", "idea_simple": "≤45 words, what the idea is", '
            '"worth_statement": "≤45 words: is it worth pursuing and why", '
            '"how_it_works": ["3-6 short steps"], "automation_plan": ["3-5 steps naming free tools"], '
            '"limitations": ["3-6 short items"], "technical": {"tools": ["..."], "data_sources": ["..."], '
            '"free_resources": ["..."], "start_capital": "...", "time_to_first_result": "...", '
            '"cheapest_test": "...", "kill_criteria": "..."}}\n\n'
            + json.dumps({k: winner.get(k) for k in ("name", "one_liner", "system", "gap", "mechanism",
                                                      "why_now", "automation", "start_capital_usd")} | {"panel": p}),
            max_tokens=2200, tier="smart", system=JUDGE_SYSTEM) or {}
        verdict = {"pursue": "Yes", "test_first": "Test first", "no": "No"}.get(
            str(p.get("verdict")).lower(), "Test first")
        out["verdict"] = verdict  # always consistent with the panel, never re-decided by the writer
        out.setdefault("title", winner["name"])
        out.setdefault("idea_simple", winner["one_liner"])
        out.setdefault("worth_statement", p.get("verdict_reason", ""))
        lines = None
        if mentions:
            m = self.llm.ask_json(
                "For each idea, give a clear short name (≤6 words) and ONE plain sentence (≤25 words) explaining "
                'it and its main catch. Return JSON: {"items": [{"i": int, "name": "...", "sentence": "..."}]}\n\n' + "\n".join(
                    f"[{j}] {x['name']} — {x['one_liner']} | Verdict: {(x.get('panel') or {}).get('verdict_reason', '')}"
                    for j, x in enumerate(mentions)), max_tokens=1200) or {}
            lines = {int(it["i"]): it for it in m.get("items") or [] if str(it.get("i", "")).isdigit()}
        lines = lines or {}
        out["mentions"] = [{"name": (lines.get(j) or {}).get("name") or x["name"],
                            "sentence": (lines.get(j) or {}).get("sentence") or x["one_liner"],
                            "verdict": {"pursue": "Yes", "test_first": "Test first", "no": "No"}.get(
                                str((x.get("panel") or {}).get("verdict")).lower(), "Screened"),
                            "score": x.get("final", x.get("quick"))}
                           for j, x in enumerate(mentions)]
        return out

    # ── Orchestration ─────────────────────────────────────────────
    def run(self):
        self.start = time.time()
        ideas = self.generate()
        unique = self.filter_dedupe(ideas)
        finalists, screened = self.quick_screen(unique)
        ranked = self.deep_panel(finalists)
        if not ranked:  # fall back to quick-screen order if the panel failed
            ranked = [dict(f, final=f["quick"], panel={}) for f in finalists]
        ranked = self.tournament(ranked)
        winner = ranked[0] if ranked else None
        n_m = self.cfg.get("worthy_mentions", 6)
        rest = ranked[1:] + [s for s in screened if s not in ranked]
        mentions = rest[:n_m]
        report = self.writeup(winner, mentions) if winner else None
        self._archive(ideas_all=unique, winner=winner)
        return winner, report

    def _past_top(self, n):
        since = (dt.date.today() - dt.timedelta(days=14)).isoformat()
        return [dict(r) for r in self.con.execute(
            "SELECT name, one_liner FROM ideas WHERE day>=? AND final IS NOT NULL ORDER BY final DESC LIMIT ?",
            (since, n))]

    def _archive(self, ideas_all, winner):
        day = dt.date.today().isoformat()
        for i in ideas_all:
            self.con.execute(
                "INSERT INTO ideas (day, name, one_liner, op, quick, final, winner, data) VALUES (?,?,?,?,?,?,?,?)",
                (day, i["name"][:200], i["one_liner"][:400], i.get("op"), i.get("quick"), i.get("final"),
                 1 if i is winner else 0, json.dumps(i, default=str)[:12000]))
