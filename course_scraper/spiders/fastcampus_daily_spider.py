import scrapy
import os
import pymysql
from scrapy_playwright.page import PageMethod
from datetime import datetime

# credentials.py에서 로그인 정보 가져오기
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
credentials_path = os.path.join(project_root, 'credentials.py')

KAKAO_EMAIL = None
KAKAO_PASSWORD = None
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = ''
MYSQL_DATABASE = 'crawler'

if os.path.exists(credentials_path):
    with open(credentials_path, 'r', encoding='utf-8') as f:
        exec_globals = {}
        exec(f.read(), exec_globals)
        KAKAO_EMAIL = exec_globals.get('KAKAO_EMAIL')
        KAKAO_PASSWORD = exec_globals.get('KAKAO_PASSWORD')
        MYSQL_HOST = exec_globals.get('MYSQL_HOST', MYSQL_HOST)
        MYSQL_PORT = exec_globals.get('MYSQL_PORT', MYSQL_PORT)
        MYSQL_USER = exec_globals.get('MYSQL_USER', MYSQL_USER)
        MYSQL_PASSWORD = exec_globals.get('MYSQL_PASSWORD', MYSQL_PASSWORD)
        MYSQL_DATABASE = exec_globals.get('MYSQL_DATABASE', MYSQL_DATABASE)
else:
    raise FileNotFoundError(f"credentials.py not found")

if not KAKAO_EMAIL or not KAKAO_PASSWORD:
    raise ValueError("KAKAO_EMAIL or KAKAO_PASSWORD not set")


