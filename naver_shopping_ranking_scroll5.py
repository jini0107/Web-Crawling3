#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
네이버 쇼핑 랭킹(프로모션) 페이지 Selenium 스크롤 크롤러

요구사항(사용자 지정)
- 기준 URL: https://shopping.naver.com/promotion?type=RANKING&categoryId=50000000
- 스크롤 5번 수행
- UL 탐색 기준
  1) CSS selector:
     #promotion_module_list > div.promotionVerticalResponsive_promotion_modules__tTk52 > div > div > div.productListResponsive_product_list_responsive__87_gs > ul
  2) XPath:
     //*[@id="promotion_module_list"]/div[3]/div/div/div[4]/ul
- 수집 데이터: UL 태그 밑의 LI 태그의 값(텍스트 + outerHTML)

출력
- 기본: JSONL (각 줄이 1개 item)
- 옵션: CSV

의존성
- selenium (Selenium 4는 Selenium Manager로 드라이버 자동 관리)

실행 예시
1) 기본 실행(비-헤드리스, JSONL 저장)
   python naver_shopping_ranking_scroll5.py

2) 헤드리스 + CSV 저장
   python naver_shopping_ranking_scroll5.py --headless --format csv --out out.csv

3) 스크롤 횟수 변경
   python naver_shopping_ranking_scroll5.py --scrolls 5
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


DEFAULT_URL = "https://shopping.naver.com/promotion?type=RANKING&categoryId=50000000"

CSS_UL = (
    "#promotion_module_list > "
    "div.promotionVerticalResponsive_promotion_modules__tTk52 > div > div > "
    "div.productListResponsive_product_list_responsive__87_gs > ul"
)
XPATH_UL = '//*[@id="promotion_module_list"]/div[3]/div/div/div[4]/ul'


@dataclass
class LiItem:
    idx: int
    text: str
    outer_html: str


def build_driver(headless: bool, window_size: str, user_agent: Optional[str]) -> webdriver.Chrome:
    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")

    opts.add_argument(f"--window-size={window_size}")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--lang=ko-KR")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")

    driver = webdriver.Chrome(options=opts)

    # automation flag 완화(사이트에 따라 필요)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
    )
    return driver


def wait_ready(driver: webdriver.Chrome, timeout: float) -> None:
    WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")


def locate_ul(driver: webdriver.Chrome, timeout: float, css_ul: str, xpath_ul: str):
    """
    1) CSS selector로 UL 찾기
    2) 실패 시 XPath로 찾기
    """
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CSS_SELECTOR, css_ul)))
    except TimeoutException:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath_ul)))


def li_count_under_ul(ul) -> int:
    try:
        return len(ul.find_elements(By.CSS_SELECTOR, "li"))
    except WebDriverException:
        return 0


def scroll_down_once(driver: webdriver.Chrome) -> None:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")


def crawl(
    url: str,
    css_ul: str,
    xpath_ul: str,
    scrolls: int,
    wait_sec: float,
    timeout: float,
    headless: bool,
    window_size: str,
    user_agent: Optional[str],
    debug: bool,
) -> List[LiItem]:
    driver: Optional[webdriver.Chrome] = None
    try:
        driver = build_driver(headless=headless, window_size=window_size, user_agent=user_agent)
        driver.get(url)
        wait_ready(driver, timeout)

        ul = locate_ul(driver, timeout, css_ul, xpath_ul)
        prev_count = li_count_under_ul(ul)
        if debug:
            print(f"[DEBUG] initial li_count={prev_count}", file=sys.stderr)

        for i in range(scrolls):
            scroll_down_once(driver)
            time.sleep(max(0.1, wait_sec))

            # UL이 재렌더링될 수 있어 매번 재탐색
            ul = locate_ul(driver, timeout, css_ul, xpath_ul)

            # 새 아이템 로드 대기: li 개수 증가 감시
            end_t = time.time() + timeout
            while time.time() < end_t:
                cur_count = li_count_under_ul(ul)
                if cur_count > prev_count:
                    prev_count = cur_count
                    break
                time.sleep(0.2)

            if debug:
                print(f"[DEBUG] scroll {i+1}/{scrolls} li_count={prev_count}", file=sys.stderr)

        ul = locate_ul(driver, timeout, css_ul, xpath_ul)
        li_elems = ul.find_elements(By.CSS_SELECTOR, "li")

        items: List[LiItem] = []
        for idx, li in enumerate(li_elems, start=1):
            items.append(
                LiItem(
                    idx=idx,
                    text=(li.text or "").strip(),
                    outer_html=li.get_attribute("outerHTML") or "",
                )
            )
        return items

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def save_jsonl(items: List[LiItem], out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def save_csv(items: List[LiItem], out_path: str) -> None:
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["idx", "text", "outer_html"])
        w.writeheader()
        for it in items:
            w.writerow(asdict(it))


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 쇼핑 랭킹(프로모션) 스크롤 크롤러")
    ap.add_argument("--url", default=DEFAULT_URL, help="기준 URL")
    ap.add_argument("--scrolls", type=int, default=5, help="스크롤 횟수(기본 5)")
    ap.add_argument("--wait-sec", type=float, default=0.9, help="스크롤 후 대기(초)")
    ap.add_argument("--timeout", type=float, default=12.0, help="요소 탐색/로딩 대기 타임아웃(초)")
    ap.add_argument("--css-ul", default=CSS_UL, help="UL CSS selector")
    ap.add_argument("--xpath-ul", default=XPATH_UL, help="UL XPath")
    ap.add_argument("--format", choices=("jsonl", "csv"), default="jsonl", help="출력 포맷")
    ap.add_argument("--out", default="", help="출력 파일 경로(미지정 시 자동)")
    ap.add_argument("--headless", action="store_true", help="헤드리스 모드")
    ap.add_argument("--window-size", default="1400,900", help="브라우저 창 크기, 예: 1400,900")
    ap.add_argument("--user-agent", default="", help="User-Agent 지정(선택)")
    ap.add_argument("--debug", action="store_true", help="디버그 로그 출력")
    args = ap.parse_args()

    items = crawl(
        url=args.url,
        css_ul=args.css_ul,
        xpath_ul=args.xpath_ul,
        scrolls=max(0, args.scrolls),
        wait_sec=max(0.0, args.wait_sec),
        timeout=max(1.0, args.timeout),
        headless=bool(args.headless),
        window_size=args.window_size,
        user_agent=(args.user_agent or None),
        debug=bool(args.debug),
    )

    if not args.out:
        args.out = f"naver_shopping_ranking_{args.scrolls}scroll.{args.format}"

    if args.format == "jsonl":
        save_jsonl(items, args.out)
    else:
        save_csv(items, args.out)

    print(f"OK: {len(items)} li items -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
