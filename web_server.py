
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import json
import os
import subprocess
import sys

# 앱 초기화
app = FastAPI()

# 템플릿 설정 (간단히 HTML 문자열 반환으로 대체할 수도 있지만, 확장성을 위해)
# 여기서는 파일 생성 없이 직접 HTML을 반환하는 방식으로 구현합니다.

DATA_FILE = "naver_section_101_visual.jsonl"
CRAWLER_SCRIPT = "naver_section_101_crawler_visual.py"

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>네이버 경제 뉴스 라이브 모니터링</title>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; padding: 20px; }
        .news-card { 
            background: white; 
            border-radius: 12px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.05); 
            margin-bottom: 20px; 
            transition: transform 0.2s;
            height: 100%;
        }
        .news-card:hover { transform: translateY(-3px); box-shadow: 0 8px 12px rgba(0,0,0,0.1); }
        .card-body { padding: 1.5rem; }
        .news-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.5rem; color: #333; }
        .news-title a { text-decoration: none; color: inherit; }
        .news-meta { font-size: 0.85rem; color: #6c757d; margin-bottom: 1rem; }
        .news-lede { font-size: 0.95rem; color: #555; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
        .badge-press { background-color: #03c75a; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 5px; }
        .header { text-align: center; margin-bottom: 40px; }
        .btn-crawl { font-size: 1.2rem; padding: 10px 30px; border-radius: 50px; }
        #loading { display: none; margin-top: 20px; }
    </style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1 class="display-6 fw-bold">📉 네이버 경제 뉴스 라이브</h1>
        <p class="lead">실시간으로 뉴스를 크롤링하고 확인하세요.</p>
        <button id="btn-run" class="btn btn-primary btn-crawl" onclick="runCrawling()">
            🚀 최신 뉴스 가져오기 (크롤링 시작)
        </button>
        <div id="loading" class="alert alert-info">
            <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
            크롤링 중입니다... 브라우저가 열리면 잠시만 기다려주세요! (약 5~10초)
        </div>
    </div>

    <div id="news-container" class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-4">
        <!-- 뉴스 카드가 여기 들어갑니다 -->
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    async function loadData() {
        try {
            const response = await fetch('/api/data');
            const data = await response.json();
            const container = document.getElementById('news-container');
            container.innerHTML = '';

            if (data.length === 0) {
                container.innerHTML = '<p class="text-center w-100">데이터가 없습니다. 크롤링을 실행해주세요!</p>';
                return;
            }

            data.forEach((item, index) => {
                const card = `
                    <div class="col">
                        <div class="news-card">
                            <div class="card-body">
                                <div class="news-meta">
                                    <span class="badge-press">${item.press || '언론사'}</span>
                                    <span>${index + 1}위</span>
                                </div>
                                <h5 class="news-title">
                                    <a href="${item.url}" target="_blank">${item.title}</a>
                                </h5>
                                <p class="news-meta">${item.datetime || ''}</p>
                                <p class="news-lede">${item.lede || '내용 요약 없음'}</p>
                                <a href="${item.url}" target="_blank" class="btn btn-sm btn-outline-primary w-100 mt-2">기사 원문 보기</a>
                            </div>
                        </div>
                    </div>
                `;
                container.innerHTML += card;
            });
        } catch (error) {
            console.error('Error loading data:', error);
        }
    }

    async function runCrawling() {
        const btn = document.getElementById('btn-run');
        const loading = document.getElementById('loading');
        
        btn.disabled = true;
        loading.style.display = 'block';

        try {
            const response = await fetch('/api/crawl', { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                alert('크롤링 완료! 최신 데이터를 불러옵니다.');
                loadData();
            } else {
                alert('크롤링 실패: ' + result.error);
            }
        } catch (error) {
            alert('서버 오류 발생');
        } finally {
            btn.disabled = false;
            loading.style.display = 'none';
        }
    }

    // 페이지 로드 시 데이터 불러오기
    window.onload = loadData;
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_CONTENT

@app.get("/api/data")
async def get_data():
    items = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return items

@app.post("/api/crawl")
async def run_crawler():
    try:
        # 비주얼 크롤러 실행 (브라우저가 뜸)
        # python 실행 경로를 현재 가상환경으로 지정
        python_exe = sys.executable
        result = subprocess.run(
            [python_exe, CRAWLER_SCRIPT, "--pages", "1", "--sleep", "1"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            return {"success": True, "message": "Crawling finished"}
        else:
            return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