class FastCampusDailySpider(scrapy.Spider):
    """
    매일 실행: DB에서 강의 URL을 가져와서 진도율과 커리큘럼을 업데이트하는 spider
    """
    name = 'fastcampus_daily'
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logged_in = False
        self.course_urls = []

        # 명령줄 옵션
        self.target_only = kwargs.get('target_only', 'false').lower() == 'true'
        self.skip_recent = kwargs.get('skip_recent', 'false').lower() == 'true'
        self.course_id = kwargs.get('course_id', None)

    def start_requests(self):
        # DB에서 강의 URL 가져오기
        try:
            connection = pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                charset='utf8mb4'
            )

            with connection.cursor() as cursor:
                # 쿼리 조건 동적 생성
                conditions = ["url IS NOT NULL"]

                # 옵션 1: 특정 course_id만 크롤링
                if self.course_id:
                    conditions.append(f"course_id = {self.course_id}")
                    self.logger.info(f"Filtering by course_id: {self.course_id}")

                # 옵션 2: 목표 강의만 크롤링
                elif self.target_only:
                    conditions.append("is_target_course = 1")
                    self.logger.info("Filtering: is_target_course = 1")

                # 옵션 3: 최근 업데이트된 강의 제외 (24시간 이내)
                if self.skip_recent and not self.course_id:
                    conditions.append("(updated_at < DATE_SUB(NOW(), INTERVAL 1 DAY) OR updated_at IS NULL)")
                    self.logger.info("Filtering: skip recently updated courses (< 24h)")

                query = f"SELECT course_id, url FROM courses WHERE {' AND '.join(conditions)}"
                self.logger.info(f"SQL: {query}")

                cursor.execute(query)
                rows = cursor.fetchall()
                self.course_urls = [{'course_id': row[0], 'url': row[1]} for row in rows]

            connection.close()
            self.logger.info(f"✓ Loaded {len(self.course_urls)} course URLs from DB")

        except Exception as e:
            self.logger.error(f"Failed to load URLs from DB: {e}")
            return

        if not self.course_urls:
            self.logger.warning("No course URLs found in DB. Run fastcampus_discover first.")
            return

        # 로그인 시작
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

                # 각 강의 URL을 크롤링
                self.logger.info(f"Starting to crawl {len(self.course_urls)} courses...")

                for course_data in self.course_urls:
                    url = course_data['url']
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

            # CourseItem 생성 (courses 테이블 업데이트용)
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
                for section_idx, section in enumerate(curriculum, 1):
                    section_title = section.get('section', f'Section {section_idx}')
                    lessons = section.get('lessons', [])

                    self.logger.info(f"  Section {section_idx}: {section_title} ({len(lessons)} lectures)")

                    for lecture_idx, lesson in enumerate(lessons, 1):
                        sort_order += 1

                        lecture_title = lesson.get('title', f'Lecture {lecture_idx}')
                        lecture_duration = lesson.get('duration', None)
                        lecture_time = self.parse_duration(lecture_duration) if lecture_duration else 0
                        is_completed = lesson.get('is_completed', False)

                        lecture_item = LectureItem(
                            course_id=course_id,
                            course_title=course_title,
                            section_number=section_idx,
                            section_title=section_title,
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
        """Playwright를 사용하여 커리큘럼 추출"""
        curriculum = []

        try:
            # 각 섹션(챕터) 찾기
            chapter_elements = await page.query_selector_all('.classroom-sidebar-clip__chapter')
            self.logger.info(f"Found {len(chapter_elements)} chapters")

            # 모든 섹션 열기 (닫혀있는 섹션들) - 개선된 버전
            self.logger.info("Opening all accordion sections...")
            for idx, chapter in enumerate(chapter_elements):
                try:
                    # 방법 1: 아코디언 헤더 클릭
                    header = await chapter.query_selector('.common-accordion-menu__header')
                    if header:
                        # 열려있는지 확인
                        menu = await chapter.query_selector('.common-accordion-menu')
                        class_attr = await menu.get_attribute('class') if menu else ''

                        # 닫혀있으면 클릭
                        if 'common-accordion-menu--open' not in class_attr:
                            self.logger.info(f"  Opening section {idx + 1} (closed)...")

                            # 여러 방법으로 클릭 시도
                            clicked = False

                            # 시도 1: 헤더 직접 클릭
                            try:
                                await header.click(timeout=2000)
                                clicked = True
                            except:
                                pass

                            # 시도 2: 화살표 아이콘 클릭
                            if not clicked:
                                try:
                                    arrow = await chapter.query_selector('.common-accordion-menu__header__arrow-icon')
                                    if arrow:
                                        await arrow.click(timeout=2000)
                                        clicked = True
                                except:
                                    pass

                            # 시도 3: JavaScript로 강제 클릭
                            if not clicked:
                                try:
                                    await header.evaluate('el => el.click()')
                                    clicked = True
                                except:
                                    pass

                            if clicked:
                                await page.wait_for_timeout(800)  # 애니메이션 대기 증가
                                self.logger.info(f"  ✓ Section {idx + 1} opened")
                            else:
                                self.logger.warning(f"  ✗ Could not open section {idx + 1}")
                        else:
                            self.logger.info(f"  Section {idx + 1} already open")

                except Exception as e:
                    self.logger.warning(f"  Error opening section {idx + 1}: {e}")
                    continue

            # 모든 섹션이 열린 후 충분한 대기
            self.logger.info("Waiting for all sections to expand...")
            await page.wait_for_timeout(2000)  # 대기 시간 증가

            # 다시 모든 섹션 가져오기
            chapter_elements = await page.query_selector_all('.classroom-sidebar-clip__chapter')

            for section_idx, chapter in enumerate(chapter_elements, 1):
                try:
                    # 섹션 제목
                    section_title_elem = await chapter.query_selector('.classroom-sidebar-clip__chapter__title__text')
                    section_title = await section_title_elem.inner_text() if section_title_elem else f'Section {section_idx}'
                    section_title = section_title.strip()

                    # 완료/전체 강의 수
                    complete_elem = await chapter.query_selector('.classroom-sidebar-clip__chapter__title__number__complete')
                    total_elem = await chapter.query_selector('.classroom-sidebar-clip__chapter__title__number__total')
                    complete_count = int(await complete_elem.inner_text()) if complete_elem else 0
                    total_count = int(await total_elem.inner_text()) if total_elem else 0

                    # 섹션 총 시간
                    playtime_elem = await chapter.query_selector('.classroom-sidebar-clip__chapter__clip-playtime')
                    section_playtime = await playtime_elem.inner_text() if playtime_elem else ''

                    # 해당 섹션의 강의들 찾기
                    lecture_elements = await chapter.query_selector_all('.classroom-sidebar-clip__chapter__clip')
                    lessons = []

                    self.logger.info(f"  Section {section_idx}: {section_title} ({complete_count}/{total_count}) - {len(lecture_elements)} lectures")

                    for lecture_idx, lecture_elem in enumerate(lecture_elements, 1):
                        try:
                            # 강의 제목
                            title_elem = await lecture_elem.query_selector('.classroom-sidebar-clip__chapter__clip__title')
                            lecture_title = await title_elem.inner_text() if title_elem else f'Lecture {lecture_idx}'
                            lecture_title = lecture_title.strip()

                            # 강의 시간
                            time_elem = await lecture_elem.query_selector('.classroom-sidebar-clip__chapter__clip__time')
                            lecture_duration = await time_elem.inner_text() if time_elem else ''
                            lecture_duration = lecture_duration.strip()

                            # 완료 여부 확인
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
