import scrapy
import json


class UdemySpider(scrapy.Spider):
    name = 'udemy'
    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def start_requests(self):
        urls = [
            # TODO: Udemy URL 추가
        ]

        for url in urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        # 커리큘럼 파싱
        curriculum = self.extract_curriculum(response)

        if curriculum:
            yield {
                'url': response.url,
                'title': self.extract_title(response),
                'curriculum': curriculum,
                'total_sections': len(curriculum),
            }

    def extract_title(self, response):
        """강의 제목 추출"""
        title = response.css('h1[data-purpose="lead-title"]::text, h1::text').get()
        if not title:
            title = response.xpath('//h1/text()').get()
        return title.strip() if title else 'Unknown Title'

    def extract_curriculum(self, response):
        """커리큘럼 추출 로직"""
        curriculum = []

        # Udemy 커리큘럼 구조 추출
        sections = response.css('.curriculum-section, section[data-purpose="curriculum-section"]')

        for section in sections:
            section_title = section.css('.section-title::text, h2::text, .ud-heading-xl::text').get()
            lessons = section.css('.curriculum-item, .lecture-item, li[data-purpose="curriculum-item"]')

            lesson_list = []
            for lesson in lessons:
                lesson_title = lesson.css('.lecture-title::text, span::text, button::text').get()
                lesson_duration = lesson.css('.duration::text, .content-summary::text').get()

                if lesson_title:
                    lesson_list.append({
                        'title': lesson_title.strip(),
                        'duration': lesson_duration.strip() if lesson_duration else None
                    })

            if section_title:
                curriculum.append({
                    'section': section_title.strip(),
                    'lessons': lesson_list,
                    'lesson_count': len(lesson_list)
                })

        return curriculum
