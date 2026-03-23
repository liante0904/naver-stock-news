# -*- coding:utf-8 -*- 
import os
import asyncio
import aiohttp
import html
import datetime
from loguru import logger
from dotenv import load_dotenv

from models.database import DatabaseManager
from utils.telegram_util import sendMarkDownText

load_dotenv()

# 환경 변수
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN_REPORT_ALARM_SECRET')
CHANNELS = {
    'CHOSUN': os.getenv('TELEGRAM_CHANNEL_ID_CHOSUNBIZBOT'),
    'NAVER_FLASH': os.getenv('TELEGRAM_CHANNEL_ID_NAVER_FLASHNEWS'),
    'NAVER_RANK': os.getenv('TELEGRAM_CHANNEL_ID_NAVER_RANKNEWS')
}

EMOJI_PICK = "👉"

class NewsScraper:
    def __init__(self, db: DatabaseManager, is_dev: bool = False):
        self.db = db
        # 이 부분이 핵심입니다. 확실하게 [DEV]를 붙입니다.
        self.prefix = "<b>[DEV]</b> " if is_dev else ""
        logger.info(f"NewsScraper initialized with prefix: '{self.prefix}'")

    async def fetch(self, session, url):
        try:
            async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as response:
                if response.status != 200:
                    logger.error(f"{url} 접속 실패 (Status: {response.status})")
                    return None
                return await response.json()
        except Exception as e:
            logger.exception(f"Error fetching {url}: {e}")
            return None

    def escape_html(self, text):
        return html.escape(text) if text else ""

    async def _send_batch_message(self, chat_id, header, body):
        if not body: return
        full_message = f"{self.prefix}{header}\n{body}"
        await sendMarkDownText(token=TELEGRAM_BOT_TOKEN, chat_id=chat_id, sendMessageText=full_message, parse_mode="HTML")

    async def scrap_chosun_biz(self):
        source = "CHOSUN_BIZ"
        url = 'https://mweb-api.stockplus.com/api/news_items/all_news.json?scope=latest&limit=100'
        header = "●조선비즈 - C-Biz봇"
        async with aiohttp.ClientSession() as session:
            data = await self.fetch(session, url)
            if not data: return
            send_buffer = ""
            for item in data.get('newsItems', []):
                title_raw = item.get('title', '').strip()
                if not title_raw: continue
                title = self.escape_html(title_raw)
                link = item['url']
                if self.db.insert_article(title=title, url=link, source=source):
                    logger.info(f"New {source} Article: {title}")
                    send_buffer += f"{title}\n{EMOJI_PICK}<a href='{link}'>링크</a>\n\n"
                    if len(send_buffer) >= 3000:
                        await self._send_batch_message(CHANNELS['CHOSUN'], header, send_buffer)
                        send_buffer = ""
            if send_buffer:
                await self._send_batch_message(CHANNELS['CHOSUN'], header, send_buffer)

    async def scrap_naver_flash(self):
        source = "NAVER_FLASH"
        url = 'https://m.stock.naver.com/api/json/news/newsListJson.nhn?category=flashnews'
        header = "●네이버 - 실시간 뉴스 속보"
        async with aiohttp.ClientSession() as session:
            res = await self.fetch(session, url)
            if not res or 'result' not in res: return
            data = res['result']
            send_buffer = ""
            for item in data.get('newsList', []):
                title_raw = item.get('tit', '').strip()
                if not title_raw: continue
                title = self.escape_html(title_raw)
                link = f"https://m.stock.naver.com/investment/news/flashnews/{item['oid']}/{item['aid']}"
                if self.db.insert_article(title=title, url=link, source=source):
                    logger.info(f"New {source} Article: {title}")
                    send_buffer += f"{title}\n{EMOJI_PICK}<a href='{link}'>링크</a>\n\n"
                    if len(send_buffer) >= 3000:
                        await self._send_batch_message(CHANNELS['NAVER_FLASH'], header, send_buffer)
                        send_buffer = ""
            if send_buffer:
                await self._send_batch_message(CHANNELS['NAVER_FLASH'], header, send_buffer)

    async def scrap_naver_rank(self):
        source = "NAVER_RANK"
        url = 'https://m.stock.naver.com/api/json/news/newsListJson.nhn?category=ranknews'
        header = "●네이버 - 가장 많이 본 뉴스"
        async with aiohttp.ClientSession() as session:
            res = await self.fetch(session, url)
            if not res or 'result' not in res: return
            data = res['result']
            send_buffer = ""
            for item in data.get('newsList', []):
                title_raw = item.get('tit', '').strip()
                if not title_raw: continue
                title = self.escape_html(title_raw)
                link = f"https://m.stock.naver.com/investment/news/ranknews/{item['oid']}/{item['aid']}"
                if self.db.insert_article(title=title, url=link, source=source):
                    logger.info(f"New {source} Article: {title}")
                    send_buffer += f"{title}\n{EMOJI_PICK}<a href='{link}'>링크</a>\n\n"
                    if len(send_buffer) >= 3000:
                        await self._send_batch_message(CHANNELS['NAVER_RANK'], header, send_buffer)
                        send_buffer = ""
            if send_buffer:
                await self._send_batch_message(CHANNELS['NAVER_RANK'], header, send_buffer)

    async def run_all(self):
        await asyncio.gather(
            self.scrap_chosun_biz(),
            self.scrap_naver_flash(),
            self.scrap_naver_rank()
        )
