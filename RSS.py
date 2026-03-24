# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import feedparser


BASE_DIR = Path(__file__).resolve().parent
PROFILE_PATH = BASE_DIR / "zotero_profile.json"
RSS_PATH = BASE_DIR / "rss_sources.json"
SEEN_PATH = BASE_DIR / "seen_items.json"
OUTPUT_PATH = BASE_DIR / "rss_matches.json"
DOCS_DIR = BASE_DIR / "docs"

TOP_KW = 200

HIGH_SCORE = 12
MID_SCORE = 7
MIN_SCORE = 3

TIER_WEIGHTS = [3, 2, 1]
MAX_ITEMS_PER_FEED = 1000


# 文本标准化
def norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


# 读取画像
def load_profile():
    print("读取画像")
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    keyword_items = profile.get("keywords") or profile.get("top_keywords_focus") or profile.get("top_keywords") or []
    keyword_items = keyword_items[:TOP_KW]
    kw = {}

    if not keyword_items:
        return kw

    total = len(keyword_items)
    tier_count = len(TIER_WEIGHTS)

    for idx, item in enumerate(keyword_items):
        keyword = item["keyword"].lower()
        tier_idx = min(idx * tier_count // total, tier_count - 1)
        kw[keyword] = float(TIER_WEIGHTS[tier_idx])

    return kw


# 读取 RSS 源
def load_rss_urls():
    print("读取 RSS 列表")
    return json.loads(RSS_PATH.read_text(encoding="utf-8"))


# 读取已处理记录
def load_seen():
    print("读取已处理记录")
    if SEEN_PATH.exists():
        return set(json.loads(SEEN_PATH.read_text(encoding="utf-8")))
    return set()


# 保存已处理记录
def save_seen(seen):
    print("保存已处理记录")
    SEEN_PATH.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")


def load_history():
    print("读取历史命中")
    if not OUTPUT_PATH.exists():
        return []
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def save_history(items):
    print("保存 JSON")
    OUTPUT_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# 条目标识
def get_uid(entry):
    return entry.get("id", "").strip() or entry.get("link", "").strip() or entry.get("title", "").strip()


def history_key(item):
    return item.get("link", "").strip() or item.get("title", "").strip()


def history_timestamp(item):
    return item.get("collected_at", "") or item.get("published", "") or ""


def merge_history(history_items, new_items):
    merged = {}

    for item in history_items:
        key = history_key(item)
        if not key:
            continue
        item.setdefault("matched_keywords", [])
        item.setdefault("summary", "")
        item.setdefault("collected_at", "")
        merged[key] = item

    for item in new_items:
        key = history_key(item)
        if not key:
            continue
        merged[key] = item

    merged_items = list(merged.values())
    merged_items.sort(key=history_timestamp, reverse=True)
    return merged_items


# 打分
def score_text(text, kw_weights):
    text = norm(text)
    score = 0.0
    kw_hits = []

    words = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text))
    for kw, weight in kw_weights.items():
        if kw in words:
            score += weight
            kw_hits.append({"keyword": kw, "score": round(weight, 4)})

    return round(score, 4), kw_hits


# 读取单个 RSS
def parse_rss(url):
    print(f"读取 RSS: {url}")
    feed = feedparser.parse(url)
    source_title = feed.feed.get("title", "")

    items = []
    for entry in feed.entries:
        items.append({
            "uid": get_uid(entry),
            "feed_title": source_title,
            "rss_url": url,
            "title": entry.get("title", ""),
            "summary": entry.get("summary", "") or entry.get("description", ""),
            "link": entry.get("link", "") or entry.get("id", ""),
            "published": entry.get("published", "") or entry.get("updated", ""),
        })
    return items


# 单条 RSS item
def item_xml(item):
    score = item["score"]
    title = escape(f"[{score}] {item['title']}")
    link = escape(item["link"])
    pub = escape(item["published"] or "")
    desc = escape(
        f"Score: {score} | Feed: {item['feed_title']} | "
        f"Keywords: {', '.join(x['keyword'] for x in item['matched_keywords'])}\n\n"
        f"{item['summary']}"
    )
    guid = escape(item["link"] or item["title"])

    return f"""<item>
<title>{title}</title>
<link>{link}</link>
<description>{desc}</description>
<pubDate>{pub}</pubDate>
<guid>{guid}</guid>
</item>"""


# 写 RSS 文件
def write_rss(items, title, out_path):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>{escape(title)}</title>
<link></link>
<description>{escape(title)}</description>
{''.join(item_xml(x) for x in items)}
</channel>
</rss>
"""
    out_path.write_text(xml, encoding="utf-8")


# 主流程
def main():
    kw_weights = load_profile()
    rss_urls = load_rss_urls()
    seen = load_seen()
    history_items = load_history()

    new_results = []
    new_seen = set()

    for rss_url in rss_urls:
        for item in parse_rss(rss_url):
            uid = item["uid"]
            if not uid or uid in seen:
                continue

            text = f"{item['title']} {item['summary']}"
            score, kw_hits = score_text(text, kw_weights)
            new_seen.add(uid)

            if score < MIN_SCORE:
                continue

            new_results.append({
                "score": score,
                "title": item["title"],
                "link": item["link"],
                "published": item["published"],
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "feed_title": item["feed_title"],
                "rss_url": item["rss_url"],
                "matched_keywords": sorted(kw_hits, key=lambda x: x["score"], reverse=True),
                "summary": item["summary"],
            })

    results = merge_history(history_items, new_results)

    save_history(results)

    print("生成 RSS")
    DOCS_DIR.mkdir(exist_ok=True)

    high = [x for x in results if x["score"] >= HIGH_SCORE][:MAX_ITEMS_PER_FEED]
    mid = [x for x in results if MID_SCORE <= x["score"] < HIGH_SCORE][:MAX_ITEMS_PER_FEED]
    low = [x for x in results if MIN_SCORE <= x["score"] < MID_SCORE][:MAX_ITEMS_PER_FEED]

    write_rss(high, f"High Score Papers (>= {HIGH_SCORE})", DOCS_DIR / "high.xml")
    write_rss(mid, f"Mid Score Papers ({MID_SCORE} - {HIGH_SCORE})", DOCS_DIR / "mid.xml")
    write_rss(low, f"Low Score Papers ({MIN_SCORE} - {MID_SCORE})", DOCS_DIR / "low.xml")

    save_seen(seen | new_seen)

    print("完成")


if __name__ == "__main__":
    main()
