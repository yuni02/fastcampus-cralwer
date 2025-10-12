# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class CourseItem(scrapy.Item):
    """강의 정보 아이템"""
    course_id = scrapy.Field()          # URL의 강의 ID
    course_title = scrapy.Field()       # 강의 제목
    progress_rate = scrapy.Field()      # 수강률
    study_time = scrapy.Field()         # 수강시간 (분)
    total_lecture_time = scrapy.Field() # 총 강의시간 (분)
    url = scrapy.Field()                # 강의 URL


class LectureItem(scrapy.Item):
    """강의 목차 아이템"""
    course_id = scrapy.Field()          # 강의 ID (FK)
    course_title = scrapy.Field()       # 강의 제목 (courses 테이블과 조인 없이 조회 가능)
    section_number = scrapy.Field()     # 섹션 번호
    section_title = scrapy.Field()      # 섹션/챕터 제목
    lecture_number = scrapy.Field()     # 강의 번호 (섹션 내)
    lecture_title = scrapy.Field()      # 강의 제목
    lecture_time = scrapy.Field()       # 강의 시간 (분)
    is_completed = scrapy.Field()       # 완료 여부
    sort_order = scrapy.Field()         # 정렬 순서
