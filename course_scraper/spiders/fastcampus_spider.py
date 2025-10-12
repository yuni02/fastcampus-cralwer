import scrapy
import json
import os
import sys
from scrapy_playwright.page import PageMethod

# credentials.py에서 로그인 정보 가져오기
# course_scraper/course_scraper/spiders/ -> /Users/jennie/PycharmProjects/fastcampus-scrapping/
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
credentials_path = os.path.join(project_root, 'credentials.py')

# 직접 파일을 읽어서 실행
KAKAO_EMAIL = None
KAKAO_PASSWORD = None

if os.path.exists(credentials_path):
    with open(credentials_path, 'r', encoding='utf-8') as f:
        exec_globals = {}
        exec(f.read(), exec_globals)
        KAKAO_EMAIL = exec_globals.get('KAKAO_EMAIL')
        KAKAO_PASSWORD = exec_globals.get('KAKAO_PASSWORD')
else:
    raise FileNotFoundError(f"credentials.py not found at {credentials_path}. Please create it from credentials_example.py")

if not KAKAO_EMAIL or not KAKAO_PASSWORD:
    raise ValueError("KAKAO_EMAIL or KAKAO_PASSWORD not set in credentials.py")


class FastCampusSpider(scrapy.Spider):
    name = 'fastcampus'
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logged_in = False

    def start_requests(self):
        # 첫 번째 요청: 로그인
        yield scrapy.Request(
            'https://fastcampus.co.kr/account/sign-in',
            callback=self.login,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_methods': [
                    PageMethod('wait_for_timeout', 8000),  # 8초 대기 (페이지 로딩 충분히 기다림)
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

            # 초기 페이지 스크린샷
            await page.screenshot(path='screenshot_1_initial.png')
            self.logger.info("✓ Saved screenshot: screenshot_1_initial.png")

            # 1. "카카오로 1초 만에 시작하기" 버튼 클릭
            self.logger.info("Looking for Kakao login button...")

            # 페이지 내용 확인
            page_content = await page.content()
            if '카카오' in page_content:
                self.logger.info("✓ Found '카카오' text in page")

            # 여러 가능한 선택자 시도
            selectors = [
                'button:has-text("카카오로 1초 만에 시작하기")',
                'button:has-text("카카오")',
                'a:has-text("카카오로 1초 만에 시작하기")',
                'a:has-text("카카오")',
                '[class*="kakao"]',
                '[class*="Kakao"]',
                'button[class*="Social"]',
            ]

            clicked = False
            for selector in selectors:
                try:
                    self.logger.info(f"Trying selector: {selector}")
                    await page.click(selector, timeout=5000)
                    self.logger.info(f"✓ Clicked Kakao button with selector: {selector}")
                    clicked = True
                    break
                except Exception as e:
                    self.logger.info(f"  Failed: {str(e)[:100]}")
                    continue

            if not clicked:
                self.logger.error("✗ Could not find Kakao login button")
                await page.screenshot(path='screenshot_error_no_button.png')
                await page.close()
                return

            # 2. 카카오 로그인 페이지 로드 대기
            await page.wait_for_timeout(3000)
            await page.screenshot(path='screenshot_2_kakao_page.png')
            self.logger.info("✓ Saved screenshot: screenshot_2_kakao_page.png")

            current_url = page.url
            self.logger.info(f"Current URL: {current_url}")

            # 3. 이메일 입력
            self.logger.info("Entering email...")
            email_selectors = [
                'input[name="loginId"]',
                'input[type="email"]',
                'input[placeholder*="이메일"]',
                'input[placeholder*="아이디"]',
                '#loginId',
            ]

            email_entered = False
            for selector in email_selectors:
                try:
                    await page.fill(selector, KAKAO_EMAIL, timeout=3000)
                    self.logger.info(f"✓ Entered email with selector: {selector}")
                    email_entered = True
                    break
                except Exception as e:
                    continue

            if not email_entered:
                self.logger.error("✗ Could not enter email")
                await page.screenshot(path='screenshot_error_email.png')
                await page.close()
                return

            # 4. 비밀번호 입력
            self.logger.info("Entering password...")
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                '#password',
            ]

            password_entered = False
            for selector in password_selectors:
                try:
                    await page.fill(selector, KAKAO_PASSWORD, timeout=3000)
                    self.logger.info(f"✓ Entered password with selector: {selector}")
                    password_entered = True
                    break
                except Exception as e:
                    continue

            if not password_entered:
                self.logger.error("✗ Could not enter password")
                await page.screenshot(path='screenshot_error_password.png')
                await page.close()
                return

            await page.wait_for_timeout(1000)
            await page.screenshot(path='screenshot_3_credentials_entered.png')
            self.logger.info("✓ Saved screenshot: screenshot_3_credentials_entered.png")

            # 5. 로그인 버튼 클릭
            self.logger.info("Clicking login button...")
            login_selectors = [
                'button[type="submit"]',
                'button:has-text("로그인")',
                '.btn_confirm',
                'button.submit',
                'input[type="submit"]',
            ]

            login_clicked = False
            for selector in login_selectors:
                try:
                    self.logger.info(f"Trying login button selector: {selector}")
                    await page.click(selector, timeout=3000)
                    self.logger.info(f"✓ Clicked login button with selector: {selector}")
                    login_clicked = True
                    break
                except Exception as e:
                    self.logger.info(f"  Failed: {str(e)[:100]}")
                    continue

            if not login_clicked:
                self.logger.error("✗ Could not click login button")
                await page.screenshot(path='screenshot_error_login_button.png')
                await page.close()
                return

            # 6. 2단계 인증을 위한 대기 (90초)
            await page.wait_for_timeout(3000)
            await page.screenshot(path='screenshot_4_after_login_click.png')
            self.logger.info("✓ Saved screenshot: screenshot_4_after_login_click.png")

            self.logger.info("=" * 70)
            self.logger.info("⚠️  KakaoTalk 앱에서 2단계 인증을 승인해주세요! ⚠️")
            self.logger.info("90초 대기 중... 앱에서 빠르게 승인해주세요!")
            self.logger.info("=" * 70)

            # 2FA 승인을 위해 대기하면서 Continue 버튼 모니터링
            max_wait_time = 90  # 90초
            check_interval = 2  # 2초마다 체크

            for i in range(0, max_wait_time, check_interval):
                await page.wait_for_timeout(check_interval * 1000)

                # Continue 버튼 찾기 (노란색 버튼)
                continue_selectors = [
                    'button.btn_confirm',  # Kakao의 노란색 확인 버튼
                    'button:has-text("Continue")',
                    'button:has-text("계속")',
                    'button:has-text("확인")',
                    'button[type="submit"]:has-text("계속")',
                    'a.btn_confirm',
                ]

                for selector in continue_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn:
                            # 버튼이 보이는지 확인
                            is_visible = await btn.is_visible()
                            if is_visible:
                                self.logger.info(f"✓ Found Continue button with selector: {selector}")
                                await btn.click()
                                self.logger.info("✓ Clicked Continue button!")
                                await page.wait_for_timeout(3000)
                                break
                    except Exception:
                        continue

                # FastCampus로 리디렉트되었는지 확인
                current_url = page.url
                if 'fastcampus.co.kr' in current_url and 'sign-in' not in current_url and 'kakao' not in current_url:
                    self.logger.info(f"✓ Successfully redirected to FastCampus! (after {i}s)")
                    break

            await page.screenshot(path='screenshot_5_after_2fa.png')
            self.logger.info("✓ Saved screenshot: screenshot_5_after_2fa.png")

            current_url = page.url
            page_title = await page.title()
            self.logger.info(f"Current URL after login: {current_url}")
            self.logger.info(f"Page title: {page_title}")

            # 로그인 성공 확인
            if 'sign-in' not in current_url and '인증' not in page_title:
                self.logger.info("✓ Login successful!")
                self.logged_in = True

                # 페이지가 완전히 로드될 때까지 짧게 대기
                await page.wait_for_timeout(1000)

                # 추가 네비게이션: 마이페이지 > 내강의장으로 이동
                try:
                    # 1. 헤더에서 "장윤경님" 클릭
                    self.logger.info("Clicking user menu (장윤경님)...")
                    user_menu_selectors = [
                        'button:has-text("장윤경")',
                        'a:has-text("장윤경")',
                        '[class*="profile"]',
                        '[class*="Profile"]',
                        'button[class*="user"]',
                        'button[class*="User"]',
                    ]

                    clicked_user_menu = False
                    for selector in user_menu_selectors:
                        try:
                            await page.click(selector, timeout=3000)
                            self.logger.info(f"✓ Clicked user menu with selector: {selector}")
                            clicked_user_menu = True
                            break
                        except Exception:
                            continue

                    if not clicked_user_menu:
                        self.logger.error("✗ Could not click user menu")
                        await page.screenshot(path='screenshot_error_user_menu.png')
                    else:
                        # 드롭다운 메뉴가 완전히 렌더링될 때까지 대기 (애니메이션 포함)
                        await page.wait_for_timeout(1000)
                        await page.screenshot(path='screenshot_6_user_menu_opened.png')
                        self.logger.info("✓ Saved screenshot: screenshot_6_user_menu_opened.png")

                        # 2. "마이페이지" 클릭 - 더 많은 선택자와 대기 시간 추가
                        self.logger.info("Clicking '마이페이지'...")
                        mypage_selectors = [
                            'a:has-text("마이페이지")',
                            'button:has-text("마이페이지")',
                            '[href*="mypage"]',
                            '[href*="my-page"]',
                            'li:has-text("마이페이지") a',
                            'div:has-text("마이페이지") a',
                            '[class*="menu"] a:has-text("마이페이지")',
                            '[class*="dropdown"] a:has-text("마이페이지")',
                        ]

                        clicked_mypage = False
                        for selector in mypage_selectors:
                            try:
                                # 요소가 보이는지 먼저 확인
                                elem = await page.query_selector(selector)
                                if elem:
                                    is_visible = await elem.is_visible()
                                    if is_visible:
                                        await elem.click()
                                        self.logger.info(f"✓ Clicked 마이페이지 with selector: {selector}")
                                        clicked_mypage = True
                                        break
                            except Exception as e:
                                self.logger.debug(f"  Failed selector {selector}: {str(e)[:50]}")
                                continue

                        if not clicked_mypage:
                            self.logger.error("✗ Could not click 마이페이지")
                            await page.screenshot(path='screenshot_error_mypage.png')
                            # 페이지의 HTML 일부를 로그로 출력하여 디버깅
                            page_content = await page.content()
                            if '마이페이지' in page_content:
                                self.logger.info("Found '마이페이지' text in page, but couldn't click")
                            else:
                                self.logger.warning("'마이페이지' text not found in page")
                        else:
                            await page.wait_for_timeout(1000)
                            await page.screenshot(path='screenshot_7_mypage.png')
                            self.logger.info("✓ Saved screenshot: screenshot_7_mypage.png")

                            # 3. 왼쪽 메뉴에서 "내 강의장" 클릭
                            self.logger.info("Clicking '내 강의장'...")
                            classroom_menu_selectors = [
                                'a:has-text("내 강의장")',
                                'button:has-text("내 강의장")',
                                '[href*="classroom"]',
                                'nav a:has-text("내 강의장")',
                            ]

                            clicked_classroom_menu = False
                            for selector in classroom_menu_selectors:
                                try:
                                    await page.click(selector, timeout=2000)
                                    self.logger.info(f"✓ Clicked 내 강의장 with selector: {selector}")
                                    clicked_classroom_menu = True
                                    break
                                except Exception:
                                    continue

                            if not clicked_classroom_menu:
                                self.logger.error("✗ Could not click 내 강의장")
                                await page.screenshot(path='screenshot_error_classroom_menu.png')
                            else:
                                await page.wait_for_timeout(1500)
                                await page.screenshot(path='screenshot_8_classroom_list.png')
                                self.logger.info("✓ Saved screenshot: screenshot_8_classroom_list.png")

                                current_url = page.url
                                self.logger.info(f"Current URL after navigation: {current_url}")

                                # 4. "수강중" 탭 확인/클릭
                                self.logger.info("Checking '수강중' tab...")
                                try:
                                    # 수강중 탭이 이미 선택되어 있는지 확인, 아니면 클릭
                                    tab_selectors = [
                                        'button:has-text("수강중")',
                                        'a:has-text("수강중")',
                                        '[role="tab"]:has-text("수강중")',
                                    ]

                                    for selector in tab_selectors:
                                        try:
                                            await page.click(selector, timeout=2000)
                                            self.logger.info(f"✓ Clicked 수강중 tab")
                                            await page.wait_for_timeout(2000)
                                            break
                                        except Exception:
                                            continue

                                    await page.screenshot(path='screenshot_9_studying_tab.png')
                                    self.logger.info("✓ Saved screenshot: screenshot_9_studying_tab.png")

                                    # 5. 페이지 스크롤하여 모든 강의 로드
                                    self.logger.info("Scrolling to load all courses...")

                                    # 페이지 끝까지 스크롤
                                    previous_height = 0
                                    scroll_attempts = 0
                                    max_scroll_attempts = 20  # 최대 20번 스크롤

                                    while scroll_attempts < max_scroll_attempts:
                                        # 현재 페이지 높이
                                        current_height = await page.evaluate('document.body.scrollHeight')

                                        if current_height == previous_height:
                                            # 더 이상 로드할 콘텐츠가 없음
                                            break

                                        # 페이지 끝까지 스크롤
                                        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                                        await page.wait_for_timeout(2000)  # 콘텐츠 로딩 대기

                                        previous_height = current_height
                                        scroll_attempts += 1
                                        self.logger.info(f"  Scrolled {scroll_attempts} times...")

                                    # 맨 위로 돌아가기
                                    await page.evaluate('window.scrollTo(0, 0)')
                                    await page.wait_for_timeout(1000)

                                    # 6. 수강중 강의 목록 가져오기
                                    self.logger.info("Getting list of courses by clicking buttons with popup detection...")

                                    course_boxes = await page.query_selector_all('.vn-me-courses__box')
                                    total_courses = len(course_boxes)  # 모든 강의
                                    self.logger.info(f"Found {total_courses} course boxes")

                                    course_urls = []

                                    for idx in range(total_courses):
                                        # 매번 새로 쿼리 (DOM이 변경될 수 있음)
                                        course_boxes = await page.query_selector_all('.vn-me-courses__box')
                                        box = course_boxes[idx]

                                        # 강의 제목 추출
                                        title_elem = await box.query_selector('.vn-me-courses__title')
                                        title = await title_elem.inner_text() if title_elem else f'Course {idx + 1}'
                                        self.logger.info(f"  {idx + 1}/{total_courses}. {title}")

                                        # 버튼 찾기
                                        classroom_btn = await box.query_selector('button[data-e2e="classroom-enter-button"]')

                                        if classroom_btn:
                                            # 새 페이지나 팝업이 열리는지 감지
                                            try:
                                                self.logger.info(f"     Clicking and monitoring for new pages/popups...")

                                                # 새 페이지 열림을 감지 (팝업이나 새 탭)
                                                async with page.context.expect_page(timeout=5000) as page_info:
                                                    await classroom_btn.click()

                                                # 새 페이지가 열렸음
                                                new_page = await page_info.value
                                                await new_page.wait_for_load_state('load', timeout=10000)

                                                course_url = new_page.url
                                                self.logger.info(f"     ✓ New page opened: {course_url}")

                                                if '/classroom/' in course_url:
                                                    course_urls.append(course_url)
                                                    self.logger.info(f"     ✓ Added classroom URL")

                                                # 새 페이지 닫기
                                                await new_page.close()
                                                await page.wait_for_timeout(1000)

                                            except Exception as e:
                                                self.logger.warning(f"     No new page opened, trying direct navigation...")

                                                # 새 페이지가 열리지 않으면 현재 페이지에서 navigation 시도
                                                try:
                                                    current_url_before = page.url
                                                    await classroom_btn.click()
                                                    await page.wait_for_timeout(3000)
                                                    current_url_after = page.url

                                                    if current_url_before != current_url_after and '/classroom/' in current_url_after:
                                                        self.logger.info(f"     ✓ Navigated to: {current_url_after}")
                                                        course_urls.append(current_url_after)

                                                        # 뒤로 가기
                                                        await page.go_back()
                                                        await page.wait_for_timeout(2000)
                                                    else:
                                                        self.logger.warning(f"     URL didn't change: {current_url_after}")
                                                except Exception as nav_error:
                                                    self.logger.error(f"     Navigation failed: {str(nav_error)[:100]}")

                                    self.logger.info(f"✓ Found {len(course_urls)} total course URLs")
                                    for idx, url in enumerate(course_urls, 1):
                                        self.logger.info(f"  {idx}. {url}")

                                    # 페이지 닫기 전에 course_urls를 저장
                                    self.course_urls_to_crawl = course_urls

                                except Exception as e:
                                    self.logger.error(f"Failed to get course list: {e}")
                                    import traceback
                                    self.logger.error(traceback.format_exc())

                except Exception as e:
                    self.logger.error(f"Navigation failed: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())

                # 페이지 닫기
                await page.close()

                # 가져온 강의 URL들을 크롤링
                if hasattr(self, 'course_urls_to_crawl') and self.course_urls_to_crawl:
                    self.logger.info(f"Starting to crawl {len(self.course_urls_to_crawl)} courses...")

                    for url in self.course_urls_to_crawl:
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
                    self.logger.warning("No course URLs found to crawl")
            else:
                self.logger.error("✗ Login failed!")
                await page.close()

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if page:
                await page.screenshot(path='screenshot_error_exception.png')
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

            # 스크린샷 저장
            if page:
                course_id = response.url.split('/classroom/')[-1].split('?')[0]
                await page.screenshot(path=f'screenshot_course_{course_id}.png')
                self.logger.info(f"✓ Saved screenshot: screenshot_course_{course_id}.png")

            # Course ID 추출
            course_id = response.url.split('/classroom/')[-1].split('?')[0]

            # 강의 제목 추출 - 페이지 타이틀에서 추출 (가장 확실함)
            course_title = None

            # 페이지 타이틀: "패스트캠퍼스 온라인 강의 - 지금 당장 나만의 서비스 런칭! 13가지 초!고퀄리티 웹 서비스로 Cursor AI 마스터"
            if ' - ' in page_title:
                course_title = page_title.split(' - ', 1)[1].strip()
            elif '|' in page_title:
                course_title = page_title.split('|')[0].strip()

            # 만약 추출 실패하면 페이지 상단에서 h1 찾기
            if not course_title or course_title == page_title or len(course_title) < 10:
                if page:
                    try:
                        # 상단 헤더의 제목
                        title_elem = await page.query_selector('header h1, h1')
                        if title_elem:
                            title_text = await title_elem.inner_text()
                            if title_text and len(title_text) > 10:
                                course_title = title_text.strip()
                    except:
                        pass

            # 최종 폴백
            if not course_title or len(course_title) < 5:
                course_title = f'Course {course_id}'

            course_title = course_title.strip()
            self.logger.info(f"Course: {course_title}")

            # 진도율, 학습시간, 전체시간 추출 - Playwright로 상단 바에서 찾기
            progress_rate = 0.0
            study_time = 0
            total_lecture_time = 0

            if page:
                # 상단 바의 텍스트 전체 가져오기
                try:
                    # "수강률 0%", "수강시간 0:00", "강의시간 23:08:50" 같은 텍스트 찾기
                    page_text = await page.inner_text('body')

                    # 수강률 추출
                    import re
                    progress_match = re.search(r'수강률\s*(\d+(?:\.\d+)?)\s*%', page_text)
                    if progress_match:
                        progress_rate = float(progress_match.group(1))
                        self.logger.info(f"  Progress: {progress_rate}%")

                    # 수강시간 추출 (HH:MM:SS 또는 MM:SS 형식)
                    study_match = re.search(r'수강시간\s*(\d+):(\d+)(?::(\d+))?', page_text)
                    if study_match:
                        first = int(study_match.group(1))
                        second = int(study_match.group(2))
                        third = int(study_match.group(3)) if study_match.group(3) else None

                        if third is not None:  # HH:MM:SS 형식
                            study_time = first * 60 + second + round(third / 60, 2)
                        else:  # MM:SS 형식 (콜론이 1개만 있으면 분:초로 간주)
                            study_time = first + round(second / 60, 2)

                        self.logger.info(f"  Study time: {study_time} min")

                    # 강의시간 추출 (23:08:50 형식)
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

            # 커리큘럼 추출 (섹션과 강의 목록)
            curriculum = await self.extract_curriculum_playwright(page) if page else self.extract_curriculum(response)

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
                            course_title=course_title,  # 추가
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
            # 페이지 닫기
            if page:
                await page.close()

    async def extract_curriculum_playwright(self, page):
        """Playwright를 사용하여 커리큘럼 추출 (JavaScript 렌더링된 콘텐츠)"""
        curriculum = []

        try:
            # 오른쪽 사이드바의 커리큘럼 영역에서 Part 단위로 추출
            # 스크린샷 기준: Part 1, Part 2, Part 3... 등의 섹션들

            # 전체 페이지 텍스트를 가져와서 파싱 (더 안정적)
            page_content = await page.content()

            # Part로 시작하는 섹션들 찾기
            import re

            # Part 1, Part 2 등의 패턴 찾기
            # 예: "Part 1. 커서 시작하기: 환경 셋업과 기초 개념 51:53"
            part_pattern = r'Part\s+(\d+)\.\s+([^\d]+?)\s+(\d+:\d+(?::\d+)?)'

            # 챕터/강의 패턴
            # 예: "Ch 1. Cursor 25:20" 또는 "01. Cursor 소개 및 설치 22:36"
            lecture_pattern = r'(?:Ch\s+\d+\.|^\d+\.)\s+(.+?)\s+(\d+:\d+)'

            # 더 나은 방법: 오른쪽 사이드바의 실제 DOM 요소들을 찾기
            # FastCampus는 커리큘럼을 리스트 형태로 렌더링함

            # 섹션(Part) 요소들 찾기
            section_elements = await page.query_selector_all('[class*="curriculum"] > div, aside [role="list"] > div, aside > div > div')

            if not section_elements:
                # 다른 선택자 시도
                section_elements = await page.query_selector_all('aside li, [class*="sidebar"] li, [class*="curriculum"] li')

            self.logger.info(f"  Found {len(section_elements)} potential section elements")

            # DOM 구조가 복잡하므로, 페이지 텍스트 전체를 가져와서 정규식으로 파싱
            full_text = await page.inner_text('body')

            # 디버깅: 텍스트의 일부를 파일에 저장
            with open('curriculum_text_debug.txt', 'w', encoding='utf-8') as f:
                f.write(full_text[:10000])  # 처음 10000자만

            # Part로 시작하는 라인들 찾기
            lines = full_text.split('\n')
            current_section = None

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # Part X. 로 시작하는 섹션 찾기
                # 예: "Part 1. 커서 시작하기: 환경 셋업과 기초 개념 51:53"
                # 더 유연한 패턴: Part 뒤에 숫자, 점, 텍스트, 시간
                part_match = re.match(r'^Part\s+(\d+)\.\s+(.+?)\s+(\d+:\d+(?::\d+)?)\s*$', line)
                if part_match:
                    # 이전 섹션 저장
                    if current_section and current_section['lessons']:
                        curriculum.append(current_section)

                    # 새 섹션 시작
                    part_num = part_match.group(1)
                    section_name = part_match.group(2).strip()
                    section_duration = part_match.group(3).strip()
                    current_section = {
                        'section': f"Part {part_num}. {section_name}",
                        'lessons': [],
                        'lesson_count': 0
                    }
                    self.logger.debug(f"    Found section: {current_section['section']}")
                    continue

                # 현재 섹션이 있고, 강의 라인인 경우
                if current_section:
                    # "Ch X. " 또는 "숫자. "로 시작하는 강의 찾기
                    # 예: "Ch 1. Cursor 25:20" 또는 "01. Cursor 소개 및 설치 22:36"
                    lecture_match = re.match(r'^((?:Ch\s+\d+\.|\d+\.)\s+.+?)\s+(\d+:\d+)\s*$', line)
                    if lecture_match:
                        lecture_title = lecture_match.group(1).strip()
                        lecture_duration = lecture_match.group(2).strip()

                        # 완료 여부 확인 (다음 라인에 "0 / 4" 같은 패턴이 있을 수 있음)
                        is_completed = False  # 기본값

                        current_section['lessons'].append({
                            'title': lecture_title,
                            'duration': lecture_duration,
                            'is_completed': is_completed
                        })
                        self.logger.debug(f"      Found lecture: {lecture_title}")

            # 마지막 섹션 저장
            if current_section and current_section['lessons']:
                curriculum.append(current_section)

            # lesson_count 업데이트
            for section in curriculum:
                section['lesson_count'] = len(section['lessons'])

        except Exception as e:
            self.logger.error(f"Error extracting curriculum with Playwright: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        return curriculum

    def parse_duration(self, duration_str):
        """시간 문자열을 분 단위로 변환
        예: "1시간 30분" -> 90, "25:20" -> 25.33, "1:30:45" -> 90.75
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

        # "HH:MM:SS" 또는 "MM:SS" 또는 "HH:MM" 형식
        if ':' in duration_str:
            time_parts = duration_str.strip().split(':')
            if len(time_parts) == 3:  # HH:MM:SS
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                seconds = int(time_parts[2])
                total_minutes = hours * 60 + minutes + seconds / 60
            elif len(time_parts) == 2:  # MM:SS 또는 HH:MM
                # 첫 번째 숫자가 크면 MM:SS, 작으면 HH:MM으로 간주
                first = int(time_parts[0])
                second = int(time_parts[1])
                if first > 60:  # MM:SS 형식
                    total_minutes = first + second / 60
                else:  # HH:MM 형식
                    total_minutes = first * 60 + second

        return total_minutes

    async def errback(self, failure):
        """에러 처리"""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        self.logger.error(f"✗ Request failed: {failure.request.url}")

    def extract_title(self, response):
        """강의 제목 추출"""
        title = response.css('h1.title::text').get()
        if not title:
            title = response.css('h1::text').get()
        if not title:
            title = response.xpath('//h1/text()').get()
        return title.strip() if title else 'Unknown Title'

    def extract_curriculum(self, response):
        """커리큘럼 추출 로직"""
        curriculum = []

        # 방법 1: CSS 선택자로 섹션 추출
        sections = response.css('.curriculum-section, .course-section, section.curriculum')

        for section in sections:
            section_title = section.css('.section-title::text, h2::text, h3::text').get()
            lessons = section.css('.lesson-item, .curriculum-item, li')

            lesson_list = []
            for lesson in lessons:
                lesson_title = lesson.css('.lesson-title::text, a::text, span::text').get()
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

        # 방법 2: JSON-LD 데이터 추출 시도
        if not curriculum:
            json_ld = response.css('script[type="application/ld+json"]::text').getall()
            for json_data in json_ld:
                try:
                    data = json.loads(json_data)
                    if isinstance(data, dict) and 'hasCourseInstance' in data:
                        # 구조화된 데이터에서 커리큘럼 추출
                        pass
                except json.JSONDecodeError:
                    continue

        # 방법 3: 일반적인 리스트 구조 추출
        if not curriculum:
            sections = response.css('ul.curriculum, ol.curriculum, div.curriculum ul, div.curriculum ol')
            for idx, section in enumerate(sections, 1):
                lessons = section.css('li')
                lesson_list = [
                    {
                        'title': lesson.css('::text').get('').strip(),
                        'duration': None
                    }
                    for lesson in lessons if lesson.css('::text').get('').strip()
                ]

                if lesson_list:
                    curriculum.append({
                        'section': f'Section {idx}',
                        'lessons': lesson_list,
                        'lesson_count': len(lesson_list)
                    })

        return curriculum
