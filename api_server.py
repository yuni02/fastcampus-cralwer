"""
FastAPI 서버 - Next.js에서 크롤링을 요청할 수 있는 API 서버

실행 방법:
    uvicorn api_server:app --reload --port 8000

API 엔드포인트:
    GET  /api/spiders          - 사용 가능한 스파이더 목록
    POST /api/crawl            - 크롤링 시작
    GET  /api/crawl/{job_id}   - 크롤링 상태 확인
    GET  /api/jobs             - 모든 작업 목록
    DELETE /api/crawl/{job_id} - 크롤링 작업 취소
"""

import os
import sys
import uuid
import subprocess
import threading
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 프로젝트 루트 설정
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 크롤링 작업 상태
class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 작업 저장소
crawl_jobs: Dict[str, Dict[str, Any]] = {}
job_processes: Dict[str, subprocess.Popen] = {}


# 요청/응답 모델
class CrawlRequest(BaseModel):
    spider: str = "fastcampus"
    url: Optional[str] = None  # 특정 URL만 크롤링할 때 사용
    course_ids: Optional[List[str]] = None  # 크롤링할 강의 ID 목록 (예: ["214390", "246575"])
    output_file: Optional[str] = None  # 결과 저장 파일


class CrawlResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    spider: str
    started_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    spider: str
    started_at: str
    finished_at: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    output_file: Optional[str] = None


class SpiderInfo(BaseModel):
    name: str
    description: str


# 사용 가능한 스파이더 목록
AVAILABLE_SPIDERS = {
    "fastcampus": "패스트캠퍼스 전체 강의 크롤링 (로그인 필요, 모든 수강중 강의)",
    "fastcampus_daily": "패스트캠퍼스 일일 업데이트 크롤링",
    "fastcampus_lectures": "패스트캠퍼스 강의 목차 크롤링",
    "fastcampus_discover": "패스트캠퍼스 URL 발견 크롤링",
    "fastcampus_recrawl": "패스트캠퍼스 재크롤링",
    "inflearn": "인프런 강의 크롤링",
    "udemy": "유데미 강의 크롤링",
}


def run_spider(job_id: str, spider_name: str, url: Optional[str], course_ids: Optional[List[str]], output_file: Optional[str]):
    """백그라운드에서 스파이더 실행"""
    crawl_jobs[job_id]["status"] = JobStatus.RUNNING

    try:
        # scrapy 명령어 구성
        cmd = ["scrapy", "crawl", spider_name]

        # URL이 지정된 경우 인자로 전달
        if url:
            cmd.extend(["-a", f"url={url}"])

        # course_ids가 지정된 경우 인자로 전달 (쉼표로 구분)
        if course_ids:
            cmd.extend(["-a", f"course_ids={','.join(course_ids)}"])

        # 출력 파일이 지정된 경우
        if output_file:
            cmd.extend(["-O", output_file])

        # 작업 디렉토리 설정
        process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        job_processes[job_id] = process

        # 출력 수집
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            if line:
                output_lines.append(line.rstrip())
                # 최근 100줄만 유지
                if len(output_lines) > 100:
                    output_lines = output_lines[-100:]
                crawl_jobs[job_id]["output"] = "\n".join(output_lines)

        process.wait()

        # 완료 처리
        if process.returncode == 0:
            crawl_jobs[job_id]["status"] = JobStatus.COMPLETED
        else:
            crawl_jobs[job_id]["status"] = JobStatus.FAILED
            crawl_jobs[job_id]["error"] = f"Process exited with code {process.returncode}"

    except Exception as e:
        crawl_jobs[job_id]["status"] = JobStatus.FAILED
        crawl_jobs[job_id]["error"] = str(e)

    finally:
        crawl_jobs[job_id]["finished_at"] = datetime.now().isoformat()
        if job_id in job_processes:
            del job_processes[job_id]


@app.get("/")
async def root():
    """API 루트"""
    return {
        "message": "Course Scraper API",
        "docs": "/docs",
        "endpoints": {
            "spiders": "/api/spiders",
            "crawl": "/api/crawl",
            "jobs": "/api/jobs"
        }
    }


@app.get("/api/spiders", response_model=List[SpiderInfo])
async def list_spiders():
    """사용 가능한 스파이더 목록 조회"""
    return [
        SpiderInfo(name=name, description=desc)
        for name, desc in AVAILABLE_SPIDERS.items()
    ]


@app.post("/api/crawl", response_model=CrawlResponse)
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """크롤링 시작"""

    # 스파이더 유효성 검사
    if request.spider not in AVAILABLE_SPIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown spider: {request.spider}. Available: {list(AVAILABLE_SPIDERS.keys())}"
        )

    # 작업 ID 생성
    job_id = str(uuid.uuid4())[:8]
    started_at = datetime.now().isoformat()

    # 출력 파일 설정
    output_file = request.output_file
    if not output_file:
        output_file = f"output_{request.spider}_{job_id}.json"

    # 작업 정보 저장
    crawl_jobs[job_id] = {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "spider": request.spider,
        "url": request.url,
        "course_ids": request.course_ids,
        "started_at": started_at,
        "finished_at": None,
        "output": None,
        "error": None,
        "output_file": output_file
    }

    # 백그라운드에서 실행
    background_tasks.add_task(run_spider, job_id, request.spider, request.url, request.course_ids, output_file)

    return CrawlResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message=f"크롤링 작업이 시작되었습니다. job_id: {job_id}",
        spider=request.spider,
        started_at=started_at
    )


@app.get("/api/crawl/{job_id}", response_model=JobStatusResponse)
async def get_crawl_status(job_id: str):
    """크롤링 작업 상태 조회"""

    if job_id not in crawl_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job = crawl_jobs[job_id]

    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        spider=job["spider"],
        started_at=job["started_at"],
        finished_at=job.get("finished_at"),
        output=job.get("output"),
        error=job.get("error"),
        output_file=job.get("output_file")
    )


@app.delete("/api/crawl/{job_id}")
async def cancel_crawl(job_id: str):
    """크롤링 작업 취소"""

    if job_id not in crawl_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job = crawl_jobs[job_id]

    if job["status"] not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job['status']}"
        )

    # 프로세스 종료
    if job_id in job_processes:
        process = job_processes[job_id]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        del job_processes[job_id]

    job["status"] = JobStatus.CANCELLED
    job["finished_at"] = datetime.now().isoformat()

    return {"message": f"Job {job_id} cancelled", "status": JobStatus.CANCELLED}


@app.get("/api/jobs")
async def list_jobs():
    """모든 크롤링 작업 목록 조회"""

    jobs = []
    for job_id, job in crawl_jobs.items():
        jobs.append({
            "job_id": job["job_id"],
            "status": job["status"],
            "spider": job["spider"],
            "started_at": job["started_at"],
            "finished_at": job.get("finished_at")
        })

    # 최신순 정렬
    jobs.sort(key=lambda x: x["started_at"], reverse=True)

    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/crawl/{job_id}/result")
async def get_crawl_result(job_id: str):
    """크롤링 결과 파일 내용 조회"""

    if job_id not in crawl_jobs:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job = crawl_jobs[job_id]

    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed yet. Current status: {job['status']}"
        )

    output_file = job.get("output_file")
    if not output_file:
        raise HTTPException(status_code=404, detail="No output file specified")

    file_path = os.path.join(PROJECT_ROOT, output_file)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Output file not found: {output_file}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"file": output_file, "data": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse output file: {e}")


# 서버 직접 실행 시
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
