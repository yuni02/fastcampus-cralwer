"""
FastAPI 서버 - Next.js에서 크롤링을 요청할 수 있는 API 서버

실행 방법:
    uvicorn api.main:app --reload --port 8000

API 엔드포인트:
    GET  /api/spiders          - 사용 가능한 스파이더 목록
    POST /api/crawl            - 크롤링 시작
    GET  /api/crawl/{job_id}   - 크롤링 상태 확인
    GET  /api/jobs             - 모든 작업 목록
    DELETE /api/crawl/{job_id} - 크롤링 작업 취소
    GET  /api/crawl/{job_id}/result - 크롤링 결과 조회
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .spider_runner import AVAILABLE_SPIDERS

app = FastAPI(
    title="Course Scraper API",
    description="패스트캠퍼스 강의 크롤링 API 서버",
    version="1.0.0"
)

# CORS 설정 (Next.js에서 호출 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://codeninjax.gonetis.com:3000",
        "*",  # 개발 편의를 위해 모든 origin 허용
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(router)


@app.get("/")
async def root():
    """API 루트"""
    return {
        "message": "Course Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "spiders": "/api/spiders",
            "crawl": "/api/crawl",
            "jobs": "/api/jobs"
        },
        "available_spiders": list(AVAILABLE_SPIDERS.keys())
    }


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy"}


# 서버 직접 실행 시
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
