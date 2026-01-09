import scrapy
from scrapy_playwright.page import PageMethod

from course_scraper.utils import KakaoLoginHelper, get_screenshot_path, extract_course_title


class FastCampusDiscoverSpider(scrapy.Spider):
    """
    월 1회 실행: 새로운 강의를 찾아서 courses 테이블에 저장하는 spider

    사용법:
    1. 모든 강의 수집: scrapy crawl fastcampus_discover
    2. 특정 강의만 수집: scrapy crawl fastcampus_discover -a course_ids="214390,246575,123456"
    """
    name = 'fastcampus_discover'
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def __init__(self, course_ids=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logged_in = False
        self.login_helper = KakaoLoginHelper(logger_instance=self.logger)

        # course_ids parameter handling
        if course_ids:
            self.target_course_ids = set(course_ids.strip().split(','))
            self.logger.info(f"Target course IDs: {self.target_course_ids}")
        else:
            self.target_course_ids = None

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
            success = await self.login_helper.login_with_cookies(page, take_screenshots=True)

            if success:
                self.logged_in = True
                await page.wait_for_timeout(1000)

                # If course_ids specified, visit each course page to get title
                if self.target_course_ids:
                    self.logger.info(f"Visiting {len(self.target_course_ids)} course pages to get titles...")
                    await page.close()

                    for idx, course_id in enumerate(self.target_course_ids, start=1):
                        url = f'https://fastcampus.co.kr/classroom/{course_id}'
                        self.logger.info(f"  {idx}. Visiting course_id: {course_id}")

                        yield scrapy.Request(
                            url,
                            callback=self.parse_course,
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

                    return

                # Navigate to my courses (only when course_ids not specified)
                try:
                    self.logger.info("Navigating to /me/course...")
                    await page.goto('https://fastcampus.co.kr/me/course', wait_until='domcontentloaded')
                    await page.wait_for_timeout(2000)

                    current_url = page.url
                    self.logger.info(f"Navigated to: {current_url}")
                    await page.screenshot(path=get_screenshot_path('discover_courses_page'))

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

                    # Collect course list
                    self.logger.info("Collecting course URLs...")
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

                        course_url = None

                        # Method 1: Extract URL from <a> tag
                        try:
                            link = await box.query_selector('a[href*="/classroom/"]')
                            if link:
                                href = await link.get_attribute('href')
                                if href and '/classroom/' in href:
                                    if href.startswith('/'):
                                        course_url = f'https://fastcampus.co.kr{href}'
                                    else:
                                        course_url = href
                                    self.logger.info(f"     Method 1: Found URL from <a> tag: {course_url}")
                        except Exception as e:
                            self.logger.debug(f"     Method 1 failed: {e}")

                        # Method 2: Extract course_id from button data attribute
                        if not course_url:
                            try:
                                classroom_btn = await box.query_selector('button[data-e2e="classroom-enter-button"]')
                                if classroom_btn:
                                    for attr in ['data-course-id', 'data-id', 'data-key']:
                                        course_id = await classroom_btn.get_attribute(attr)
                                        if course_id:
                                            course_url = f'https://fastcampus.co.kr/classroom/{course_id}'
                                            self.logger.info(f"     Method 2: Extracted course_id from {attr}: {course_id}")
                                            break
                            except Exception as e:
                                self.logger.debug(f"     Method 2 failed: {e}")

                        # Method 3: JavaScript evaluate
                        if not course_url:
                            try:
                                course_url = await box.evaluate('''
                                    (element) => {
                                        const link = element.querySelector('a[href*="/classroom/"]');
                                        if (link) return link.href;

                                        const btn = element.querySelector('button');
                                        if (btn) {
                                            const attrs = ['data-course-id', 'data-id', 'data-key'];
                                            for (const attr of attrs) {
                                                const val = btn.getAttribute(attr);
                                                if (val) return 'https://fastcampus.co.kr/classroom/' + val;
                                            }
                                        }
                                        return null;
                                    }
                                ''')
                                if course_url:
                                    self.logger.info(f"     Method 3: Extracted URL via JavaScript: {course_url}")
                            except Exception as e:
                                self.logger.debug(f"     Method 3 failed: {e}")

                        # Method 4: Fallback - open new tab
                        if not course_url:
                            self.logger.info("     Fallback: Using new tab method...")
                            classroom_btn = await box.query_selector('button[data-e2e="classroom-enter-button"]')
                            if classroom_btn:
                                try:
                                    async with page.context.expect_page(timeout=5000) as page_info:
                                        await classroom_btn.click()

                                    new_page = await page_info.value
                                    await new_page.wait_for_load_state('load', timeout=10000)
                                    course_url = new_page.url
                                    self.logger.info(f"     Method 4: Got URL from new page: {course_url}")

                                    await new_page.close()
                                    await page.wait_for_timeout(1000)

                                except Exception as e:
                                    self.logger.warning(f"     All methods failed for course {idx + 1}: {e}")

                        # Add URL to list
                        if course_url and '/classroom/' in course_url:
                            course_urls.append(course_url)
                        else:
                            self.logger.warning(f"     Could not extract URL for course {idx + 1}")

                    self.logger.info(f"Found {len(course_urls)} total course URLs")

                    # Filter by target_course_ids if specified
                    if self.target_course_ids:
                        filtered_urls = []
                        for url in course_urls:
                            course_id = url.split('/classroom/')[-1].split('?')[0]
                            if course_id in self.target_course_ids:
                                filtered_urls.append(url)
                                self.logger.info(f"Matched target course: {course_id}")
                            else:
                                self.logger.debug(f"  Skipping non-target course: {course_id}")

                        self.logger.info(f"Filtered to {len(filtered_urls)} target courses (from {len(course_urls)} total)")
                        course_urls = filtered_urls

                        # Warn about unmatched course IDs
                        found_ids = {url.split('/classroom/')[-1].split('?')[0] for url in course_urls}
                        not_found = self.target_course_ids - found_ids
                        if not_found:
                            self.logger.warning(f"Target course IDs not found: {not_found}")

                    # Visit each course page to get title
                    self.logger.info(f"Visiting {len(course_urls)} course pages to get titles...")

                    for idx, url in enumerate(course_urls, start=1):
                        course_id = url.split('/classroom/')[-1].split('?')[0]
                        self.logger.info(f"  {idx}. Visiting course_id: {course_id}")

                        yield scrapy.Request(
                            url,
                            callback=self.parse_course,
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

    async def parse_course(self, response):
        """Parse course page to extract title and basic info"""
        page = response.meta.get('playwright_page')

        try:
            page_title = await page.title() if page else response.css('title::text').get()
            self.logger.info(f"Parsing: {response.url}")

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

        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        finally:
            if page:
                await page.close()

    async def errback(self, failure):
        """Error handling"""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        self.logger.error(f"Request failed: {failure.request.url}")
