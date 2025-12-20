"""
API Routes for the Crawler API
"""
import os
import json
import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, BackgroundTasks

from .models import (
    CrawlRequest,
    CrawlResponse,
    JobStatusResponse,
    SpiderInfo,
    JobListResponse,
    JobListItem,
    JobStatus,
)
from .spider_runner import (
    AVAILABLE_SPIDERS,
    PROJECT_ROOT,
    run_spider,
    cancel_job,
    get_job,
    create_job,
    list_all_jobs,
    crawl_jobs,
)

router = APIRouter(prefix="/api", tags=["crawler"])


@router.get("/spiders", response_model=List[SpiderInfo])
async def list_spiders():
    """사용 가능한 스파이더 목록 조회"""
    return [
        SpiderInfo(name=name, description=desc)
        for name, desc in AVAILABLE_SPIDERS.items()
    ]


@router.post("/crawl", response_model=CrawlResponse)
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
        output_file = f"crawl_{request.spider}_{job_id}.json"

    # 작업 생성
    create_job(
        job_id=job_id,
        spider=request.spider,
        url=request.url,
        course_ids=request.course_ids,
        output_file=output_file,
        started_at=started_at
    )

    # 백그라운드에서 실행
    background_tasks.add_task(
        run_spider,
        job_id,
        request.spider,
        request.url,
        request.course_ids,
        output_file
    )

    return CrawlResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message=f"크롤링 작업이 시작되었습니다. job_id: {job_id}",
        spider=request.spider,
        started_at=started_at
    )


@router.get("/crawl/{job_id}", response_model=JobStatusResponse)
async def get_crawl_status(job_id: str):
    """크롤링 작업 상태 조회"""
    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

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


@router.delete("/crawl/{job_id}")
async def cancel_crawl(job_id: str):
    """크롤링 작업 취소"""
    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job['status']}"
        )

    cancel_job(job_id)

    job["status"] = JobStatus.CANCELLED
    job["finished_at"] = datetime.now().isoformat()

    return {"message": f"Job {job_id} cancelled", "status": JobStatus.CANCELLED}


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs():
    """모든 크롤링 작업 목록 조회"""
    jobs = list_all_jobs()

    return JobListResponse(
        jobs=[JobListItem(**job) for job in jobs],
        total=len(jobs)
    )


@router.get("/crawl/{job_id}/result")
async def get_crawl_result(job_id: str):
    """크롤링 결과 파일 내용 조회"""
    job = get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed yet. Current status: {job['status']}"
        )

    output_file = job.get("output_file")
    if not output_file:
        raise HTTPException(status_code=404, detail="No output file specified")

    file_path = os.path.join(PROJECT_ROOT, "output", output_file)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Output file not found: {output_file}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"file": output_file, "data": data}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse output file: {e}")
