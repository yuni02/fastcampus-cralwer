import scrapy
import os
from scrapy_playwright.page import PageMethod

# credentials.py에서 로그인 정보 가져오기
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
credentials_path = os.path.join(project_root, 'credentials.py')

KAKAO_EMAIL = None
KAKAO_PASSWORD = None

if os.path.exists(credentials_path):
    with open(credentials_path, 'r', encoding='utf-8') as f:
        exec_globals = {}
        exec(f.read(), exec_globals)
        KAKAO_EMAIL = exec_globals.get('KAKAO_EMAIL')
        KAKAO_PASSWORD = exec_globals.get('KAKAO_PASSWORD')


class FastCampusTestSpider(scrapy.Spider):
    """
    테스트용: 한 개 강의만 크롤링하여 커리큘럼 구조 파악
    """
    name = 'fastcampus_test'

    # 테스트할 강의 URL
    TEST_URL = 'https://fastcampus.co.kr/classroom/201998'

    custom_settings = {
        'DOWNLOAD_DELAY': 3,
        'CONCURRENT_REQUESTS': 1,  # 한 번에 하나만
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'ITEM_PIPELINES': {
            "course_scraper.pipelines.MySQLPipeline": 300,
        },  # 파이프라인 활성화
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

                # 테스트 URL로 이동
                yield scrapy.Request(
                    self.TEST_URL,
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
        """테스트: 커리큘럼 추출 및 DB 저장"""
        page = response.meta.get('playwright_page')

        try:
            self.logger.info(f"=" * 80)
            self.logger.info(f"Testing curriculum extraction for: {response.url}")
            self.logger.info(f"=" * 80)

            # 페이지가 완전히 로드될 때까지 대기
            await page.wait_for_timeout(3000)

            # 페이지 제목 확인
            page_title = await page.title()
            self.logger.info(f"Page title: {page_title}")

            # Course ID 추출
            course_id = response.url.split('/classroom/')[-1].split('?')[0]

            # 강의 제목 추출
            course_title = None
            if ' - ' in page_title:
                course_title = page_title.split(' - ', 1)[1].strip()
            elif '|' in page_title:
                course_title = page_title.split('|')[0].strip()

            if not course_title or len(course_title) < 10:
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
            curriculum = await self.extract_curriculum_playwright(page)

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

            # 이전 스크린샷 저장 코드는 유지
            await page.wait_for_timeout(2000)

            # 전체 페이지 스크린샷
            await page.screenshot(path='test_full_page.png', full_page=True)
            self.logger.info("✓ Saved: test_full_page.png (full page)")

            # 뷰포트 스크린샷
            await page.screenshot(path='test_viewport.png')
            self.logger.info("✓ Saved: test_viewport.png (viewport)")

            # 오른쪽 사이드바/커리큘럼 영역 찾기
            self.logger.info("\n" + "=" * 80)
            self.logger.info("Finding curriculum sidebar...")
            self.logger.info("=" * 80)

            # 가능한 선택자들
            possible_selectors = [
                'aside',
                '[class*="curriculum"]',
                '[class*="Curriculum"]',
                '[class*="sidebar"]',
                '[class*="Sidebar"]',
                '[class*="lecture"]',
                '[class*="Lecture"]',
                '[class*="playlist"]',
                '[class*="Playlist"]',
                'nav[class*="side"]',
                'div[class*="side"]',
            ]

            found_elements = []

            for selector in possible_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        self.logger.info(f"✓ Found {len(elements)} elements with selector: {selector}")
                        found_elements.append({
                            'selector': selector,
                            'count': len(elements),
                            'elements': elements
                        })
                except Exception as e:
                    pass

            # 가장 많은 요소를 찾은 선택자 사용
            if found_elements:
                found_elements.sort(key=lambda x: x['count'], reverse=True)
                best_match = found_elements[0]

                self.logger.info(f"\n✓ Best match: {best_match['selector']} ({best_match['count']} elements)")

                # 첫 번째 요소의 HTML 저장
                first_elem = best_match['elements'][0]
                html_content = await first_elem.inner_html()

                with open('test_curriculum_html.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.logger.info("✓ Saved: test_curriculum_html.html")

                # 텍스트 내용 저장
                text_content = await first_elem.inner_text()
                with open('test_curriculum_text.txt', 'w', encoding='utf-8') as f:
                    f.write(text_content)
                self.logger.info("✓ Saved: test_curriculum_text.txt")

                # 처음 2000자만 로그 출력
                self.logger.info(f"\n{'=' * 80}")
                self.logger.info("Curriculum text preview (first 2000 chars):")
                self.logger.info(f"{'=' * 80}")
                self.logger.info(text_content[:2000])
                self.logger.info(f"\n... (see test_curriculum_text.txt for full content)")

                # 스크린샷 찍기
                try:
                    await first_elem.screenshot(path='test_curriculum_element.png')
                    self.logger.info("✓ Saved: test_curriculum_element.png")
                except Exception as e:
                    self.logger.warning(f"Could not screenshot element: {e}")

            else:
                self.logger.warning("✗ No curriculum elements found with any selector")

            # 페이지 전체 텍스트도 저장
            full_text = await page.inner_text('body')
            with open('test_full_page_text.txt', 'w', encoding='utf-8') as f:
                f.write(full_text)
            self.logger.info("✓ Saved: test_full_page_text.txt")

            # 페이지 HTML도 저장
            full_html = await page.content()
            with open('test_full_page_html.html', 'w', encoding='utf-8') as f:
                f.write(full_html)
            self.logger.info("✓ Saved: test_full_page_html.html")

            self.logger.info(f"\n{'=' * 80}")
            self.logger.info("Test complete! Check the saved files:")
            self.logger.info("  - test_full_page.png (full page screenshot)")
            self.logger.info("  - test_viewport.png (viewport screenshot)")
            self.logger.info("  - test_curriculum_html.html (curriculum HTML)")
            self.logger.info("  - test_curriculum_text.txt (curriculum text)")
            self.logger.info("  - test_curriculum_element.png (curriculum element screenshot)")
            self.logger.info("  - test_full_page_text.txt (full page text)")
            self.logger.info("  - test_full_page_html.html (full page HTML)")
            self.logger.info(f"{'=' * 80}\n")

        except Exception as e:
            self.logger.error(f"Error in test: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

        finally:
            if page:
                await page.close()

    async def extract_curriculum_playwright(self, page):
        """Playwright를 사용하여 커리큘럼 추출"""
        curriculum = []

        try:
            # 커리큘럼 영역이 로드될 때까지 대기
            await page.wait_for_selector('.classroom-sidebar-clip__chapter', timeout=10000)
            await page.wait_for_timeout(2000)  # 추가 대기

            # 각 섹션(챕터) 찾기
            chapter_elements = await page.query_selector_all('.classroom-sidebar-clip__chapter')
            self.logger.info(f"Found {len(chapter_elements)} chapters")

            if len(chapter_elements) == 0:
                self.logger.warning("No chapters found! Aborting curriculum extraction.")
                return curriculum

            # STEP 1: 모든 Chapter(큰 섹션) 열기
            self.logger.info("STEP 1: Opening all chapters (main sections)...")

            opened_chapters = 0
            for idx, chapter in enumerate(chapter_elements, 1):
                try:
                    # 아코디언 메뉴 찾기
                    menu = await chapter.query_selector('.common-accordion-menu')
                    if not menu:
                        continue

                    # 현재 상태 확인
                    class_attr = await menu.get_attribute('class')
                    is_open = 'common-accordion-menu--open' in class_attr if class_attr else False

                    if not is_open:
                        # 헤더 찾기
                        header = await chapter.query_selector('.common-accordion-menu__header')
                        if header:
                            self.logger.info(f"  Opening chapter {idx}/{len(chapter_elements)}...")

                            # 화면에 보이도록 스크롤
                            await header.scroll_into_view_if_needed()
                            await page.wait_for_timeout(500)

                            # 클릭
                            await header.click()
                            await page.wait_for_timeout(1500)  # 충분히 대기

                            # 열렸는지 다시 확인
                            class_attr_after = await menu.get_attribute('class')
                            if 'common-accordion-menu--open' in class_attr_after:
                                opened_chapters += 1
                                self.logger.info(f"    ✓ Chapter {idx} opened")
                            else:
                                self.logger.warning(f"    ✗ Chapter {idx} failed, retrying...")
                                await page.wait_for_timeout(500)
                                await header.click()
                                await page.wait_for_timeout(1500)
                    else:
                        self.logger.info(f"  Chapter {idx} already open")
                        opened_chapters += 1

                except Exception as e:
                    self.logger.warning(f"  Error opening chapter {idx}: {e}")
                    continue

            self.logger.info(f"✓ Opened {opened_chapters}/{len(chapter_elements)} chapters")
            await page.wait_for_timeout(3000)

            # STEP 2: 각 Chapter 안의 모든 sub-section 아코디언도 열기
            self.logger.info("STEP 2: Opening all sub-sections within chapters...")

            # 페이지 내 모든 아코디언 메뉴 찾기 (chapter 내부 포함)
            all_accordion_menus = await page.query_selector_all('.common-accordion-menu')
            self.logger.info(f"Found {len(all_accordion_menus)} total accordion menus")

            opened_subsections = 0
            for idx, menu in enumerate(all_accordion_menus, 1):
                try:
                    # 현재 상태 확인
                    class_attr = await menu.get_attribute('class')
                    is_open = 'common-accordion-menu--open' in class_attr if class_attr else False

                    if not is_open:
                        # 헤더 찾기
                        header = await menu.query_selector('.common-accordion-menu__header')
                        if header:
                            # 화면에 보이도록 스크롤
                            await header.scroll_into_view_if_needed()
                            await page.wait_for_timeout(300)

                            # 클릭
                            await header.click()
                            await page.wait_for_timeout(1000)

                            # 열렸는지 확인
                            class_attr_after = await menu.get_attribute('class')
                            if 'common-accordion-menu--open' in class_attr_after:
                                opened_subsections += 1

                except Exception as e:
                    continue

            self.logger.info(f"✓ Opened {opened_subsections} additional sub-sections")

            # 모든 섹션이 열린 후 충분히 대기
            await page.wait_for_timeout(5000)

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
