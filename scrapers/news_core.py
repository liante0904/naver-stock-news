# -*- coding:utf-8 -*-
"""Naver + ChosunBiz news scraping core — pure logic, no DB/Telegram deps."""
import asyncio
import os
import aiohttp
import html
import datetime
from loguru import logger

# ── API 엔드포인트 (환경변수 우선, 기본값은 예시) ──
_CHOSUN_BIZ_URL = os.getenv(
    "CHOSUN_BIZ_API_URL",
    ""  # CHOSUN_BIZ_API_URL env required
)
_NAVER_FLASH_URL = os.getenv(
    "NAVER_FLASH_API_URL",
    ""  # NAVER_FLASH_API_URL env required
)
_NAVER_RANK_URL = os.getenv(
    "NAVER_RANK_API_URL",
    ""  # NAVER_RANK_API_URL env required
)
_NAVER_FLASH_LINK_TPL = os.getenv(
    "NAVER_FLASH_LINK_TPL",
    ""  # {oid}/{aid} 치환
)
_NAVER_RANK_LINK_TPL = os.getenv(
    "NAVER_RANK_LINK_TPL",
    ""  # {oid}/{aid} 치환
)


async def _fetch(session, url, max_retries=3, delay=3):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    for attempt in range(max_retries):
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                if attempt < max_retries - 1:
                    logger.warning(f"{url} status {response.status}, retry {attempt+1}/{max_retries}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"{url} final fail (status {response.status})")
                    return None
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"{url} error: {e}, retry {attempt+1}/{max_retries}")
                await asyncio.sleep(delay)
            else:
                logger.exception(f"{url} final fail after {max_retries} retries: {e}")
                return None


def _escape_html(text):
    return html.escape(text) if text else ""


async def scrape_chosun_biz(session) -> list[dict]:
    url = _CHOSUN_BIZ_URL
    if not url:
        logger.error("CHOSUN_BIZ_API_URL not set")
        return []
    data = await _fetch(session, url)
    if not data:
        return []

    articles = []
    today_str = datetime.datetime.now().strftime('%Y%m%d')
    for item in data.get('newsItems', []):
        title_raw = item.get('title', '').strip()
        if not title_raw:
            continue
        title = _escape_html(title_raw)
        link = item['url']

        articles.append({
            "sec_firm_order": 100,
            "article_board_order": 0,
            "firm_nm": "조선비즈",
            "reg_dt": today_str,
            "article_title": title,
            "article_url": link,
            "download_url": link,
            "telegram_url": link,
            "pdf_url": link,
            "writer": "",
            "save_time": datetime.datetime.now().isoformat(),
            "report_unique_key": link,
        })
    return articles


async def scrape_naver_flash(session) -> list[dict]:
    url = _NAVER_FLASH_URL
    if not url:
        logger.error("NAVER_FLASH_API_URL not set")
        return []
    res = await _fetch(session, url)
    if not res or 'result' not in res:
        return []

    articles = []
    today_str = datetime.datetime.now().strftime('%Y%m%d')
    for item in res['result'].get('newsList', []):
        title_raw = item.get('tit', '').strip()
        if not title_raw:
            continue
        title = _escape_html(title_raw)
        oid, aid = item['oid'], item['aid']
        link = _NAVER_FLASH_LINK_TPL.format(oid=oid, aid=aid)
        unique_key = f"naver_flash_{oid}_{aid}"

        articles.append({
            "sec_firm_order": 101,
            "article_board_order": 0,
            "firm_nm": "네이버",
            "reg_dt": today_str,
            "article_title": title,
            "article_url": link,
            "download_url": link,
            "telegram_url": link,
            "pdf_url": link,
            "writer": "",
            "save_time": datetime.datetime.now().isoformat(),
            "report_unique_key": unique_key,
        })
    return articles


async def scrape_naver_rank(session) -> list[dict]:
    url = _NAVER_RANK_URL
    if not url:
        logger.error("NAVER_RANK_API_URL not set")
        return []
    res = await _fetch(session, url)
    if not res or 'result' not in res:
        return []

    articles = []
    today_str = datetime.datetime.now().strftime('%Y%m%d')
    for item in res['result'].get('newsList', []):
        title_raw = item.get('tit', '').strip()
        if not title_raw:
            continue
        title = _escape_html(title_raw)
        oid, aid = item['oid'], item['aid']
        link = _NAVER_RANK_LINK_TPL.format(oid=oid, aid=aid)
        unique_key = f"naver_rank_{oid}_{aid}"

        articles.append({
            "sec_firm_order": 101,
            "article_board_order": 1,
            "firm_nm": "네이버",
            "reg_dt": today_str,
            "article_title": title,
            "article_url": link,
            "download_url": link,
            "telegram_url": link,
            "pdf_url": link,
            "writer": "",
            "save_time": datetime.datetime.now().isoformat(),
            "report_unique_key": unique_key,
        })
    return articles


async def scrape_all_news() -> list[dict]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            scrape_chosun_biz(session),
            scrape_naver_flash(session),
            scrape_naver_rank(session),
        )
    return results[0] + results[1] + results[2]
