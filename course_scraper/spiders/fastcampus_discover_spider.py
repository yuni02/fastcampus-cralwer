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


class FastCampusDiscoverSpider(scrapy.Spider):
    """
    월 1회 실행: 새로운 강의를 찾아서 courses 테이블에 저장하는 spider
    """
    name = 'fastcampus_discover'
    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logged_in = False

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
            await page.screenshot(path='screenshot_1_initial.png')

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

            # 카카오 로그인 페이지 로드 대기
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
                await page.wait_for_timeout(1000)

                # 내 강의장으로 이동
                try:
                    self.logger.info("Navigating to /me/courses...")
                    await page.goto('https://fastcampus.co.kr/me/courses', wait_until='domcontentloaded')
                    await page.wait_for_timeout(2000)

                    current_url = page.url
                    self.logger.info(f"✓ Navigated to: {current_url}")
                    await page.screenshot(path='screenshot_discover_courses_page.png')

                    # 수강중 탭 클릭
                    tab_selectors = ['button:has-text("수강중")', 'a:has-text("수강중")', '[role="tab"]:has-text("수강중")']
                    for selector in tab_selectors:
                        try:
                            await page.click(selector, timeout=2000)
                            self.logger.info(f"✓ Clicked 수강중 tab")
                            await page.wait_for_timeout(2000)
                            break
                        except Exception:
                            continue

                    # 페이지 스크롤하여 모든 강의 로드
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

                    # 강의 목록 수집 (개선된 버전 - 직접 URL 추출)
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

                        # 방법 1: <a> 태그에서 URL 추출 시도
                        try:
                            link = await box.query_selector('a[href*="/classroom/"]')
                            if link:
                                href = await link.get_attribute('href')
                                if href and '/classroom/' in href:
                                    # 상대 경로면 절대 경로로 변환
                                    if href.startswith('/'):
                                        course_url = f'https://fastcampus.co.kr{href}'
                                    else:
                                        course_url = href
                                    self.logger.info(f"     ✓ Method 1: Found URL from <a> tag: {course_url}")
                        except Exception as e:
                            self.logger.debug(f"     Method 1 failed: {e}")

                        # 방법 2: 버튼의 data 속성에서 course_id 추출 시도
                        if not course_url:
                            try:
                                classroom_btn = await box.query_selector('button[data-e2e="classroom-enter-button"]')
                                if classroom_btn:
                                    # data-course-id, data-id 등 확인
                                    for attr in ['data-course-id', 'data-id', 'data-key']:
                                        course_id = await classroom_btn.get_attribute(attr)
                                        if course_id:
                                            course_url = f'https://fastcampus.co.kr/classroom/{course_id}'
                                            self.logger.info(f"     ✓ Method 2: Extracted course_id from {attr}: {course_id}")
                                            break
                            except Exception as e:
                                self.logger.debug(f"     Method 2 failed: {e}")

                        # 방법 3: JavaScript evaluate로 데이터 추출
                        if not course_url:
                            try:
                                course_url = await box.evaluate('''
                                    (element) => {
                                        // <a> 태그 찾기
                                        const link = element.querySelector('a[href*="/classroom/"]');
                                        if (link) return link.href;

                                        // data 속성 찾기
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
                                    self.logger.info(f"     ✓ Method 3: Extracted URL via JavaScript: {course_url}")
                            except Exception as e:
                                self.logger.debug(f"     Method 3 failed: {e}")

                        # 방법 4: 실패 시 기존 방식 (새 탭 열기) - Fallback
                        if not course_url:
                            self.logger.info(f"     Fallback: Using new tab method...")
                            classroom_btn = await box.query_selector('button[data-e2e="classroom-enter-button"]')
                            if classroom_btn:
                                try:
                                    async with page.context.expect_page(timeout=5000) as page_info:
                                        await classroom_btn.click()

                                    new_page = await page_info.value
                                    await new_page.wait_for_load_state('load', timeout=10000)
                                    course_url = new_page.url
                                    self.logger.info(f"     ✓ Method 4: Got URL from new page: {course_url}")

                                    await new_page.close()
                                    await page.wait_for_timeout(1000)

                                except Exception as e:
                                    self.logger.warning(f"     All methods failed for course {idx + 1}: {e}")

                        # URL을 찾았으면 리스트에 추가
                        if course_url and '/classroom/' in course_url:
                            course_urls.append(course_url)
                        else:
                            self.logger.warning(f"     ✗ Could not extract URL for course {idx + 1}")

                    self.logger.info(f"✓ Found {len(course_urls)} total course URLs")

                    # courses 테이블에 저장할 아이템 생성
                    from course_scraper.items import CourseItem

                    for idx, url in enumerate(course_urls, start=1):
                        course_id = url.split('/classroom/')[-1].split('?')[0]

                        # 기본 정보만 저장 (제목은 나중에 daily spider에서 업데이트)
                        course_item = CourseItem(
                            course_id=course_id,
                            course_title=f'Course {course_id}',  # placeholder
                            progress_rate=0.0,
                            study_time=0,
                            total_lecture_time=0,
                            url=url,
                            display_order=idx  # 강의 표시 순서 저장
                        )
                        yield course_item

                except Exception as e:
                    self.logger.error(f"Navigation failed: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())

                await page.close()
            else:
                self.logger.error("✗ Login failed!")
                await page.close()

        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if page:
                await page.close()

    async def errback(self, failure):
        """에러 처리"""
        page = failure.request.meta.get('playwright_page')
        if page:
            await page.close()
        self.logger.error(f"✗ Request failed: {failure.request.url}")
