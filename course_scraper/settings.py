# Scrapy settings for course_scraper project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "course_scraper"

SPIDER_MODULES = ["course_scraper.spiders"]
NEWSPIDER_MODULE = "course_scraper.spiders"


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = "course_scraper (+http://www.yourdomain.com)"

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure maximum concurrent requests performed by Scrapy (default: 16)
#CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
#DOWNLOAD_DELAY = 3
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    "course_scraper.middlewares.CourseScraperSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#DOWNLOADER_MIDDLEWARES = {
#    "course_scraper.middlewares.CourseScraperDownloaderMiddleware": 543,
#}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "course_scraper.pipelines.MySQLPipeline": 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
#AUTOTHROTTLE_ENABLED = True
# The initial download delay
#AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
#AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# MySQL Database Settings
# credentials.py에서 로그인 정보 가져오기
import sys
import os

# credentials.py 직접 로드
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
_credentials_path = os.path.join(_project_root, 'credentials.py')

# 기본값
MYSQL_HOST = 'localhost'
MYSQL_PORT = 3306
MYSQL_USER = 'root'
MYSQL_PASSWORD = ''
MYSQL_DATABASE = 'crawler'
KAKAO_EMAIL = ''
KAKAO_PASSWORD = ''

if os.path.exists(_credentials_path):
    with open(_credentials_path, 'r', encoding='utf-8') as f:
        _exec_globals = {}
        exec(f.read(), _exec_globals)
        MYSQL_HOST = _exec_globals.get('MYSQL_HOST', MYSQL_HOST)
        MYSQL_PORT = _exec_globals.get('MYSQL_PORT', MYSQL_PORT)
        MYSQL_USER = _exec_globals.get('MYSQL_USER', MYSQL_USER)
        MYSQL_PASSWORD = _exec_globals.get('MYSQL_PASSWORD', MYSQL_PASSWORD)
        MYSQL_DATABASE = _exec_globals.get('MYSQL_DATABASE', MYSQL_DATABASE)
        KAKAO_EMAIL = _exec_globals.get('KAKAO_EMAIL', KAKAO_EMAIL)
        KAKAO_PASSWORD = _exec_globals.get('KAKAO_PASSWORD', KAKAO_PASSWORD)
else:
    print("WARNING: credentials.py not found. Please create it from credentials_example.py")

# Playwright Settings
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": False,  # 2단계 인증을 위해 브라우저 표시
    "timeout": 120000,  # 브라우저 시작 타임아웃 2분
}

# 브라우저 컨텍스트 설정 - 로그인 세션 유지
PLAYWRIGHT_CONTEXTS = {
    "default": {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
}

PLAYWRIGHT_MAX_CONTEXTS = 1  # 모든 요청이 동일한 컨텍스트 사용
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60000  # 페이지 네비게이션 타임아웃 60초

# Playwright 동시 실행 제한
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# 다운로드 타임아웃 설정
DOWNLOAD_TIMEOUT = 60  # 60초
