"""
Database utilities for course_scraper
"""
import pymysql
import logging
from typing import Optional, Any
from contextlib import contextmanager

from .credentials import get_db_config

logger = logging.getLogger(__name__)


def get_db_connection(cursorclass=None):
    """
    Get a database connection

    Args:
        cursorclass: Optional cursor class (e.g., pymysql.cursors.DictCursor)

    Returns:
        pymysql connection object
    """
    config = get_db_config()

    kwargs = {
        'host': config['host'],
        'port': config['port'],
        'user': config['user'],
        'password': config['password'],
        'database': config['database'],
        'charset': 'utf8mb4',
    }

    if cursorclass:
        kwargs['cursorclass'] = cursorclass

    return pymysql.connect(**kwargs)


@contextmanager
def db_connection(cursorclass=None):
    """
    Context manager for database connection

    Usage:
        with db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM courses")
    """
    conn = get_db_connection(cursorclass)
    try:
        yield conn
    finally:
        conn.close()


def get_course_title_from_db(course_id: str, logger_instance=None) -> Optional[str]:
    """
    Get course title from database

    Args:
        course_id: The course ID to look up
        logger_instance: Optional logger for debug output

    Returns:
        Course title if found and valid, None otherwise
    """
    log = logger_instance or logger

    try:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT course_title FROM courses WHERE course_id = %s",
                    (course_id,)
                )
                row = cursor.fetchone()

                if row and row[0] and not row[0].startswith('Course '):
                    log.info(f"Title from DB: {row[0]}")
                    return row[0]

    except Exception as e:
        log.warning(f"Could not get title from DB: {e}")

    return None


def get_courses_to_recrawl(time_diff_percent: float = 0.1, logger_instance=None) -> list:
    """
    Get courses where lecture time difference exceeds threshold

    Args:
        time_diff_percent: Threshold for time difference (default 10%)
        logger_instance: Optional logger for debug output

    Returns:
        List of dicts with course_id, url, title, expected_time, actual_time, diff
    """
    log = logger_instance or logger

    try:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        c.course_id,
                        c.url,
                        c.course_title,
                        c.total_lecture_time as expected_time,
                        COALESCE(SUM(l.lecture_time), 0) as actual_time,
                        c.total_lecture_time - COALESCE(SUM(l.lecture_time), 0) as diff
                    FROM courses c
                    LEFT JOIN lectures l ON c.course_id = l.course_id
                    WHERE c.url IS NOT NULL AND c.total_lecture_time > 0
                    GROUP BY c.course_id, c.course_title, c.total_lecture_time, c.url
                    HAVING ABS(c.total_lecture_time - COALESCE(SUM(l.lecture_time), 0))
                           > c.total_lecture_time * %s
                    ORDER BY diff DESC
                """, (time_diff_percent,))

                rows = cursor.fetchall()
                courses = []

                for row in rows:
                    courses.append({
                        'course_id': row[0],
                        'url': row[1],
                        'title': row[2],
                        'expected_time': row[3],
                        'actual_time': row[4],
                        'diff': row[5],
                    })

                return courses

    except Exception as e:
        log.error(f"Failed to load problematic courses from DB: {e}")
        return []


def delete_lectures_for_courses(course_ids: list, logger_instance=None) -> int:
    """
    Delete lectures for given course IDs

    Args:
        course_ids: List of course IDs
        logger_instance: Optional logger for debug output

    Returns:
        Number of deleted lectures
    """
    log = logger_instance or logger

    if not course_ids:
        return 0

    try:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                placeholders = ','.join(['%s'] * len(course_ids))

                # Count before delete
                cursor.execute(
                    f"SELECT COUNT(*) FROM lectures WHERE course_id IN ({placeholders})",
                    course_ids
                )
                before_count = cursor.fetchone()[0]

                # Delete
                cursor.execute(
                    f"DELETE FROM lectures WHERE course_id IN ({placeholders})",
                    course_ids
                )
                connection.commit()

                log.info(f"Deleted {before_count} old lectures from {len(course_ids)} courses")
                return before_count

    except Exception as e:
        log.error(f"Failed to delete old lectures: {e}")
        return 0


def get_courses_for_crawling(
    target_only: bool = False,
    skip_recent: bool = False,
    course_id: Optional[str] = None,
    logger_instance=None
) -> list:
    """
    Get courses URLs for daily crawling

    Args:
        target_only: Only get courses where is_target_course = 1
        skip_recent: Skip courses updated in last 24 hours
        course_id: Get only specific course
        logger_instance: Optional logger for debug output

    Returns:
        List of dicts with course_id and url
    """
    log = logger_instance or logger

    try:
        conditions = ["url IS NOT NULL"]
        # Exclude manually completed courses
        conditions.append("(is_manually_completed IS NULL OR is_manually_completed = 0)")

        if course_id:
            conditions.append(f"course_id = '{course_id}'")
            log.info(f"Filtering by course_id: {course_id}")
        elif target_only:
            conditions.append("is_target_course = 1")
            log.info("Filtering: is_target_course = 1")

        if skip_recent and not course_id:
            conditions.append(
                "(updated_at < DATE_SUB(NOW(), INTERVAL 1 DAY) OR updated_at IS NULL)"
            )
            log.info("Filtering: skip recently updated courses (< 24h)")

        query = f"SELECT course_id, url FROM courses WHERE {' AND '.join(conditions)}"
        log.info(f"SQL: {query}")

        with db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                courses = [{'course_id': row[0], 'url': row[1]} for row in rows]
                log.info(f"Loaded {len(courses)} course URLs from DB")
                return courses

    except Exception as e:
        log.error(f"Failed to load URLs from DB: {e}")
        return []


def get_manually_completed_course_ids(course_ids: list) -> set:
    """
    Get course IDs that are marked as manually completed

    Args:
        course_ids: List of course IDs to check

    Returns:
        Set of course IDs that are manually completed
    """
    if not course_ids:
        return set()

    try:
        with db_connection() as connection:
            with connection.cursor() as cursor:
                placeholders = ','.join([f"'{cid}'" for cid in course_ids])
                query = f"""
                    SELECT course_id FROM courses
                    WHERE course_id IN ({placeholders}) AND is_manually_completed = 1
                """
                cursor.execute(query)
                return {str(row[0]) for row in cursor.fetchall()}

    except Exception as e:
        logger.error(f"Error checking manually completed courses: {e}")
        return set()
