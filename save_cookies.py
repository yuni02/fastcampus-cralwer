#!/usr/bin/env python
"""
FastCampus 로그인 후 쿠키를 저장하는 스크립트
한 번만 실행하면 됩니다.
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def save_cookies():
    """수동 로그인 후 쿠키 저장"""
    async with async_playwright() as p:
        # 브라우저 실행 (화면에 표시)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        print("브라우저가 열렸습니다.")
        print("FastCampus 로그인 페이지로 이동합니다...")

        # 로그인 페이지로 이동
        await page.goto('https://fastcampus.co.kr/account/sign-in')

        print("\n" + "="*60)
        print("브라우저에서 수동으로 로그인을 완료해주세요:")
        print("1. 카카오로 로그인")
        print("2. 2단계 인증 완료")
        print("3. FastCampus 메인 페이지로 이동될 때까지 대기")
        print("="*60 + "\n")

        # 로그인 완료될 때까지 대기 (fastcampus.co.kr로 리다이렉트)
        try:
            print("로그인 완료를 기다리는 중... (최대 5분)")
            await page.wait_for_url('https://fastcampus.co.kr/**', timeout=300000)
            print("✓ 로그인 성공!")
        except Exception as e:
            print(f"✗ 타임아웃: {e}")
            print("로그인을 완료하고 Enter를 눌러주세요...")
            input()

        # 추가 대기
        await page.wait_for_timeout(3000)

        # 현재 URL 확인
        current_url = page.url
        print(f"현재 URL: {current_url}")

        # 쿠키 저장
        cookies = await context.cookies()

        # 쿠키를 JSON 파일로 저장
        with open('cookies.json', 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"\n✓ 쿠키 저장 완료: cookies.json")
        print(f"✓ 총 {len(cookies)}개의 쿠키가 저장되었습니다.")

        # 브라우저 닫기
        await browser.close()
        print("\n쿠키 저장이 완료되었습니다!")
        print("이제 Scrapy 스파이더를 실행할 수 있습니다.")


if __name__ == '__main__':
    asyncio.run(save_cookies())
