#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver News(경제 섹션 101) 헤드라인 리스트 크롤러 (Visual/Selenium 버전)
- requests 대신 Selenium을 사용하여 브라우저가 작동하는 모습을 직접 볼 수 있습니다.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

DEFAULT_SECTION_URL = "https://news.naver.com/section/101"
# DOM 구조에 따른 Selector
CSS_UL_CANDIDATE = "ul[id^='_SECTION_HEADLINE_LIST_']"


@dataclass
class HeadlineItem:
    title: str
    url: str
    press: Optional[str] = None
    datetime: Optional[str] = None
    lede: Optional[str] = None
    is_blind: bool = False
    rank: Optional[int] = None


def build_driver(headless: bool = False) -> webdriver.Chrome:
    """
    Selenium WebDriver 생성
    """
    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")

    opts.add_argument("--window-size=1200,800")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=ko-KR")
    
    # 자동화 탐지 방지
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=opts)
    return driver


def with_page(url: str, page: int) -> str:
    """
    URL에 page 파라미터 적용
    """
    if page <= 1:
        return url
    p = urlparse(url)
    qs = parse_qs(p.query)
    qs["page"] = [str(page)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def extract_text(element, by, selector) -> Optional[str]:
    try:
        el = element.find_element(by, selector)
        return el.text.strip() or None
    except NoSuchElementException:
        return None


def crawl_visual(
    section_url: str,
    pages: int,
    sleep: float,
    timeout: float,
    debug: bool
) -> List[HeadlineItem]:
    
    driver = build_driver(headless=False)  # 화면을 보기 위해 headless=False 강제
    all_items: List[HeadlineItem] = []

    try:
        for page in range(1, pages + 1):
            target_url = with_page(section_url, page)
            if debug:
                print(f"[DEBUG] 이동 중: {target_url}")
            
            driver.get(target_url)
            
            # 페이지 로딩 대기 (UL 요소가 뜰 때까지)
            try:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, CSS_UL_CANDIDATE))
                )
            except TimeoutException:
                print(f"[ERROR] 페이지 {page}: 뉴스 리스트를 찾을 수 없습니다.")
                continue

            # 뉴스 리스트 찾기
            try:
                ul = driver.find_element(By.CSS_SELECTOR, CSS_UL_CANDIDATE)
            except NoSuchElementException:
                continue

            # 아이템 추출
            lis = ul.find_elements(By.CSS_SELECTOR, "li.sa_item._SECTION_HEADLINE")
            
            if debug:
                print(f"[DEBUG] {len(lis)}개의 기사 발견")

            for li in lis:
                try:
                    # is_blind 체크
                    classes = li.get_attribute("class")
                    is_blind = "is_blind" in classes if classes else False

                    # 제목 및 링크
                    try:
                        a_tag = li.find_element(By.CSS_SELECTOR, "a.sa_text_title")
                    except NoSuchElementException:
                        a_tag = li.find_element(By.CSS_SELECTOR, "a[href]")
                    
                    title = a_tag.text.strip()
                    link = a_tag.get_attribute("href")

                    # 언론사
                    press = extract_text(li, By.CSS_SELECTOR, ".sa_text_press")
                    
                    # 르데(요약)
                    lede = extract_text(li, By.CSS_SELECTOR, ".sa_text_lede")
                    
                    # 시간 (여러 후보)
                    dt = extract_text(li, By.CSS_SELECTOR, ".sa_text_datetime")
                    if not dt:
                        dt = extract_text(li, By.CSS_SELECTOR, "._SECTION_HEADLINE_LIST_TIME")

                    item = HeadlineItem(
                        title=title,
                        url=link,
                        press=press,
                        datetime=dt,
                        lede=lede,
                        is_blind=is_blind,
                        rank=len(all_items) + 1
                    )
                    all_items.append(item)

                except Exception as e:
                    if debug:
                        print(f"[WARN] 아이템 파싱 중 에러: {e}")
                    continue

            # 사용자가 볼 수 있게 대기
            time.sleep(sleep)

    finally:
        driver.quit()

    return all_items


def save_jsonl(items: List[HeadlineItem], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 뉴스 헤드라인 크롤러 (Visual 버전)")
    ap.add_argument("--url", default=DEFAULT_SECTION_URL, help="섹션 URL")
    ap.add_argument("--pages", type=int, default=1, help="크롤링할 페이지 수")
    ap.add_argument("--sleep", type=float, default=2.0, help="페이지 간 대기(초) - 관전용")
    ap.add_argument("--out", default="naver_section_101_visual.jsonl", help="출력 파일 경로")
    ap.add_argument("--debug", action="store_true", help="디버그 모드")
    
    args = ap.parse_args()

    print("브라우저를 실행합니다...", file=sys.stderr)
    items = crawl_visual(
        section_url=args.url,
        pages=args.pages,
        sleep=args.sleep,
        timeout=10.0,
        debug=args.debug
    )

    save_jsonl(items, args.out)
    print(f"완료: {len(items)}개의 기사를 {args.out}에 저장했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
