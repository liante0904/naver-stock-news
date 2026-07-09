#!/usr/bin/env python3
"""GA standalone: scrape news AND send to Telegram with in-memory dedup."""
import asyncio
import os
import sys
def _escape_html(text: str) -> str:
    """Telegram HTML parse mode에서 특수문자만 최소 이스케이프."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scrapers.news_core import scrape_all_news
from utils.telegram_util import sendMarkDownText

# 환경변수에서 설정 읽기
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_REPORT_ALARM_SECRET", "")
CHANNELS = {
    "CHOSUN_BIZ": os.getenv("TELEGRAM_CHANNEL_ID_CHOSUNBIZBOT", ""),
    "NAVER_FLASH": os.getenv("TELEGRAM_CHANNEL_ID_NAVER_FLASHNEWS", ""),
    "NAVER_RANK": os.getenv("TELEGRAM_CHANNEL_ID_NAVER_RANKNEWS", ""),
}

SOURCE_TO_CHANNEL = {
    "CHOSUN_BIZ": "CHOSUN_BIZ",
    "NAVER_FLASH": "NAVER_FLASH",
    "NAVER_RANK": "NAVER_RANK",
}

HEADERS = {
    "CHOSUN_BIZ": "●조선비즈 - C-Biz봇",
    "NAVER_FLASH": "●네이버 - 실시간 뉴스 속보",
    "NAVER_RANK": "●네이버 - 가장 많이 본 뉴스",
}

EMOJI_PICK = "\U0001f449"


async def send_articles(articles):
    """기사를 소스별로 그룹화하여 텔레그램 채널로 발송"""
    # 소스별로 그룹화
    grouped = {}
    for art in articles:
        source = art.get("source", "")
        if source not in grouped:
            grouped[source] = []
        grouped[source].append(art)

    for source, items in grouped.items():
        channel_key = SOURCE_TO_CHANNEL.get(source)
        if not channel_key:
            continue
        chat_id = CHANNELS.get(channel_key)
        if not chat_id:
            print(f"[send_news] No channel for source={source}", file=sys.stderr)
            continue

        header = HEADERS.get(source, f"●{source}")
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
                    token=BOT_TOKEN,
                    chat_id=chat_id,
                    sendMessageText=msg,
                    parse_mode="HTML",
                )
                buffer = ""
            buffer += line

        if buffer:
            msg = f"{header}\n{buffer}"
            await sendMarkDownText(
                token=BOT_TOKEN,
                chat_id=chat_id,
                sendMessageText=msg,
                parse_mode="HTML",
            )

        print(
            f"[send_news] {source}: {len(items)} articles sent to {chat_id}",
            file=sys.stderr,
        )


async def main():
    # 1. 스크래핑
    articles = await scrape_all_news()
    print(f"[send_news] scraped {len(articles)} articles", file=sys.stderr)

    if not articles:
        print("[send_news] no articles, exiting", file=sys.stderr)
        return

    # 2. 발송
    await send_articles(articles)
    print(f"[send_news] done", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
