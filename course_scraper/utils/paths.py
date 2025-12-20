"""
Path utilities for saving screenshots, logs, and debug files to backup folder
"""
import os
from datetime import datetime

# 프로젝트 루트 경로 (course_scraper/course_scraper/utils -> course_scraper)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Backup 폴더 경로
BACKUP_DIR = os.path.join(PROJECT_ROOT, 'backup')
SCREENSHOTS_DIR = os.path.join(BACKUP_DIR, 'screenshots')
LOGS_DIR = os.path.join(BACKUP_DIR, 'logs')
DEBUG_DIR = os.path.join(BACKUP_DIR, 'debug')
SQL_DIR = os.path.join(BACKUP_DIR, 'sql')

# Output 폴더 경로
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')


def ensure_backup_dirs():
    """Backup 폴더들이 존재하는지 확인하고 없으면 생성"""
    for dir_path in [BACKUP_DIR, SCREENSHOTS_DIR, LOGS_DIR, DEBUG_DIR, SQL_DIR, OUTPUT_DIR]:
        os.makedirs(dir_path, exist_ok=True)


def get_screenshot_path(name: str, with_timestamp: bool = False) -> str:
    """
    스크린샷 저장 경로 반환

    Args:
        name: 파일명 (확장자 없이)
        with_timestamp: True면 파일명에 타임스탬프 추가

    Returns:
        전체 경로
    """
    ensure_backup_dirs()

    if with_timestamp:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name}_{timestamp}.png"
    else:
        filename = f"{name}.png" if not name.endswith('.png') else name

    return os.path.join(SCREENSHOTS_DIR, filename)


def get_log_path(name: str) -> str:
    """
    로그 파일 저장 경로 반환

    Args:
        name: 파일명

    Returns:
        전체 경로
    """
    ensure_backup_dirs()
    filename = f"{name}.log" if not name.endswith('.log') else name
    return os.path.join(LOGS_DIR, filename)


def get_debug_path(name: str, ext: str = 'html') -> str:
    """
    디버그 파일 저장 경로 반환

    Args:
        name: 파일명
        ext: 확장자 (기본: html)

    Returns:
        전체 경로
    """
    ensure_backup_dirs()
    if not name.endswith(f'.{ext}'):
        filename = f"{name}.{ext}"
    else:
        filename = name
    return os.path.join(DEBUG_DIR, filename)


def get_output_path(name: str) -> str:
    """
    크롤링 결과 출력 파일 저장 경로 반환

    Args:
        name: 파일명

    Returns:
        전체 경로
    """
    ensure_backup_dirs()
    return os.path.join(OUTPUT_DIR, name)
