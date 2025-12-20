"""
Pydantic models for the Crawler API
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel


class JobStatus(str, Enum):
    """크롤링 작업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CrawlRequest(BaseModel):
    """크롤링 요청 모델"""
    spider: str = "fastcampus"
    url: Optional[str] = None
    course_ids: Optional[List[str]] = None
    output_file: Optional[str] = None


class CrawlResponse(BaseModel):
    """크롤링 시작 응답 모델"""
    job_id: str
    status: JobStatus
    message: str
    spider: str
    started_at: str


class JobStatusResponse(BaseModel):
    """작업 상태 조회 응답 모델"""
    job_id: str
    status: JobStatus
    spider: str
    started_at: str
    finished_at: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    output_file: Optional[str] = None


class SpiderInfo(BaseModel):
    """스파이더 정보 모델"""
    name: str
    description: str


class JobListItem(BaseModel):
    """작업 목록 아이템"""
    job_id: str
    status: JobStatus
    spider: str
    started_at: str
    finished_at: Optional[str] = None


class JobListResponse(BaseModel):
    """작업 목록 응답"""
    jobs: List[JobListItem]
    total: int
