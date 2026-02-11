
import json
import sys
import os
from datetime import datetime

# 설정
INPUT_FILE = "naver_section_101_headlines.jsonl"
OUTPUT_FILE = "naver_section_101_headlines.html"

def load_data(file_path):
    items = []
    if not os.path.exists(file_path):
        print(f"파일을 찾을 수 없습니다: {file_path}")
        return []
        
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items

def generate_html(items):


    card_template = """
        <div class="col">
            <div class="news-card">
                <div class="card-body">
                    <div class="news-meta">
                        <span class="badge-press">{press}</span>
                        <span>{rank}위</span>
                    </div>
                    <h5 class="news-title">
                        <a href="{url}" target="_blank">{title}</a>
                    </h5>
                    <p class="news-meta">{datetime}</p>
                    <p class="news-lede">{lede}</p>
                    <a href="{url}" target="_blank" class="btn btn-sm btn-outline-primary w-100 mt-2">기사 원문 보기</a>
                </div>
            </div>
        </div>
    """

    content_html = ""
    for item in items:
        content_html += card_template.format(
            rank=item.get('rank', '-'),
            press=item.get('press', '알수없음') or "언론사",
            title=item.get('title', '제목 없음'),
            url=item.get('url', '#'),
            datetime=item.get('datetime', '') or "",
            lede=item.get('lede', '') or "내용 요약 없음"
        )

    full_html = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>네이버 경제 뉴스 크롤링 결과</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ background-color: #f8f9fa; padding: 20px; }}
        .news-card {{ 
            background: white; 
            border-radius: 12px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
            margin-bottom: 20px; 
            transition: transform 0.2s;
            height: 100%;
        }}
        .news-card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 12px rgba(0,0,0,0.1); }}
        .card-body {{ padding: 1.5rem; }}
        .news-title {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; color: #333; }}
        .news-title a {{ text-decoration: none; color: inherit; }}
        .news-meta {{ font-size: 0.85rem; color: #6c757d; margin-bottom: 1rem; }}
        .news-lede {{ font-size: 0.95rem; color: #555; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
        .badge-press {{ background-color: #03c75a; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 5px; }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        .updated-time {{ font-size: 0.9rem; color: #888; margin-top: 10px; }}
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1 class="display-6 fw-bold">📉 네이버 경제 뉴스 모니터링</h1>
        <p class="updated-time">생성 시간: {timestamp}</p>
        <p class="lead">총 {total_count}개의 기사가 수집되었습니다.</p>
    </div>

    <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">
        {content}
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
    """.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_count=len(items),
        content=content_html
    )
    
    return full_html
    
    return full_html

def main():
    print(f"[{INPUT_FILE}] 데이터를 읽고 있습니다...")
    items = load_data(INPUT_FILE)
    
    if not items:
        print("데이터가 없습니다. 크롤링을 먼저 실행해주세요!")
        return

    print(f"총 {len(items)}개의 데이터를 HTML로 변환합니다...")
    html_content = generate_html(items)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"변환 완료! 아래 파일을 브라우저에서 여세요: \n{os.path.abspath(OUTPUT_FILE)}")

if __name__ == "__main__":
    main()
