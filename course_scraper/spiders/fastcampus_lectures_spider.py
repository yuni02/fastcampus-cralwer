import scrapy
import os
from scrapy_playwright.page import PageMethod

# credentials.py에서 로그인 정보 가져오기
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
credentials_path = os.path.join(project_root, 'credentials.py')

KAKAO_EMAIL = None
KAKAO_PASSWORD = None

if os.path.exists(credentials_path):
    with open(credentials_path, 'r', encoding='utf-8') as f:
        exec_globals = {}
        exec(f.read(), exec_globals)
        KAKAO_EMAIL = exec_globals.get('KAKAO_EMAIL')
        KAKAO_PASSWORD = exec_globals.get('KAKAO_PASSWORD')
else:
    raise FileNotFoundError(f"credentials.py not found at {credentials_path}")

if not KAKAO_EMAIL or not KAKAO_PASSWORD:
    raise ValueError("KAKAO_EMAIL or KAKAO_PASSWORD not set in credentials.py")


class FastCampusLecturesSpider(scrapy.Spider):
    """
    특정 코스 ID를 입력받아 해당 강의의 lectures 목록만 크롤링하는 spider

    사용법:
    scrapy crawl fastcampus_lectures -a course_id=YOUR_COURSE_ID
    """
    name = 'fastcampus_lectures'
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def __init__(self, course_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logged_in = False

        if not course_id:
            raise ValueError("course_id parameter is required! Usage: scrapy crawl fastcampus_lectures -a course_id=YOUR_COURSE_ID")

        self.course_id = course_id
        self.course_url = f'https://fastcampus.co.kr/classroom/{course_id}'
        self.logger.info(f"Target course: {self.course_url}")

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
        """카카오 로그인 자동화"""
        page = response.meta['playwright_page']

        try:
            self.logger.info("Starting Kakao login process...")

            # 카카오 로그인 버튼 클릭
            selectors = [
                'button:has-text("카카오로 1초 만에 시작하기")',
                'button:has-text("카카오")',
                'a:has-text("카카오로 1초 만에 시작하기")',
                '[class*="kakao"]',
            ]

            clicked = False
            for selector in selectors:
                try:
                    await page.click(selector, timeout=5000)
                    self.logger.info(f"✓ Clicked Kakao button")
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                self.logger.error("✗ Could not find Kakao login button")
                await page.close()
                return

            await page.wait_for_timeout(3000)

            # 이메일 입력
            email_selectors = ['input[name="loginId"]', 'input[type="email"]', '#loginId']
            for selector in email_selectors:
                try:
                    await page.fill(selector, KAKAO_EMAIL, timeout=3000)
                    self.logger.info(f"✓ Entered email")
                    break
                except Exception:
                    continue

            # 비밀번호 입력
            password_selectors = ['input[name="password"]', 'input[type="password"]', '#password']
            for selector in password_selectors:
                try:
                    await page.fill(selector, KAKAO_PASSWORD, timeout=3000)
                    self.logger.info(f"✓ Entered password")
                    break
                except Exception:
                    continue

            # 로그인 버튼 클릭
            login_selectors = ['button[type="submit"]', 'button:has-text("로그인")', '.btn_confirm']
            for selector in login_selectors:
                try:
                    await page.click(selector, timeout=3000)
                    self.logger.info(f"✓ Clicked login button")
                    break
                except Exception:
                    continue

            # 2FA 대기
            self.logger.info("=" * 70)
            self.logger.info("⚠️  KakaoTalk 앱에서 2단계 인증을 승인해주세요! ⚠️")
            self.logger.info("90초 대기 중...")
            self.logger.info("=" * 70)

            max_wait_time = 90
            check_interval = 2

            for i in range(0, max_wait_time, check_interval):
                await page.wait_for_timeout(check_interval * 1000)

                # Continue 버튼 찾기
                continue_selectors = ['button.btn_confirm', 'button:has-text("Continue")', 'button:has-text("확인")']
                for selector in continue_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn and await btn.is_visible():
                            await btn.click()
                            self.logger.info("✓ Clicked Continue button!")
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        continue

                # FastCampus로 리디렉트되었는지 확인
                current_url = page.url
                if 'fastcampus.co.kr' in current_url and 'sign-in' not in current_url:
                    self.logger.info(f"✓ Successfully redirected to FastCampus!")
                    break

            current_url = page.url
            page_title = await page.title()

            # 로그인 성공 확인
            if 'sign-in' not in current_url and '인증' not in page_title:
                self.logger.info("✓ Login successful!")
                self.logged_in = True

                # 페이지 닫기
                await page.close()

                # 특정 코스 URL로 크롤링 요청
                self.logger.info(f"Starting to crawl course: {self.course_url}")
                yield scrapy.Request(
                    self.course_url,
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
            else:
                self.logger.error("✗ Login failed!")
                await page.close()

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if page:
                await page.close()

    async def parse(self, response):
        """페이지 파싱 및 강의 정보 추출하여 DB 저장"""
        page = response.meta.get('playwright_page')

        try:
            # 페이지 제목 확인
            page_title = await page.title() if page else response.css('title::text').get()
            self.logger.info(f"Parsing: {response.url}")
            self.logger.info(f"Page title: {page_title}")

            # 로그인 확인
            if '인증' in page_title or 'sign-in' in response.url:
                self.logger.error(f"✗ Still on login page! Session expired.")
                if page:
                    await page.close()
                return

            # Course ID 추출
            course_id = response.url.split('/classroom/')[-1].split('?')[0]

            # 강의 제목 추출
            course_title = None
            if ' - ' in page_title:
                course_title = page_title.split(' - ', 1)[1].strip()
            elif '|' in page_title:
                course_title = page_title.split('|')[0].strip()

            if not course_title or len(course_title) < 10:
                if page:
                    try:
                        title_elem = await page.query_selector('header h1, h1')
                        if title_elem:
                            title_text = await title_elem.inner_text()
                            if title_text and len(title_text) > 10:
                                course_title = title_text.strip()
                    except:
                        pass

            if not course_title or len(course_title) < 5:
                course_title = f'Course {course_id}'

            course_title = course_title.strip()
            self.logger.info(f"Course: {course_title}")

            # 진도율, 학습시간, 전체시간 추출
            progress_rate = 0.0
            study_time = 0
            total_lecture_time = 0

            if page:
                try:
                    page_text = await page.inner_text('body')

                    import re
                    # 수강률 추출
                    progress_match = re.search(r'수강률\s*(\d+(?:\.\d+)?)\s*%', page_text)
                    if progress_match:
                        progress_rate = float(progress_match.group(1))
                        self.logger.info(f"  Progress: {progress_rate}%")

                    # 수강시간 추출
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

                    # 강의시간 추출
                    total_match = re.search(r'강의시간\s*(\d+):(\d+):(\d+)', page_text)
                    if total_match:
                        hours = int(total_match.group(1))
                        minutes = int(total_match.group(2))
                        seconds = int(total_match.group(3))
                        total_lecture_time = hours * 60 + minutes + (seconds / 60)
                        self.logger.info(f"  Total time: {total_lecture_time} min")
                except Exception as e:
                    self.logger.warning(f"Could not extract time info: {str(e)[:100]}")

            # CourseItem 생성
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
            self.logger.info(f"✓ Yielded CourseItem: {course_title}")

            # 커리큘럼 추출
            curriculum = await self.extract_curriculum_playwright(page) if page else []

            if curriculum:
                from course_scraper.items import LectureItem

                sort_order = 0
                for section in curriculum:
                    section_number = section.get('section_number')
                    section_title = section.get('section', f'Section {section_number}')
                    chapters = section.get('chapters')

                    if chapters:
                        # Chapter 구조가 있는 경우
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
                        # Chapter 구조가 없고 Section 레벨에서 바로 강의
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

                self.logger.info(f"✓ Extracted {len(curriculum)} sections, {sort_order} total lectures")
            else:
                self.logger.warning(f"✗ No curriculum found for {response.url}")

        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        finally:
            if page:
                await page.close()

    async def extract_curriculum_playwright(self, page):
        """Playwright를 사용하여 커리큘럼 추출 - 모든 nested 아코디언 섹션 펼치기"""
        curriculum = []

        try:
            # 커리큘럼 영역이 로드될 때까지 대기
            await page.wait_for_selector('.classroom-sidebar-clip__chapter', timeout=10000)
            await page.wait_for_timeout(2000)

            # STEP 1: 페이지 내 모든 아코디언 헤더 아이콘 찾기
            self.logger.info("=" * 80)
            self.logger.info("STEP 1: Finding ALL accordion headers with arrow icons...")
            self.logger.info("=" * 80)

            all_headers = await page.query_selector_all('.common-accordion-menu__header')
            self.logger.info(f"Found {len(all_headers)} total accordion headers")

            # STEP 2: 모든 아코디언 헤더를 차근차근 클릭하여 펼치기
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

            self.logger.info(f"✓ Opened {opened_count} accordion sections")

            # STEP 3: 추가 섹션이 있을 수 있으므로 한번 더 확인하고 열기
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

                except Exception as e:
                    continue

            if additional_opened > 0:
                self.logger.info(f"✓ Opened {additional_opened} additional sections on second pass")

            await page.wait_for_timeout(3000)

            self.logger.info("=" * 80)
            self.logger.info("All accordion sections opened! Now extracting curriculum data...")
            self.logger.info("=" * 80)

            # 다시 모든 섹션 가져오기
            section_elements = await page.query_selector_all('.classroom-sidebar-clip__chapter')

            for section_idx, section_elem in enumerate(section_elements, 1):
                try:
                    # 섹션(Part) 제목
                    section_title_elem = await section_elem.query_selector('.classroom-sidebar-clip__chapter__title__text')
                    section_title = await section_title_elem.inner_text() if section_title_elem else f'Section {section_idx}'
                    section_title = section_title.strip()

                    # 완료/전체 강의 수
                    complete_elem = await section_elem.query_selector('.classroom-sidebar-clip__chapter__title__number__complete')
                    total_elem = await section_elem.query_selector('.classroom-sidebar-clip__chapter__title__number__total')
                    complete_count = int(await complete_elem.inner_text()) if complete_elem else 0
                    total_count = int(await total_elem.inner_text()) if total_elem else 0

                    # Chapter들을 찾기
                    chapter_elements = await section_elem.query_selector_all('.classroom-sidebar-clip__chapter__part__title')

                    if chapter_elements and len(chapter_elements) > 0:
                        # Chapter 구조가 있는 경우
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
                        # Chapter 구조가 없는 경우
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

            self.logger.info(f"✓ Extracted {len(curriculum)} sections total")

        except Exception as e:
            self.logger.error(f"Error extracting curriculum: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        return curriculum

    def parse_duration(self, duration_str):
        """시간 문자열을 분 단위로 변환
        예: "25:50" -> 25.83분 (25분 50초)
            "1:30:45" -> 90.75분 (1시간 30분 45초)
        """
        if not duration_str:
            return 0

        total_minutes = 0
        import re

        # "1시간 30분" 형식
        hours_match = re.search(r'(\d+)\s*시간', duration_str)
        minutes_match = re.search(r'(\d+)\s*분', duration_str)

        if hours_match:
            total_minutes += int(hours_match.group(1)) * 60
        if minutes_match:
            total_minutes += int(minutes_match.group(1))

        # "HH:MM:SS" 또는 "MM:SS" 형식
        if ':' in duration_str:
            time_parts = duration_str.strip().split(':')
            if len(time_parts) == 3:  # HH:MM:SS
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                seconds = int(time_parts[2])
                total_minutes = hours * 60 + minutes + round(seconds / 60, 2)
            elif len(time_parts) == 2:  # MM:SS
                minutes = int(time_parts[0])
                seconds = int(time_parts[1])
                total_minutes = minutes + round(seconds / 60, 2)

        return round(total_minutes, 2)

    async def errback(self, failure):
        """에러 처리"""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        self.logger.error(f"✗ Request failed: {failure.request.url}")
