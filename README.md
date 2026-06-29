# naver-stock-news

## 운영 방식

- 운영 발송은 GitHub Actions `Naver/Chosun News Scraper -> SCP`가 담당한다.
- 스케줄은 KST 05~19시 5분 간격이다.
- OCI의 `naver-stock-news-bot` Docker 컨테이너는 상시 운영 대상이 아니다.
- Docker 컨테이너는 GA 장애 시 수동 fallback 용도이며 기본 `docker compose up -d`로는 실행되지 않는다.

수동 fallback 실행:

```bash
docker compose --profile fallback up -d
```

GA 운영으로 복귀:

```bash
docker update --restart=no naver-stock-news-bot
docker stop naver-stock-news-bot
```
