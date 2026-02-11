#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naver News(경제 섹션 101) 헤드라인 리스트 크롤러

요구사항
- ul(id="_SECTION_HEADLINE_LIST_4aiik") 아래의 li 태그 전부 수집
- li class가 "sa_item _SECTION_HEADLINE" 또는 "sa_item _SECTION_HEADLINE is_blind" 인 항목만 대상으로 파싱

주의
- 사이트의 robots.txt / 이용약관 / 트래픽 정책을 준수하세요.
- 과도한 호출을 피하기 위해 기본적으로 페이지 간 sleep을 둡니다.

의존성
- requests
- beautifulsoup4

참고(공식 문서):
- https://requests.readthedocs.io/
- https://www.crummy.com/software/BeautifulSoup/bs4/doc/
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_SECTION_URL = "https://news.naver.com/section/101"
DEFAULT_LIST_ID = "_SECTION_HEADLINE_LIST_4aiik"


@dataclass
class HeadlineItem:
    title: str
    url: str
    press: Optional[str] = None
    datetime: Optional[str] = None
    lede: Optional[str] = None
    is_blind: bool = False
    rank: Optional[int] = None  # 리스트 내 순번(1부터)


def build_session(timeout: float = 10.0) -> requests.Session:
    """
    기본 UA/헤더 + 재시도 정책을 가진 requests.Session 생성
    """
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://news.naver.com/",
            "Connection": "keep-alive",
        }
    )

    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    # timeout은 request 호출에서 사용
    s._timeout = timeout  # type: ignore[attr-defined]
    return s


def with_page(url: str, page: int) -> str:
    """
    section URL에 page 파라미터를 설정(또는 교체)하여 반환
    """
    if page <= 1:
        return url

    p = urlparse(url)
    qs = parse_qs(p.query)
    qs["page"] = [str(page)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))


def fetch_html(session: requests.Session, url: str) -> str:
    timeout = getattr(session, "_timeout", 10.0)
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    # 네이버는 보통 utf-8
    if not r.encoding:
        r.encoding = "utf-8"
    return r.text


def pick_ul(soup: BeautifulSoup, list_id: str) -> Optional[object]:
    """
    1) 사용자가 준 list_id로 ul 찾기
    2) 없으면 id가 '_SECTION_HEADLINE_LIST_'로 시작하는 ul을 fallback
    """
    ul = soup.find(id=list_id)
    if ul:
        return ul

    # fallback: id prefix 기반
    for candidate in soup.select('ul[id^="_SECTION_HEADLINE_LIST_"]'):
        return candidate
    return None


def iter_target_lis(ul) -> Iterable[object]:
    """
    ul 아래에서 class에 sa_item + _SECTION_HEADLINE 이 포함된 li만 반환
    (is_blind 추가 여부는 무관)
    """
    # CSS selector: li.sa_item._SECTION_HEADLINE 은 is_blind 포함 항목도 매칭됨
    for li in ul.select("li.sa_item._SECTION_HEADLINE"):
        yield li


def extract_text(el) -> Optional[str]:
    if not el:
        return None
    txt = el.get_text(" ", strip=True)
    return txt or None


def parse_item(li, base_url: str) -> Optional[HeadlineItem]:
    """
    li 1개에서 필요한 필드들을 최대한 견고하게 추출
    (DOM 구조 변경에 대비해 여러 selector를 순차적으로 시도)
    """
    classes = li.get("class", []) or []
    is_blind = "is_blind" in classes

    # 링크/제목
    link = (
        li.select_one("a.sa_text_title[href]")
        or li.select_one("a[href]")
    )
    if not link or not link.get("href"):
        return None

    title = extract_text(link) or ""
    url = urljoin(base_url, link.get("href"))

    # 언론사/시간/요약 (여러 후보 selector)
    press = (
        extract_text(li.select_one(".sa_text_press"))
        or extract_text(li.select_one(".sa_text_press em"))
        or extract_text(li.select_one(".sa_text_press span"))
    )

    dt = (
        extract_text(li.select_one(".sa_text_datetime"))
        or extract_text(li.select_one("._SECTION_HEADLINE_LIST_TIME"))
        or extract_text(li.select_one("time"))
    )

    lede = (
        extract_text(li.select_one(".sa_text_lede"))
        or extract_text(li.select_one(".sa_text_lede_text"))
    )

    return HeadlineItem(
        title=title,
        url=url,
        press=press,
        datetime=dt,
        lede=lede,
        is_blind=is_blind,
    )


def crawl(section_url: str, list_id: str, pages: int, sleep: float, timeout: float, debug: bool) -> list[HeadlineItem]:
    session = build_session(timeout=timeout)
    all_items: list[HeadlineItem] = []

    for page in range(1, pages + 1):
        url = with_page(section_url, page)
        html = fetch_html(session, url)
        soup = BeautifulSoup(html, "html.parser")

        ul = pick_ul(soup, list_id)
        if not ul:
            raise RuntimeError(
                f"헤드라인 UL을 찾지 못했습니다. list_id={list_id}. "
                "페이지 DOM이 바뀌었을 수 있습니다. (fallback도 실패)"
            )

        lis = list(iter_target_lis(ul))
        if debug:
            print(f"[DEBUG] page={page} url={url} li_count={len(lis)}", file=sys.stderr)

        for li in lis:
            item = parse_item(li, base_url=section_url)
            if not item:
                continue
            item.rank = len(all_items) + 1
            all_items.append(item)

        if page < pages and sleep > 0:
            time.sleep(sleep)

    return all_items


def save_jsonl(items: list[HeadlineItem], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(asdict(it), ensure_ascii=False) + "\n")


def save_csv(items: list[HeadlineItem], path: str) -> None:
    fields = ["rank", "title", "url", "press", "datetime", "lede", "is_blind"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for it in items:
            w.writerow({k: getattr(it, k) for k in fields})


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 뉴스(섹션) 헤드라인 크롤러")
    ap.add_argument("--url", default=DEFAULT_SECTION_URL, help="섹션 URL (기본: 경제 101)")
    ap.add_argument("--list-id", default=DEFAULT_LIST_ID, help="헤드라인 UL id (기본: _SECTION_HEADLINE_LIST_4aiik)")
    ap.add_argument("--pages", type=int, default=1, help="크롤링할 페이지 수")
    ap.add_argument("--sleep", type=float, default=0.8, help="페이지 간 대기(초)")
    ap.add_argument("--timeout", type=float, default=10.0, help="요청 타임아웃(초)")
    ap.add_argument("--format", choices=("jsonl", "csv"), default="jsonl", help="저장 포맷")
    ap.add_argument("--out", default="", help="출력 파일 경로 (미지정 시 자동 생성)")
    ap.add_argument("--debug", action="store_true", help="디버그 로그 출력")
    args = ap.parse_args()

    items = crawl(
        section_url=args.url,
        list_id=args.list_id,
        pages=max(1, args.pages),
        sleep=max(0.0, args.sleep),
        timeout=max(1.0, args.timeout),
        debug=args.debug,
    )

    if not args.out:
        args.out = f"naver_section_101_headlines.{args.format}"

    if args.format == "jsonl":
        save_jsonl(items, args.out)
    else:
        save_csv(items, args.out)

    print(f"OK: {len(items)} items -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
