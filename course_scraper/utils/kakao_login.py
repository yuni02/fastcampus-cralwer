"""
Kakao login helper for FastCampus spiders
"""
import logging
from typing import Optional, Callable, Any

from .credentials import get_kakao_credentials
from .paths import get_screenshot_path

logger = logging.getLogger(__name__)


class KakaoLoginHelper:
    """Helper class for Kakao login automation with Playwright"""

    # Selectors for Kakao login
    KAKAO_BUTTON_SELECTORS = [
        'button:has-text("카카오로 1초 만에 시작하기")',
        'button:has-text("카카오")',
        'a:has-text("카카오로 1초 만에 시작하기")',
        '[class*="kakao"]',
    ]

    EMAIL_SELECTORS = [
        'input[name="loginId"]',
        'input[type="email"]',
        '#loginId',
    ]

    PASSWORD_SELECTORS = [
        'input[name="password"]',
        'input[type="password"]',
        '#password',
    ]

    LOGIN_BUTTON_SELECTORS = [
        'button[type="submit"]',
        'button:has-text("로그인")',
        '.btn_confirm',
    ]

    CONTINUE_BUTTON_SELECTORS = [
        'button.btn_confirm',
        'button:has-text("Continue")',
        'button:has-text("확인")',
    ]

    def __init__(self, logger_instance=None):
        """
        Initialize the login helper

        Args:
            logger_instance: Optional logger to use (default: module logger)
        """
        self.log = logger_instance or logger
        self.email, self.password = get_kakao_credentials()

    async def click_kakao_button(self, page) -> bool:
        """Click the Kakao login button on FastCampus"""
        self.log.info("Looking for Kakao login button...")

        for selector in self.KAKAO_BUTTON_SELECTORS:
            try:
                await page.click(selector, timeout=5000)
                self.log.info("Clicked Kakao button")
                return True
            except Exception:
                continue

        self.log.error("Could not find Kakao login button")
        return False

    async def enter_credentials(self, page) -> bool:
        """Enter email and password on Kakao login page"""
        # Enter email
        email_entered = False
        for selector in self.EMAIL_SELECTORS:
            try:
                await page.fill(selector, self.email, timeout=3000)
                self.log.info("Entered email")
                email_entered = True
                break
            except Exception:
                continue

        if not email_entered:
            self.log.error("Could not enter email")
            return False

        # Enter password
        password_entered = False
        for selector in self.PASSWORD_SELECTORS:
            try:
                await page.fill(selector, self.password, timeout=3000)
                self.log.info("Entered password")
                password_entered = True
                break
            except Exception:
                continue

        if not password_entered:
            self.log.error("Could not enter password")
            return False

        return True

    async def click_login_button(self, page) -> bool:
        """Click the login button on Kakao page"""
        for selector in self.LOGIN_BUTTON_SELECTORS:
            try:
                await page.click(selector, timeout=3000)
                self.log.info("Clicked login button")
                return True
            except Exception:
                continue

        self.log.error("Could not click login button")
        return False

    async def wait_for_2fa(self, page, max_wait_time: int = 90) -> bool:
        """
        Wait for 2FA approval and handle redirect

        Args:
            page: Playwright page
            max_wait_time: Maximum seconds to wait for 2FA

        Returns:
            True if successfully logged in, False otherwise
        """
        self.log.info("=" * 70)
        self.log.info("KakaoTalk 앱에서 2단계 인증을 승인해주세요!")
        self.log.info(f"{max_wait_time}초 대기 중...")
        self.log.info("=" * 70)

        check_interval = 2

        for i in range(0, max_wait_time, check_interval):
            await page.wait_for_timeout(check_interval * 1000)

            # Try to click Continue button if visible
            for selector in self.CONTINUE_BUTTON_SELECTORS:
                try:
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        self.log.info("Clicked Continue button!")
                        await page.wait_for_timeout(3000)
                        break
                except Exception:
                    continue

            # Check if redirected to FastCampus
            current_url = page.url
            if 'fastcampus.co.kr' in current_url and 'sign-in' not in current_url:
                self.log.info("Successfully redirected to FastCampus!")
                return True

        return False

    def is_login_successful(self, url: str, page_title: str) -> bool:
        """Check if login was successful based on URL and page title"""
        return 'sign-in' not in url and '인증' not in page_title

    async def login(self, page, take_screenshots: bool = False) -> bool:
        """
        Perform full Kakao login flow

        Args:
            page: Playwright page (should be on FastCampus sign-in page)
            take_screenshots: Whether to save screenshots for debugging

        Returns:
            True if login successful, False otherwise
        """
        try:
            self.log.info("Starting Kakao login process...")

            if take_screenshots:
                await page.screenshot(path=get_screenshot_path('login_1_initial'))

            # Step 1: Click Kakao button
            if not await self.click_kakao_button(page):
                await page.close()
                return False

            # Wait for Kakao page to load
            await page.wait_for_timeout(3000)

            # Step 2: Enter credentials
            if not await self.enter_credentials(page):
                await page.close()
                return False

            await page.wait_for_timeout(1000)

            # Step 3: Click login button
            if not await self.click_login_button(page):
                await page.close()
                return False

            # Step 4: Wait for 2FA
            await page.wait_for_timeout(3000)

            if take_screenshots:
                await page.screenshot(path=get_screenshot_path('login_4_after_click'))

            await self.wait_for_2fa(page)

            # Check login result
            current_url = page.url
            page_title = await page.title()

            if self.is_login_successful(current_url, page_title):
                self.log.info("Login successful!")
                return True
            else:
                self.log.error("Login failed!")
                return False

        except Exception as e:
            self.log.error(f"Login failed: {e}")
            import traceback
            self.log.error(traceback.format_exc())
            return False
