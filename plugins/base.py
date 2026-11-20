"""Every hunting ground is a Plugin with one job: find candidates and emit them."""
import hashlib
import time

from core import store
from core.scoring import score


class Plugin:
    key = "base"
    ground = 0
    name = "Base"
    pursuit = "alert"  # alert | auto-capped | auto | never (documented in the report)

    def __init__(self, con, llm, cfg, budget_s):
        self.con, self.llm, self.cfg = con, llm, cfg
        self.deadline = time.time() + budget_s
        self.items = 0
        self.hits = 0
        self.new = 0
        self.notes = []

    def time_left(self):
        return self.deadline - time.time()

    def out_of_time(self, reserve=5):
        return self.time_left() < reserve

    def emit(self, uid, title, summary, url="", value_usd=0.0, cost_usd=0.0,
             claimability=0.3, awareness=0.5, claimants=0, deadline=None,
             status="needs_review", private=False, data=None):
        cid = f"{self.key}:" + hashlib.sha1(str(uid).encode()).hexdigest()[:16]
        s = score(value_usd, cost_usd, claimability, awareness, claimants)
        is_new = store.upsert_candidate(self.con, dict(
            id=cid, plugin=self.key, title=title[:200], summary=summary[:1500], url=url,
            value_usd=value_usd or 0, cost_usd=cost_usd or 0, claimability=claimability,
            awareness=awareness, claimants=claimants, deadline=deadline, status=status,
            private=1 if private else 0, score=s, data=data or {}))
        self.items += 1
        self.new += int(is_new)
        if s >= self.cfg.get("min_score_for_top", 1.0):
            self.hits += 1
        return cid

    def run(self):
        raise NotImplementedError
