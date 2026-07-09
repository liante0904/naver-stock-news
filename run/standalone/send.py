#!/usr/bin/env python3
"""GA standalone: read scraped JSON from stdin, dedup via SQLite, send to Telegram.

Pipe together with news.py:
    uv run python run/standalone/news.py | uv run python run/standalone/send.py
"""
import asyncio
import json
import os
import sys


def _escape_html(text: str) -> str:
    """Telegram HTML parse mode minimal escape (<, >, & only)."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
)
from models.database import DatabaseManager  # noqa: E402
from utils.telegram_util import sendMarkDownText  # noqa: E402

# ── channel mapping ──
SOURCE_TO_CHANNEL_KEY = {
    "CHOSUN_BIZ": "CHOSUN_BIZ",
    "NAVER_FLASH": "NAVER_FLASH",
    "NAVER_RANK": "NAVER_RANK",
}

HEADERS = {
    "CHOSUN_BIZ": "●조선비즈 - C-Biz봇",
    "NAVER_FLASH": "●네이버 - 실시간 뉴스 속보",
    "NAVER_RANK": "●네이버 - 가장 많이 본 뉴스",
}

CHANNEL_ENV_MAP = {
    "CHOSUN_BIZ": "TELEGRAM_CHANNEL_ID_CHOSUNBIZBOT",
    "NAVER_FLASH": "TELEGRAM_CHANNEL_ID_NAVER_FLASHNEWS",
    "NAVER_RANK": "TELEGRAM_CHANNEL_ID_NAVER_RANKNEWS",
}

EMOJI_PICK = "\U0001f449"  # 👉

# ── DB path ──
DB_DIR = os.environ.get("DEDUP_DB_DIR", "db")
DB_PATH = os.path.join(DB_DIR, "dedup.db")


def dedup_articles(articles: list[dict], db: DatabaseManager) -> dict[str, list[dict]]:
    """Filter articles through SQLite dedup. Returns new articles grouped by source."""
    grouped: dict[str, list[dict]] = {}
    for art in articles:
        source = art.get("source", "")
        if source not in SOURCE_TO_CHANNEL_KEY:
            continue
        title = art.get("article_title", "")
        url = art.get("source_url", "")
        if not title or not url:
            continue

        if db.insert_article(title=title, url=url, source=source):
            if source not in grouped:
                grouped[source] = []
            grouped[source].append(art)
    return grouped


async def send_grouped(grouped: dict[str, list[dict]]) -> dict[str, tuple[int, int]]:
    """Send grouped articles to Telegram channels.

    Returns stats dict: {source: (new_count, sent_count)}.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN_REPORT_ALARM_SECRET", "")
    if not bot_token:
        print("[send] SKIP: TELEGRAM_BOT_TOKEN_REPORT_ALARM_SECRET not set",
              file=sys.stderr)
        return {src: (len(items), 0) for src, items in grouped.items()}

    stats: dict[str, tuple[int, int]] = {}

    for source, items in grouped.items():
        channel_key = SOURCE_TO_CHANNEL_KEY[source]
        env_key = CHANNEL_ENV_MAP.get(channel_key, "")
        chat_id = os.getenv(env_key, "")
        if not chat_id:
            print(f"[send] SKIP: no channel env for source={source}", file=sys.stderr)
            stats[source] = (len(items), 0)
            continue

        header = HEADERS.get(source, f"●{source}")
        sent_count = 0
        buffer = ""

        for item in items:
            title = _escape_html(item.get("article_title", ""))
            link = item.get("source_url", "")
            if not title or not link:
                continue

            line = f"{title}\n{EMOJI_PICK}<a href='{link}'>링크</a>\n\n"
            if len(buffer) + len(line) > 3500:
                msg = f"{header}\n{buffer}"
                await sendMarkDownText(
                    token=bot_token,
                    chat_id=chat_id,
                    sendMessageText=msg,
                    parse_mode="HTML",
                )
                buffer = ""
            buffer += line
            sent_count += 1

        if buffer:
            msg = f"{header}\n{buffer}"
            await sendMarkDownText(
                token=bot_token,
                chat_id=chat_id,
                sendMessageText=msg,
                parse_mode="HTML",
            )

        stats[source] = (len(items), sent_count)

    return stats


async def main() -> None:
    # 1. Read JSON from stdin
    raw = sys.stdin.read()
    if not raw.strip():
        print("[send] stdin empty, nothing to send", file=sys.stderr)
        return

    try:
        articles = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[send] JSON parse error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(articles, list):
        print(f"[send] expected JSON array, got {type(articles).__name__}",
              file=sys.stderr)
        sys.exit(1)

    print(f"[send] received {len(articles)} articles from stdin", file=sys.stderr)

    # 2. Dedup
    os.makedirs(DB_DIR, exist_ok=True)
    db = DatabaseManager(DB_PATH)
    grouped = dedup_articles(articles, db)
    total_new = sum(len(v) for v in grouped.values())
    if total_new == 0:
        print(f"[send] no new articles (all {len(articles)} duplicates)",
              file=sys.stderr)
        return

    # 3. Send
    stats = await send_grouped(grouped)

    # 4. Report
    total_sent = sum(s for _, s in stats.values())
    print(f"[send] {total_new} new, {total_sent} sent "
          f"(dedup saved {len(articles) - total_new} duplicates)",
          file=sys.stderr)
    for source, (new, sent) in stats.items():
        print(f"[send]   {source}: {new} new → {sent} sent", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
