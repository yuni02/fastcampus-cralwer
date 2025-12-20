# Shared utilities for course_scraper spiders
from .credentials import get_credentials, get_db_config, get_kakao_credentials
from .db import (
    get_db_connection,
    db_connection,
    get_course_title_from_db,
    get_courses_to_recrawl,
    delete_lectures_for_courses,
    get_courses_for_crawling,
    get_manually_completed_course_ids,
)
from .kakao_login import KakaoLoginHelper
from .title_extractor import extract_course_title
from .paths import (
    get_screenshot_path,
    get_log_path,
    get_debug_path,
    get_output_path,
    BACKUP_DIR,
    SCREENSHOTS_DIR,
    LOGS_DIR,
    DEBUG_DIR,
    OUTPUT_DIR,
)
from .cookies import (
    save_cookies,
    load_cookies,
    delete_cookies,
    are_cookies_valid,
    apply_cookies_to_context,
    save_cookies_from_context,
)

__all__ = [
    'get_credentials',
    'get_db_config',
    'get_kakao_credentials',
    'get_db_connection',
    'db_connection',
    'get_course_title_from_db',
    'get_courses_to_recrawl',
    'delete_lectures_for_courses',
    'get_courses_for_crawling',
    'get_manually_completed_course_ids',
    'KakaoLoginHelper',
    'extract_course_title',
    'get_screenshot_path',
    'get_log_path',
    'get_debug_path',
    'get_output_path',
    'BACKUP_DIR',
    'SCREENSHOTS_DIR',
    'LOGS_DIR',
    'DEBUG_DIR',
    'OUTPUT_DIR',
    'save_cookies',
    'load_cookies',
    'delete_cookies',
    'are_cookies_valid',
    'apply_cookies_to_context',
    'save_cookies_from_context',
]
