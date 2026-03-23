# -*- coding:utf-8 -*-
import asyncio
import os
import datetime
from loguru import logger
from dotenv import load_dotenv

from models.database import DatabaseManager
from scrapers.news import NewsScraper

load_dotenv()

# 실행 환경 감지
IS_DOCKER = os.path.exists("/app")
ENV = os.getenv('ENV', 'dev').lower()
IS_PROD = ENV == 'production'

# 로그 설정
def setup_logging():
    now_date = datetime.datetime.now().strftime("%Y%m%d")
    base_log_dir = "/app/log" if IS_DOCKER else os.path.expanduser("~/log")
    log_dir = os.path.join(base_log_dir, now_date)
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"{now_date}_news.log")
    logger.add(log_file, rotation="10 MB", retention="10 days", level="INFO", enqueue=True)
    return log_file

async def run_service(scraper, db_path):
    """도커 서비스 모드: 무한 루프 (시계 정시 기준 5분 단위 실행)"""
    log_prefix = "" if IS_PROD else "[DEV] "
    interval = 300  # 5분
    logger.info(f"{log_prefix}Starting Naver Stock News Bot in SERVICE mode (Aligned to 5m)")
    
    while True:
        now = datetime.datetime.now()
        # 현재 시간에서 정각(0분 0초) 기준 지난 총 초 계산
        seconds_since_hour = (now.minute * 60) + now.second
        # 다음 주기가 오기까지 남은 초 계산 (정각 기준)
        wait_seconds = interval - (seconds_since_hour % interval)
        
        # 만약 딱 정각에 도달했다면 (초가 0이라면) 300초를 기다리는 대신 즉시 실행 방지
        if wait_seconds <= 0: wait_seconds = interval

        logger.info(f"Waiting {int(wait_seconds)}s until next aligned run...")
        await asyncio.sleep(wait_seconds)
        
        # 미세한 오차로 일찍 깨어나는 것 방지 (0.5초 추가 대기)
        await asyncio.sleep(0.5)

        logger.info(f"--- [Loop Start: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
        try:
            await scraper.run_all()
            logger.info(f"Scraping completed.")
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}")
            await asyncio.sleep(10)

async def run_once(scraper, db_path):
    """로컬 태스크 모드: 1회 실행 (크론탭 호환)"""
    log_prefix = "" if IS_PROD else "[DEV] "
    logger.info(f"{log_prefix}Starting Naver Stock News Bot in TASK mode (Once)")
    try:
        await scraper.run_all()
        logger.info("Scraping completed successfully.")
    except Exception as e:
        logger.error(f"Task failed: {e}")

async def main():
    setup_logging()
    
    prefix = 'prod' if IS_PROD else 'dev'
    db_path = os.getenv('DB_PATH', f'./db/{prefix}_naver_stock_news.db')
    
    try:
        db = DatabaseManager(db_path)
        # 배포 환경이 아니면 is_dev를 True로 설정
        scraper = NewsScraper(db, is_dev=(not IS_PROD))
        
        if IS_DOCKER:
            await run_service(scraper, db_path)
        else:
            await run_once(scraper, db_path)
            
    except Exception as e:
        logger.critical(f"Critical Initialization Error: {e}")
        if IS_DOCKER:
            # 초기화 실패 시 무한 재시작 방지를 위해 대기 후 종료
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
