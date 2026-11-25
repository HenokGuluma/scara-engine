"""Fetch today's fresh headlines — the 'right time' context for generators."""
import random
import re
import xml.etree.ElementTree as ET

from core import net


def _items(xml_text, limit=25):
    root = ET.fromstring(xml_text.encode() if isinstance(xml_text, str) else xml_text)
    out = []
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = next((c.text for c in it if c.tag.split("}")[-1] == "title"), "") or ""
        desc = next((c.text for c in it if c.tag.split("}")[-1] in ("description", "summary")), "") or ""
        desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", desc)).strip()
        if title.strip():
            out.append(f"{title.strip()} — {desc[:160]}")
        if len(out) >= limit:
            break
    return out


def fetch(feeds):
    signals, errors = [], []
    for f in feeds:
        try:
            for line in _items(net.get(f["url"], timeout=20, tries=2).text):
                signals.append(f"[{f['name']}] {line}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{f['name']}: {type(e).__name__}")
    random.shuffle(signals)
    return signals, errors
