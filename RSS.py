# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

import feedparser


BASE_DIR = Path(__file__).resolve().parent
PROFILE_PATH = BASE_DIR / "zotero_profile.json"
RSS_PATH = BASE_DIR / "rss_sources.json"
SEEN_PATH = BASE_DIR / "seen_items.json"
OUTPUT_PATH = BASE_DIR / "rss_matches.json"
DOCS_DIR = BASE_DIR / "docs"

TOP_KW = 40
TOP_PH = 30

HIGH_SCORE = 120
MID_SCORE = 60
MIN_SCORE = 20


# 文本标准化
def norm(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


# 读取画像
def load_profile():
    print("读取画像")
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    kw = {x["keyword"].lower(): float(x["score"]) for x in profile["top_keywords_focus"][:TOP_KW]}
    ph = {x["phrase"].lower(): float(x["score"]) for x in profile["top_phrases"][:TOP_PH]}
    return kw, ph


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


# 条目标识
def get_uid(entry):
    return entry.get("id", "").strip() or entry.get("link", "").strip() or entry.get("title", "").strip()


# 打分
def score_text(text, kw_weights, ph_weights):
    text = norm(text)
    score = 0.0
    kw_hits = []
    ph_hits = []

    for phrase, weight in ph_weights.items():
        if phrase in text:
            score += weight
            ph_hits.append({"phrase": phrase, "score": round(weight, 4)})

    words = set(re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text))
    for kw, weight in kw_weights.items():
        if kw in words:
            score += weight
            kw_hits.append({"keyword": kw, "score": round(weight, 4)})

    return round(score, 4), kw_hits, ph_hits


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
        f"Keywords: {', '.join(x['keyword'] for x in item['matched_keywords'])} | "
        f"Phrases: {', '.join(x['phrase'] for x in item['matched_phrases'])}\n\n"
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
    kw_weights, ph_weights = load_profile()
    rss_urls = load_rss_urls()
    seen = load_seen()

    results = []
    new_seen = set()

    for rss_url in rss_urls:
        for item in parse_rss(rss_url):
            uid = item["uid"]
            if not uid or uid in seen:
                continue

            text = f"{item['title']} {item['summary']}"
            score, kw_hits, ph_hits = score_text(text, kw_weights, ph_weights)
            new_seen.add(uid)

            if score < MIN_SCORE:
                continue

            results.append({
                "score": score,
                "title": item["title"],
                "link": item["link"],
                "published": item["published"],
                "feed_title": item["feed_title"],
                "rss_url": item["rss_url"],
                "matched_phrases": sorted(ph_hits, key=lambda x: x["score"], reverse=True),
                "matched_keywords": sorted(kw_hits, key=lambda x: x["score"], reverse=True),
                "summary": item["summary"],
            })

    results.sort(key=lambda x: x["score"], reverse=True)

    print("保存 JSON")
    OUTPUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("生成 RSS")
    DOCS_DIR.mkdir(exist_ok=True)

    high = [x for x in results if x["score"] >= HIGH_SCORE]
    mid = [x for x in results if MID_SCORE <= x["score"] < HIGH_SCORE]
    low = [x for x in results if MIN_SCORE <= x["score"] < MID_SCORE]

    write_rss(high, f"High Score Papers (>= {HIGH_SCORE})", DOCS_DIR / "high.xml")
    write_rss(mid, f"Mid Score Papers ({MID_SCORE} - {HIGH_SCORE})", DOCS_DIR / "mid.xml")
    write_rss(low, f"Low Score Papers ({MIN_SCORE} - {MID_SCORE})", DOCS_DIR / "low.xml")

    save_seen(seen | new_seen)

    print("完成")


if __name__ == "__main__":
    main()