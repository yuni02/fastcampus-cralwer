import scrapy
import json


class InflearnSpider(scrapy.Spider):
    name = 'inflearn'
    custom_settings = {
        'DOWNLOAD_DELAY': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def start_requests(self):
        urls = [
            # TODO: 인프런 URL 추가
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
        title = response.css('h1.title::text, h1::text').get()
        if not title:
            title = response.xpath('//h1/text()').get()
        return title.strip() if title else 'Unknown Title'

    def extract_curriculum(self, response):
        """커리큘럼 추출 로직"""
        curriculum = []

        # 인프런 커리큘럼 구조 추출
        sections = response.css('.curriculum-section, .ac-curriculum')

        for section in sections:
            section_title = section.css('.section-title::text, h3::text, .title::text').get()
            lessons = section.css('.curriculum-item, .ac-curriculum-item, li.lecture')

            lesson_list = []
            for lesson in lessons:
                lesson_title = lesson.css('.lecture-title::text, .title::text, a::text').get()
                lesson_duration = lesson.css('.duration::text, .time::text').get()

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
