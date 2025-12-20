"""
Spider runner - 백그라운드에서 Scrapy 스파이더 실행
"""
import os
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Any

from .models import JobStatus

# 프로젝트 루트 (api 폴더의 상위)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 작업 저장소
crawl_jobs: Dict[str, Dict[str, Any]] = {}
job_processes: Dict[str, subprocess.Popen] = {}

# 사용 가능한 스파이더 목록
AVAILABLE_SPIDERS = {
    "fastcampus": "패스트캠퍼스 전체 강의 크롤링 (로그인 필요, 모든 수강중 강의)",
    "fastcampus_daily": "패스트캠퍼스 일일 업데이트 크롤링 (DB에 저장된 URL 기반)",
    "fastcampus_lectures": "패스트캠퍼스 특정 강의 목차 크롤링 (-a course_id=ID)",
    "fastcampus_discover": "패스트캠퍼스 URL 발견 크롤링 (새 강의 탐색)",
    "fastcampus_recrawl": "패스트캠퍼스 재크롤링 (시간 차이 나는 강의)",
}


def run_spider(
    job_id: str,
    spider_name: str,
    url: Optional[str],
    course_ids: Optional[List[str]],
    output_file: Optional[str]
):
    """백그라운드에서 스파이더 실행"""
    crawl_jobs[job_id]["status"] = JobStatus.RUNNING

    try:
        # scrapy 명령어 구성
        cmd = ["scrapy", "crawl", spider_name]

        # URL이 지정된 경우
        if url:
            cmd.extend(["-a", f"url={url}"])

        # course_ids가 지정된 경우
        if course_ids:
            cmd.extend(["-a", f"course_ids={','.join(course_ids)}"])

        # 출력 파일이 지정된 경우
        if output_file:
            output_path = os.path.join(PROJECT_ROOT, "output", output_file)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cmd.extend(["-O", output_path])

        # 프로세스 실행
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


def cancel_job(job_id: str) -> bool:
    """작업 취소"""
    if job_id in job_processes:
        process = job_processes[job_id]
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        del job_processes[job_id]
        return True
    return False


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """작업 조회"""
    return crawl_jobs.get(job_id)


def create_job(
    job_id: str,
    spider: str,
    url: Optional[str],
    course_ids: Optional[List[str]],
    output_file: Optional[str],
    started_at: str
) -> Dict[str, Any]:
    """작업 생성"""
    job = {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "spider": spider,
        "url": url,
        "course_ids": course_ids,
        "started_at": started_at,
        "finished_at": None,
        "output": None,
        "error": None,
        "output_file": output_file
    }
    crawl_jobs[job_id] = job
    return job


def list_all_jobs() -> List[Dict[str, Any]]:
    """모든 작업 목록"""
    jobs = []
    for job_id, job in crawl_jobs.items():
        jobs.append({
            "job_id": job["job_id"],
            "status": job["status"],
            "spider": job["spider"],
            "started_at": job["started_at"],
            "finished_at": job.get("finished_at")
        })
    jobs.sort(key=lambda x: x["started_at"], reverse=True)
    return jobs
