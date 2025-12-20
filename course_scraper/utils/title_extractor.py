"""
Course title extraction utilities for FastCampus spiders
"""
import logging
from typing import Optional

from .db import get_course_title_from_db

logger = logging.getLogger(__name__)

# CSS selectors for finding course title on page
TITLE_SELECTORS = [
    '.classroom-sidebar-clip__header__title',
    '.classroom-header__title',
    '.course-title',
    'header h1',
    'h1.title',
    'h1'
]


async def extract_course_title(
    page,
    page_title: str,
    course_id: str,
    logger_instance=None
) -> str:
    """
    Extract course title using multiple methods

    Args:
        page: Playwright page object
        page_title: Page title from browser
        course_id: Course ID for fallback and DB lookup
        logger_instance: Optional logger for debug output

    Returns:
        Extracted course title or fallback value
    """
    log = logger_instance or logger
    course_title = None

    log.info(f"Page title for extraction: {page_title}")

    # Method 1: Extract from page title
    course_title = _extract_from_page_title(page_title, log)

    # Method 2: Extract from page elements
    if not course_title or len(course_title) < 5:
        course_title = await _extract_from_page_elements(page, log)

    # Method 3: Get from database
    if not course_title or len(course_title) < 5 or course_title.startswith('Course '):
        db_title = get_course_title_from_db(course_id, log)
        if db_title:
            course_title = db_title

    # Final fallback
    if not course_title or len(course_title) < 5:
        course_title = f'Course {course_id}'
        log.warning(f"Using fallback title: {course_title}")

    return course_title.strip()


def _extract_from_page_title(page_title: str, log) -> Optional[str]:
    """Extract course title from page title string"""
    if not page_title:
        return None

    # Format: "패스트캠퍼스 온라인 강의 - {제목}"
    if ' - ' in page_title:
        title = page_title.split(' - ', 1)[1].strip()
        log.info(f"Title from page title (split by ' - '): {title}")
        return title

    # Format: "{제목} | FastCampus"
    if '|' in page_title:
        title = page_title.split('|')[0].strip()
        log.info(f"Title from page title (split by '|'): {title}")
        return title

    return None


async def _extract_from_page_elements(page, log) -> Optional[str]:
    """Extract course title from page DOM elements"""
    if not page:
        return None

    try:
        for selector in TITLE_SELECTORS:
            try:
                title_elem = await page.query_selector(selector)
                if title_elem:
                    title_text = await title_elem.inner_text()
                    if title_text and len(title_text.strip()) >= 5:
                        title = title_text.strip()
                        log.info(f"Title from selector '{selector}': {title}")
                        return title
            except Exception:
                continue
    except Exception as e:
        log.warning(f"Could not extract title from page elements: {e}")

    return None


def extract_course_title_sync(
    page_title: str,
    course_id: str,
    logger_instance=None
) -> str:
    """
    Synchronous version of title extraction (without page element check)

    Args:
        page_title: Page title from browser
        course_id: Course ID for fallback and DB lookup
        logger_instance: Optional logger for debug output

    Returns:
        Extracted course title or fallback value
    """
    log = logger_instance or logger
    course_title = None

    # Method 1: Extract from page title
    course_title = _extract_from_page_title(page_title, log)

    # Method 2: Get from database
    if not course_title or len(course_title) < 5 or course_title.startswith('Course '):
        db_title = get_course_title_from_db(course_id, log)
        if db_title:
            course_title = db_title

    # Final fallback
    if not course_title or len(course_title) < 5:
        course_title = f'Course {course_id}'
        log.warning(f"Using fallback title: {course_title}")

    return course_title.strip()
