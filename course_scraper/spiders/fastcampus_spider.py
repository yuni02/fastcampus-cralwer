import scrapy
from scrapy_playwright.page import PageMethod

from course_scraper.utils import (
    KakaoLoginHelper,
    extract_course_title,
    get_manually_completed_course_ids,
    get_screenshot_path,
)


class FastCampusSpider(scrapy.Spider):
    """
    메인 스파이더: 전체 강의를 수집하는 spider
    """
    name = 'fastcampus'
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logged_in = False
        self.login_helper = KakaoLoginHelper(logger_instance=self.logger)

    def start_requests(self):
        yield scrapy.Request(
            'https://fastcampus.co.kr/account/sign-in',
            callback=self.login,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_methods': [
                    PageMethod('wait_for_timeout', 8000),
                ],
            },
            errback=self.errback,
            dont_filter=True
        )

    async def login(self, response):
        """Kakao login automation"""
        page = response.meta['playwright_page']

        try:
            success = await self.login_helper.login(page, take_screenshots=True)

            if success:
                self.logged_in = True
                await page.wait_for_timeout(1000)

                # Navigate to my courses
                try:
                    self.logger.info("Navigating to /me/course...")
                    await page.goto('https://fastcampus.co.kr/me/course', wait_until='domcontentloaded')
                    await page.wait_for_timeout(2000)

                    current_url = page.url
                    self.logger.info(f"Navigated to: {current_url}")
                    await page.screenshot(path=get_screenshot_path('courses_page'))

                    # Click 수강중 tab
                    tab_selectors = ['button:has-text("수강중")', 'a:has-text("수강중")', '[role="tab"]:has-text("수강중")']
                    for selector in tab_selectors:
                        try:
                            await page.click(selector, timeout=2000)
                            self.logger.info("Clicked 수강중 tab")
                            await page.wait_for_timeout(2000)
                            break
                        except Exception:
                            continue

                    # Scroll to load all courses
                    self.logger.info("Scrolling to load all courses...")
                    previous_height = 0
                    scroll_attempts = 0
                    max_scroll_attempts = 20

                    while scroll_attempts < max_scroll_attempts:
                        current_height = await page.evaluate('document.body.scrollHeight')
                        if current_height == previous_height:
                            break
                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        await page.wait_for_timeout(2000)
                        previous_height = current_height
                        scroll_attempts += 1

                    await page.evaluate('window.scrollTo(0, 0)')
                    await page.wait_for_timeout(1000)

                    # Collect course URLs
                    course_boxes = await page.query_selector_all('.vn-me-courses__box')
                    total_courses = len(course_boxes)
                    self.logger.info(f"Found {total_courses} course boxes")

                    course_urls = []
                    for idx in range(total_courses):
                        course_boxes = await page.query_selector_all('.vn-me-courses__box')
                        box = course_boxes[idx]

                        title_elem = await box.query_selector('.vn-me-courses__title')
                        title = await title_elem.inner_text() if title_elem else f'Course {idx + 1}'
                        self.logger.info(f"  {idx + 1}/{total_courses}. {title}")

                        classroom_btn = await box.query_selector('button[data-e2e="classroom-enter-button"]')
                        if classroom_btn:
                            try:
                                async with page.context.expect_page(timeout=5000) as page_info:
                                    await classroom_btn.click()

                                new_page = await page_info.value
                                await new_page.wait_for_load_state('load', timeout=10000)
                                course_url = new_page.url
                                course_urls.append(course_url)
                                self.logger.info(f"     URL: {course_url}")

                                await new_page.close()
                                await page.wait_for_timeout(1000)
                            except Exception as e:
                                self.logger.warning(f"     Failed to get URL: {e}")

                    self.logger.info(f"Collected {len(course_urls)} course URLs")
                    await page.close()

                    # Filter out manually completed courses
                    course_ids = [url.split('/classroom/')[-1].split('?')[0] for url in course_urls]
                    manually_completed = get_manually_completed_course_ids(course_ids)

                    if manually_completed:
                        self.logger.info(f"Skipping {len(manually_completed)} manually completed courses")
                        course_urls = [url for url in course_urls
                                       if url.split('/classroom/')[-1].split('?')[0] not in manually_completed]

                    # Crawl each course
                    for url in course_urls:
                        yield scrapy.Request(
                            url,
                            callback=self.parse,
                            meta={
                                'playwright': True,
                                'playwright_include_page': True,
                                'playwright_page_methods': [
                                    PageMethod('wait_for_timeout', 3000),
                                ],
                            },
                            errback=self.errback,
                            dont_filter=True
                        )

                except Exception as e:
                    self.logger.error(f"Navigation failed: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                    await page.close()
            else:
                await page.close()

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if page:
                await page.close()

    async def parse(self, response):
        """Parse page and extract course info to save to DB"""
        page = response.meta.get('playwright_page')

        try:
            page_title = await page.title() if page else response.css('title::text').get()
            self.logger.info(f"Parsing: {response.url}")
            self.logger.info(f"Page title: {page_title}")

            # Login check
            if '인증' in page_title or 'sign-in' in response.url:
                self.logger.error("Still on login page! Session expired.")
                if page:
                    await page.close()
                return

            # Extract course ID
            course_id = response.url.split('/classroom/')[-1].split('?')[0]

            # Extract course title using shared utility
            course_title = await extract_course_title(
                page, page_title, course_id, self.logger
            )
            self.logger.info(f"Course: {course_title}")

            # Extract progress rate, study time, total lecture time
            progress_rate = 0.0
            study_time = 0
            total_lecture_time = 0

            if page:
                try:
                    page_text = await page.inner_text('body')
                    import re

                    progress_match = re.search(r'수강률\s*(\d+(?:\.\d+)?)\s*%', page_text)
                    if progress_match:
                        progress_rate = float(progress_match.group(1))
                        self.logger.info(f"  Progress: {progress_rate}%")

                    study_match = re.search(r'수강시간\s*(\d+):(\d+)(?::(\d+))?', page_text)
                    if study_match:
                        first = int(study_match.group(1))
                        second = int(study_match.group(2))
                        third = int(study_match.group(3)) if study_match.group(3) else None

                        if third is not None:
                            study_time = first * 60 + second + round(third / 60, 2)
                        else:
                            study_time = first + round(second / 60, 2)

                        self.logger.info(f"  Study time: {study_time} min")

                    total_match = re.search(r'강의시간\s*(\d+):(\d+):(\d+)', page_text)
                    if total_match:
                        hours = int(total_match.group(1))
                        minutes = int(total_match.group(2))
                        seconds = int(total_match.group(3))
                        total_lecture_time = hours * 60 + minutes + (seconds / 60)
                        self.logger.info(f"  Total time: {total_lecture_time} min")
                except Exception as e:
                    self.logger.warning(f"Could not extract time info: {str(e)[:100]}")

            # Create CourseItem
            from course_scraper.items import CourseItem
            course_item = CourseItem(
                course_id=course_id,
                course_title=course_title,
                progress_rate=progress_rate,
                study_time=study_time,
                total_lecture_time=total_lecture_time,
                url=response.url
            )

            yield course_item
            self.logger.info(f"Yielded CourseItem: {course_title}")

            # Extract curriculum
            curriculum = await self.extract_curriculum_playwright(page) if page else []

            if curriculum:
                from course_scraper.items import LectureItem

                sort_order = 0
                for section in curriculum:
                    section_number = section.get('section_number')
                    section_title = section.get('section', f'Section {section_number}')
                    chapters = section.get('chapters')

                    if chapters:
                        for chapter in chapters:
                            chapter_number = chapter.get('chapter_number')
                            chapter_title = chapter.get('chapter_title')
                            lessons = chapter.get('lessons', [])

                            for lecture_idx, lesson in enumerate(lessons, 1):
                                sort_order += 1

                                lecture_title = lesson.get('title', f'Lecture {lecture_idx}')
                                lecture_duration = lesson.get('duration', None)
                                lecture_time = self.parse_duration(lecture_duration) if lecture_duration else 0
                                is_completed = lesson.get('is_completed', False)

                                lecture_item = LectureItem(
                                    course_id=course_id,
                                    course_title=course_title,
                                    section_number=section_number,
                                    section_title=section_title,
                                    chapter_number=chapter_number,
                                    chapter_title=chapter_title,
                                    lecture_number=lecture_idx,
                                    lecture_title=lecture_title,
                                    lecture_time=lecture_time,
                                    is_completed=is_completed,
                                    sort_order=sort_order
                                )

                                yield lecture_item
                    else:
                        lessons = section.get('lessons', [])

                        for lecture_idx, lesson in enumerate(lessons, 1):
                            sort_order += 1

                            lecture_title = lesson.get('title', f'Lecture {lecture_idx}')
                            lecture_duration = lesson.get('duration', None)
                            lecture_time = self.parse_duration(lecture_duration) if lecture_duration else 0
                            is_completed = lesson.get('is_completed', False)

                            lecture_item = LectureItem(
                                course_id=course_id,
                                course_title=course_title,
                                section_number=section_number,
                                section_title=section_title,
                                chapter_number=None,
                                chapter_title=None,
                                lecture_number=lecture_idx,
                                lecture_title=lecture_title,
                                lecture_time=lecture_time,
                                is_completed=is_completed,
                                sort_order=sort_order
                            )

                            yield lecture_item

                self.logger.info(f"Extracted {len(curriculum)} sections, {sort_order} total lectures")
            else:
                self.logger.warning(f"No curriculum found for {response.url}")

        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        finally:
            if page:
                await page.close()

    async def extract_curriculum_playwright(self, page):
        """Extract curriculum using Playwright - open all nested accordion sections"""
        curriculum = []

        try:
            await page.wait_for_selector('.classroom-sidebar-clip__chapter', timeout=10000)
            await page.wait_for_timeout(2000)

            # STEP 1: Find all accordion headers
            self.logger.info("=" * 80)
            self.logger.info("STEP 1: Finding ALL accordion headers with arrow icons...")
            self.logger.info("=" * 80)

            all_headers = await page.query_selector_all('.common-accordion-menu__header')
            self.logger.info(f"Found {len(all_headers)} total accordion headers")

            # STEP 2: Open all accordion sections
            self.logger.info("=" * 80)
            self.logger.info("STEP 2: Opening ALL accordion sections one by one...")
            self.logger.info("=" * 80)

            opened_count = 0
            for idx, header in enumerate(all_headers, 1):
                try:
                    arrow_icon = await header.query_selector('.common-accordion-menu__header__arrow-icon')
                    if not arrow_icon:
                        continue

                    parent_menu = await header.evaluate_handle('el => el.closest(".common-accordion-menu")')
                    if parent_menu:
                        parent_menu_elem = parent_menu.as_element()
                        class_attr = await parent_menu_elem.get_attribute('class')
                        is_open = 'common-accordion-menu--open' in class_attr if class_attr else False

                        if not is_open:
                            await header.scroll_into_view_if_needed()
                            await page.wait_for_timeout(300)
                            await header.click()
                            await page.wait_for_timeout(800)

                            class_attr_after = await parent_menu_elem.get_attribute('class')
                            if 'common-accordion-menu--open' in class_attr_after:
                                opened_count += 1
                                if opened_count % 5 == 0:
                                    self.logger.info(f"  Opened {opened_count} sections so far...")
                            else:
                                await page.wait_for_timeout(300)
                                await header.click()
                                await page.wait_for_timeout(800)
                        else:
                            opened_count += 1

                except Exception as e:
                    self.logger.warning(f"  Error opening header {idx}: {str(e)[:100]}")
                    continue

            self.logger.info(f"Opened {opened_count} accordion sections")

            # STEP 3: Double check for remaining closed sections
            self.logger.info("=" * 80)
            self.logger.info("STEP 3: Double-checking for any remaining closed sections...")
            self.logger.info("=" * 80)

            await page.wait_for_timeout(2000)

            all_headers_again = await page.query_selector_all('.common-accordion-menu__header')
            self.logger.info(f"Found {len(all_headers_again)} headers on second pass")

            additional_opened = 0
            for header in all_headers_again:
                try:
                    arrow_icon = await header.query_selector('.common-accordion-menu__header__arrow-icon')
                    if not arrow_icon:
                        continue

                    parent_menu = await header.evaluate_handle('el => el.closest(".common-accordion-menu")')
                    if parent_menu:
                        parent_menu_elem = parent_menu.as_element()
                        class_attr = await parent_menu_elem.get_attribute('class')
                        is_open = 'common-accordion-menu--open' in class_attr if class_attr else False

                        if not is_open:
                            await header.scroll_into_view_if_needed()
                            await page.wait_for_timeout(200)
                            await header.click()
                            await page.wait_for_timeout(600)
                            additional_opened += 1

                except Exception:
                    continue

            if additional_opened > 0:
                self.logger.info(f"Opened {additional_opened} additional sections on second pass")

            await page.wait_for_timeout(3000)

            self.logger.info("=" * 80)
            self.logger.info("All accordion sections opened! Now extracting curriculum data...")
            self.logger.info("=" * 80)

            section_elements = await page.query_selector_all('.classroom-sidebar-clip__chapter')

            for section_idx, section_elem in enumerate(section_elements, 1):
                try:
                    section_title_elem = await section_elem.query_selector('.classroom-sidebar-clip__chapter__title__text')
                    section_title = await section_title_elem.inner_text() if section_title_elem else f'Section {section_idx}'
                    section_title = section_title.strip()

                    complete_elem = await section_elem.query_selector('.classroom-sidebar-clip__chapter__title__number__complete')
                    total_elem = await section_elem.query_selector('.classroom-sidebar-clip__chapter__title__number__total')
                    complete_count = int(await complete_elem.inner_text()) if complete_elem else 0
                    total_count = int(await total_elem.inner_text()) if total_elem else 0

                    chapter_elements = await section_elem.query_selector_all('.classroom-sidebar-clip__chapter__part__title')

                    if chapter_elements and len(chapter_elements) > 0:
                        self.logger.info(f"  Section {section_idx}: {section_title} (has {len(chapter_elements)} chapters)")

                        chapters_data = []
                        for chapter_idx, chapter_title_elem in enumerate(chapter_elements, 1):
                            try:
                                chapter_title = await chapter_title_elem.inner_text() if chapter_title_elem else f'Chapter {chapter_idx}'
                                chapter_title = chapter_title.strip()

                                chapter_parent = await chapter_title_elem.evaluate_handle('el => el.closest(".classroom-sidebar-clip__chapter__part")')
                                if chapter_parent:
                                    chapter_parent_elem = chapter_parent.as_element()
                                    lecture_elements = await chapter_parent_elem.query_selector_all('.classroom-sidebar-clip__chapter__clip')
                                else:
                                    lecture_elements = []

                                lessons = []
                                for lecture_idx, lecture_elem in enumerate(lecture_elements, 1):
                                    try:
                                        title_elem = await lecture_elem.query_selector('.classroom-sidebar-clip__chapter__clip__title')
                                        lecture_title = await title_elem.inner_text() if title_elem else f'Lecture {lecture_idx}'
                                        lecture_title = lecture_title.strip()

                                        time_elem = await lecture_elem.query_selector('.classroom-sidebar-clip__chapter__clip__time')
                                        lecture_duration = await time_elem.inner_text() if time_elem else ''
                                        lecture_duration = lecture_duration.strip()

                                        class_attr = await lecture_elem.get_attribute('class')
                                        is_completed = 'classroom-sidebar-clip__chapter__clip--complete' in class_attr if class_attr else False

                                        lessons.append({
                                            'title': lecture_title,
                                            'duration': lecture_duration,
                                            'is_completed': is_completed
                                        })

                                    except Exception as e:
                                        self.logger.warning(f"      Error parsing lecture {lecture_idx} in chapter {chapter_idx}: {e}")
                                        continue

                                if lessons:
                                    chapters_data.append({
                                        'chapter_number': chapter_idx,
                                        'chapter_title': chapter_title,
                                        'lessons': lessons
                                    })
                                    self.logger.info(f"    Chapter {chapter_idx}: {chapter_title} ({len(lessons)} lectures)")

                            except Exception as e:
                                self.logger.warning(f"    Error parsing chapter {chapter_idx}: {e}")
                                continue

                        if chapters_data:
                            curriculum.append({
                                'section': section_title,
                                'section_number': section_idx,
                                'chapters': chapters_data,
                                'complete_count': complete_count,
                                'total_count': total_count
                            })

                    else:
                        lecture_elements = await section_elem.query_selector_all('.classroom-sidebar-clip__chapter__clip')
                        lessons = []

                        self.logger.info(f"  Section {section_idx}: {section_title} ({complete_count}/{total_count}) - {len(lecture_elements)} lectures")

                        for lecture_idx, lecture_elem in enumerate(lecture_elements, 1):
                            try:
                                title_elem = await lecture_elem.query_selector('.classroom-sidebar-clip__chapter__clip__title')
                                lecture_title = await title_elem.inner_text() if title_elem else f'Lecture {lecture_idx}'
                                lecture_title = lecture_title.strip()

                                time_elem = await lecture_elem.query_selector('.classroom-sidebar-clip__chapter__clip__time')
                                lecture_duration = await time_elem.inner_text() if time_elem else ''
                                lecture_duration = lecture_duration.strip()

                                class_attr = await lecture_elem.get_attribute('class')
                                is_completed = 'classroom-sidebar-clip__chapter__clip--complete' in class_attr if class_attr else False

                                lessons.append({
                                    'title': lecture_title,
                                    'duration': lecture_duration,
                                    'is_completed': is_completed
                                })

                            except Exception as e:
                                self.logger.warning(f"    Error parsing lecture {lecture_idx}: {e}")
                                continue

                        if lessons:
                            curriculum.append({
                                'section': section_title,
                                'section_number': section_idx,
                                'chapters': None,
                                'lessons': lessons,
                                'lesson_count': len(lessons),
                                'complete_count': complete_count,
                                'total_count': total_count
                            })
                        else:
                            self.logger.warning(f"  No lectures found in section {section_idx}")

                except Exception as e:
                    self.logger.warning(f"  Error parsing section {section_idx}: {e}")
                    import traceback
                    self.logger.warning(traceback.format_exc())
                    continue

            self.logger.info(f"Extracted {len(curriculum)} sections total")

        except Exception as e:
            self.logger.error(f"Error extracting curriculum: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        return curriculum

    def parse_duration(self, duration_str):
        """Convert time string to minutes"""
        if not duration_str:
            return 0

        total_minutes = 0
        import re

        hours_match = re.search(r'(\d+)\s*시간', duration_str)
        minutes_match = re.search(r'(\d+)\s*분', duration_str)

        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60
        if minutes_match:
            total_minutes += int(minutes_match.group(1))

        if ':' in duration_str:
            time_parts = duration_str.strip().split(':')
            if len(time_parts) == 3:
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                seconds = int(time_parts[2])
                total_minutes = hours * 60 + minutes + round(seconds / 60, 2)
            elif len(time_parts) == 2:
                minutes = int(time_parts[0])
                seconds = int(time_parts[1])
                total_minutes = minutes + round(seconds / 60, 2)

        return round(total_minutes, 2)

    async def errback(self, failure):
        """Error handling"""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        self.logger.error(f"Request failed: {failure.request.url}")
