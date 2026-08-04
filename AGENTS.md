# News Scraper Working Guide

This repository owns Naver/Chosun news collection. Normal production collection
is the GitHub Actions workflow; the OCI Docker profile is a manual fallback.

## Read order

1. `README.md`
2. the matching GitHub Actions workflow
3. the affected source under `scrapers/`, `run/`, or `models/`

Do not start the fallback container as the first response to a missing-news
report. First inspect the GA run, artifact/import path, and source response.
Run the narrowest relevant check from this repository before committing.
