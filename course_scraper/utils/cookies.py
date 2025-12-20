"""
Cookie management for maintaining login sessions across spider runs
"""
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from .paths import BACKUP_DIR

logger = logging.getLogger(__name__)

# 쿠키 파일 경로
COOKIES_FILE = os.path.join(BACKUP_DIR, 'fastcampus_cookies.json')

# 쿠키 유효 시간 (기본 24시간)
COOKIE_VALIDITY_HOURS = 24


def save_cookies(cookies: List[Dict[str, Any]], logger_instance=None) -> bool:
    """
    쿠키를 파일에 저장

    Args:
        cookies: Playwright에서 가져온 쿠키 목록
        logger_instance: 로거 인스턴스

    Returns:
        저장 성공 여부
    """
    log = logger_instance or logger

    try:
        os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)

        cookie_data = {
            'saved_at': datetime.now().isoformat(),
            'cookies': cookies
        }

        with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookie_data, f, ensure_ascii=False, indent=2)

        log.info(f"Saved {len(cookies)} cookies to {COOKIES_FILE}")
        return True

    except Exception as e:
        log.error(f"Failed to save cookies: {e}")
        return False


def load_cookies(logger_instance=None) -> Optional[List[Dict[str, Any]]]:
    """
    저장된 쿠키 불러오기

    Args:
        logger_instance: 로거 인스턴스

    Returns:
        쿠키 목록 또는 None (없거나 만료된 경우)
    """
    log = logger_instance or logger

    if not os.path.exists(COOKIES_FILE):
        log.info("No saved cookies found")
        return None

    try:
        with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
            cookie_data = json.load(f)

        saved_at = datetime.fromisoformat(cookie_data['saved_at'])
        age_hours = (datetime.now() - saved_at).total_seconds() / 3600

        if age_hours > COOKIE_VALIDITY_HOURS:
            log.info(f"Cookies expired (saved {age_hours:.1f} hours ago)")
            delete_cookies(log)
            return None

        cookies = cookie_data['cookies']
        log.info(f"Loaded {len(cookies)} cookies (saved {age_hours:.1f} hours ago)")
        return cookies

    except Exception as e:
        log.error(f"Failed to load cookies: {e}")
        return None


def delete_cookies(logger_instance=None) -> bool:
    """
    저장된 쿠키 삭제

    Args:
        logger_instance: 로거 인스턴스

    Returns:
        삭제 성공 여부
    """
    log = logger_instance or logger

    try:
        if os.path.exists(COOKIES_FILE):
            os.remove(COOKIES_FILE)
            log.info("Deleted saved cookies")
        return True
    except Exception as e:
        log.error(f"Failed to delete cookies: {e}")
        return False


def are_cookies_valid(logger_instance=None) -> bool:
    """
    저장된 쿠키가 유효한지 확인

    Args:
        logger_instance: 로거 인스턴스

    Returns:
        쿠키가 존재하고 유효한지 여부
    """
    cookies = load_cookies(logger_instance)
    return cookies is not None and len(cookies) > 0


async def apply_cookies_to_context(context, logger_instance=None) -> bool:
    """
    저장된 쿠키를 Playwright 컨텍스트에 적용

    Args:
        context: Playwright browser context
        logger_instance: 로거 인스턴스

    Returns:
        적용 성공 여부
    """
    log = logger_instance or logger

    cookies = load_cookies(log)
    if not cookies:
        return False

    try:
        await context.add_cookies(cookies)
        log.info(f"Applied {len(cookies)} cookies to browser context")
        return True
    except Exception as e:
        log.error(f"Failed to apply cookies: {e}")
        return False


async def save_cookies_from_context(context, logger_instance=None) -> bool:
    """
    Playwright 컨텍스트에서 쿠키 추출 후 저장

    Args:
        context: Playwright browser context
        logger_instance: 로거 인스턴스

    Returns:
        저장 성공 여부
    """
    log = logger_instance or logger

    try:
        cookies = await context.cookies()
        return save_cookies(cookies, log)
    except Exception as e:
        log.error(f"Failed to get cookies from context: {e}")
        return False
