"""Ground #6 — Rule changes that open new windows.

Reads regulator / ecosystem feeds and the US Federal Register, keeps only new
items, and asks an LLM one question per batch: does this newly permit or
newly reward something an individual could do with automation, small capital
and no selling, hiring or persuading?
"""
import xml.etree.ElementTree as ET

from core import net, store
from plugins.base import Plugin


def _rss_items(xml_text):
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        get = lambda n: next((c for c in it if c.tag.split("}")[-1] == n), None)  # noqa: E731
        title = (get("title").text if get("title") is not None else "") or ""
        link_el = get("link")
        link = (link_el.text or link_el.attrib.get("href", "")) if link_el is not None else ""
        desc_el = get("description") if get("description") is not None else get("summary")
        desc = (desc_el.text or "") if desc_el is not None else ""
        out.append({"title": title.strip(), "link": link.strip(), "desc": desc[:600]})
    return out


class RuleChanges(Plugin):
    key, ground, name, pursuit = "p6", 6, "Rule changes", "alert only"

    def run(self):
        seen = set(store.kv_get(self.con, "p6_seen", []))
        fresh = []
        for feed in self.cfg.get("rule_feeds") or []:
            if self.out_of_time(10):
                break
            try:
                for it in _rss_items(net.get(feed["url"]).text)[:30]:
                    if it["link"] and it["link"] not in seen:
                        fresh.append({**it, "source": feed["name"]})
            except Exception as e:  # noqa: BLE001
                self.notes.append(f"{feed['name']}: {type(e).__name__}")
        for term in self.cfg.get("federal_register_terms") or []:
            if self.out_of_time(10):
                break
            try:
                fr = net.get_json("https://www.federalregister.gov/api/v1/documents.json",
                                  params={"conditions[term]": term, "order": "newest", "per_page": 10})
                for d in fr.get("results") or []:
                    if d.get("html_url") and d["html_url"] not in seen:
                        fresh.append({"title": d.get("title", ""), "link": d["html_url"],
                                      "desc": (d.get("abstract") or "")[:600], "source": "Federal Register"})
            except Exception as e:  # noqa: BLE001
                self.notes.append(f"Federal Register: {type(e).__name__}")
        uniq = {f["link"]: f for f in fresh}
        fresh = list(uniq.values())
        for f in fresh:
            seen.add(f["link"])
        store.kv_set(self.con, "p6_seen", list(seen)[-5000:])
        if not fresh or not self.llm.available:
            if fresh and not self.llm.available:
                self.notes.append(f"{len(fresh)} new items not screened (no LLM key).")
            return
        for i in range(0, len(fresh), 15):
            if self.out_of_time(15):
                break
            batch = fresh[i:i + 15]
            listing = "\n".join(f"[{j}] ({b['source']}) {b['title']} — {b['desc']}" for j, b in enumerate(batch))
            res = self.llm.ask_json(
                "Below are new regulatory/ecosystem announcements. Identify ONLY items that newly permit, "
                "newly reward, or create a time-limited window for something an individual could do using "
                "software automation and small capital, WITHOUT selling, hiring, persuading or competing "
                "head-to-head. Return JSON: {\"items\": [{\"index\": int, \"opportunity\": string, "
                "\"window_ends\": \"YYYY-MM-DD\"|null, \"confidence\": number}]} (empty list if none).\n\n"
                + listing) or {}
            for r in res.get("items") or []:
                try:
                    b = batch[int(r["index"])]
                except (KeyError, ValueError, IndexError, TypeError):
                    continue
                conf = float(r.get("confidence") or 0.3)
                self.emit(uid=f"rule:{b['link']}", title=f"{b['source']}: {b['title']}",
                          summary=r.get("opportunity", ""), url=b["link"], value_usd=100 * conf,
                          claimability=conf, awareness=0.5, deadline=r.get("window_ends"))
