# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import pymysql
import logging
from datetime import datetime


class MySQLPipeline:
    """MySQL 데이터베이스에 크롤링 데이터를 저장하는 파이프라인"""

    def __init__(self, mysql_host, mysql_port, mysql_user, mysql_password, mysql_db):
        self.mysql_host = mysql_host
        self.mysql_port = mysql_port
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.mysql_db = mysql_db
        self.connection = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler):
        """Scrapy settings에서 DB 설정 가져오기"""
        return cls(
            mysql_host=crawler.settings.get('MYSQL_HOST', 'localhost'),
            mysql_port=crawler.settings.get('MYSQL_PORT', 3306),
            mysql_user=crawler.settings.get('MYSQL_USER', 'root'),
            mysql_password=crawler.settings.get('MYSQL_PASSWORD', ''),
            mysql_db=crawler.settings.get('MYSQL_DATABASE', 'crawler')
        )

    def open_spider(self, spider):
        """스파이더 시작 시 DB 연결"""
        try:
            self.connection = pymysql.connect(
                host=self.mysql_host,
                port=self.mysql_port,
                user=self.mysql_user,
                password=self.mysql_password,
                database=self.mysql_db,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            self.cursor = self.connection.cursor()
            logging.info(f"MySQL connected: {self.mysql_host}:{self.mysql_port}/{self.mysql_db}")
        except Exception as e:
            logging.error(f"MySQL connection failed: {e}")
            raise

    def close_spider(self, spider):
        """스파이더 종료 시 DB 연결 종료"""
        if self.connection:
            self.connection.close()
            logging.info("MySQL connection closed")

    def process_item(self, item, spider):
        """아이템 처리 및 DB 저장"""
        from course_scraper.items import CourseItem, LectureItem

        try:
            if isinstance(item, CourseItem):
                # CourseItem 처리
                url = item.get('url', '')
                course_id = self.extract_course_id(url)

                if not course_id:
                    logging.warning(f"Cannot extract course_id from URL: {url}")
                    return item

                # 강의 정보 저장
                self.save_course(course_id, item)

                # 크롤링 로그 저장
                self.save_crawl_log(course_id, 'success', None)

                self.connection.commit()
                logging.info(f"Saved CourseItem: course_id {course_id}")

            elif isinstance(item, LectureItem):
                # LectureItem 처리
                self.save_lecture_item(item)
                self.connection.commit()

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Error saving item: {e}")
            import traceback
            logging.error(traceback.format_exc())

        return item

    def extract_course_id(self, url):
        """URL에서 course_id 추출"""
        try:
            # https://fastcampus.co.kr/classroom/214390 형식에서 214390 추출
            parts = url.rstrip('/').split('/')
            course_id = parts[-1]
            if course_id.isdigit():
                return int(course_id)
        except:
            pass
        return None

    def save_course(self, course_id, item):
        """강의 정보 저장 (UPSERT)"""
        sql = """
            INSERT INTO courses (
                course_id, course_title, progress_rate, study_time,
                total_lecture_time, url
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                course_title = VALUES(course_title),
                progress_rate = VALUES(progress_rate),
                study_time = VALUES(study_time),
                total_lecture_time = VALUES(total_lecture_time),
                url = VALUES(url),
                updated_at = CURRENT_TIMESTAMP
        """

        values = (
            course_id,
            item.get('course_title', 'Unknown Title'),
            item.get('progress_rate'),
            item.get('study_time'),
            item.get('total_lecture_time'),
            item.get('url', '')
        )

        self.cursor.execute(sql, values)

    def save_lecture_item(self, item):
        """LectureItem 저장 (UPSERT)"""
        sql = """
            INSERT INTO lectures (
                course_id, course_title, section_number, section_title,
                lecture_number, lecture_title, lecture_time,
                is_completed, sort_order
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                course_title = VALUES(course_title),
                section_title = VALUES(section_title),
                lecture_title = VALUES(lecture_title),
                lecture_time = VALUES(lecture_time),
                is_completed = VALUES(is_completed),
                updated_at = CURRENT_TIMESTAMP
        """

        values = (
            item.get('course_id'),
            item.get('course_title'),
            item.get('section_number'),
            item.get('section_title'),
            item.get('lecture_number'),
            item.get('lecture_title'),
            item.get('lecture_time'),
            item.get('is_completed', False),
            item.get('sort_order')
        )

        self.cursor.execute(sql, values)

    def save_lectures(self, course_id, curriculum):
        """강의 목차 저장"""
        # 기존 목차 삭제 (새로 저장)
        delete_sql = "DELETE FROM lectures WHERE course_id = %s"
        self.cursor.execute(delete_sql, (course_id,))

        # 새 목차 저장
        insert_sql = """
            INSERT INTO lectures (
                course_id, section_number, section_title,
                lecture_number, lecture_title, lecture_time,
                is_completed, sort_order
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        sort_order = 1
        for section_idx, section in enumerate(curriculum, 1):
            section_title = section.get('section', f'Section {section_idx}')
            lessons = section.get('lessons', [])

            for lecture_idx, lesson in enumerate(lessons, 1):
                # 시간 문자열을 분 단위로 변환 (예: "15분", "1시간 30분" -> 분)
                lecture_time_str = lesson.get('duration', '')
                lecture_time = self.parse_duration(lecture_time_str)

                values = (
                    course_id,
                    section_idx,
                    section_title,
                    lecture_idx,
                    lesson.get('title', ''),
                    lecture_time,
                    False,  # is_completed
                    sort_order
                )

                self.cursor.execute(insert_sql, values)
                sort_order += 1

    def parse_duration(self, duration_str):
        """시간 문자열을 분 단위로 변환"""
        if not duration_str:
            return None

        try:
            duration_str = duration_str.strip()
            total_minutes = 0

            # "HH:MM:SS" 또는 "MM:SS" 형식 (예: "2:46:10" 또는 "46:10")
            if ':' in duration_str:
                parts = duration_str.split(':')
                if len(parts) == 3:  # HH:MM:SS 형식
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    total_minutes = hours * 60 + minutes + round(seconds / 60, 2)
                elif len(parts) == 2:  # MM:SS 형식
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    total_minutes = minutes + round(seconds / 60, 2)
            # "1시간 30분" 형식
            elif '시간' in duration_str:
                parts = duration_str.split('시간')
                hours = int(parts[0].strip())
                total_minutes += hours * 60

                if len(parts) > 1 and '분' in parts[1]:
                    minutes = int(parts[1].replace('분', '').strip())
                    total_minutes += minutes
            # "30분" 형식
            elif '분' in duration_str:
                minutes = int(duration_str.replace('분', '').strip())
                total_minutes = minutes
            # 숫자만 있는 경우 (분으로 가정)
            elif duration_str.isdigit():
                total_minutes = int(duration_str)

            return total_minutes if total_minutes > 0 else None

        except:
            return None

    def save_crawl_log(self, course_id, status, error_message):
        """크롤링 로그 저장"""
        sql = """
            INSERT INTO crawl_logs (
                course_id, crawl_status, error_message
            ) VALUES (
                %s, %s, %s
            )
        """

        self.cursor.execute(sql, (course_id, status, error_message))
