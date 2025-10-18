# FastCampus Course Scraper

패스트캠퍼스, 인프런, Udemy 등의 강의 플랫폼에서 내가 구매한 강의 정보를 크롤링하여 MySQL 데이터베이스에 저장하는 Scrapy 프로젝트입니다.
이를 통해 효율적으로 내가 구매한 강의의 총 남은 수강시간, 공부한 시간을 쉽게 파악하여 완강을 계획적으로 할 수 있습니다.

## 주요 기능

- 🔐 카카오 로그인을 통한 패스트캠퍼스 강의 정보 수집
- 🎯 강의 커리큘럼 자동 추출
- 💾 MySQL 데이터베이스 자동 저장
- 🎭 Playwright를 사용한 동적 페이지 크롤링
- 📊 크롤링 로그 자동 기록

## 기술 스택

- Python 3.9+
- Scrapy 2.13.3
- Scrapy-Playwright
- PyMySQL
- Playwright Chromium

## 설치 방법

### 1. 저장소 클론

```bash
git clone <repository-url>
cd fastcampus-scrapping
```

### 2. 가상환경 생성 및 활성화

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. 로그인 정보 설정

`credentials_example.py`를 `credentials.py`로 복사하고 실제 정보 입력:

```bash
cp credentials_example.py credentials.py
```

`credentials.py` 파일을 열어 다음 정보 입력:

```python
# 카카오 로그인 정보
KAKAO_EMAIL = 'your_email@kakao.com'
KAKAO_PASSWORD = 'your_password'

# MySQL 데이터베이스 정보
MYSQL_HOST = 'db ip주소'
MYSQL_PORT = 'db port번호'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'your_db_password'
MYSQL_DATABASE = '저장할 db schema명'
```

### 5. MySQL 데이터베이스 설정

제공된 SQL 스키마로 데이터베이스 테이블 생성:

```sql
CREATE DATABASE crawler;
USE crawler;

-- courses, lectures, crawl_logs 테이블 생성
-- (SQL 스키마는 별도 문서 참조)
```

## 사용 방법

### 기본 실행 방법

```bash
# 1. 가상환경 활성화
source .venv/bin/activate

# 2. course_scraper 디렉토리로 이동
cd course_scraper

# 3. 크롤링 실행
scrapy crawl fastcampus_daily
```

### Spider 종류별 사용 방법

#### 1. `fastcampus_discover` (월 1회 실행)
새로운 강의 URL 발견 및 DB 저장
```bash
scrapy crawl fastcampus_discover
```

#### 2. `fastcampus_daily` (매일 실행, 추천)
DB에 있는 강의들의 진도율/커리큘럼 업데이트
```bash
# 기본 실행 (모든 강의 크롤링)
scrapy crawl fastcampus_daily

# 목표 강의만 크롤링 (is_target_course = 1인 강의만)
scrapy crawl fastcampus_daily -a target_only=true

# 최근 24시간 내 업데이트된 강의 제외
scrapy crawl fastcampus_daily -a skip_recent=true

# 특정 강의 ID만 크롤링
scrapy crawl fastcampus_daily -a course_id=214390

# 옵션 조합 (목표 강의 + 최근 업데이트 제외)
scrapy crawl fastcampus_daily -a target_only=true -a skip_recent=true
```

#### 3. `fastcampus` (전체 크롤링)
강의 목록 수집 + 각 강의 크롤링 (시간 오래 걸림)
```bash
scrapy crawl fastcampus
```

#### 4. `fastcampus_test` (테스트용)
특정 강의 하나만 테스트
```bash
scrapy crawl fastcampus_test
```

### 추천 실행 순서 (처음이라면)

```bash
# 1단계: 먼저 강의 목록 수집 (처음 1회만)
scrapy crawl fastcampus_discover

# 2단계: 매일 진도 업데이트
scrapy crawl fastcampus_daily
```

### 기타 유용한 옵션

```bash
# 결과를 JSON으로 저장
scrapy crawl fastcampus_daily -o output.json

# 로그 레벨 조정
scrapy crawl fastcampus_daily -L INFO
scrapy crawl fastcampus_daily -L ERROR
```

### fastcampus_daily 필터링 옵션 상세 설명

`fastcampus_daily` spider는 효율적인 크롤링을 위해 다음 필터링 옵션을 제공합니다:

#### 1. `target_only=true`
**용도**: 집중적으로 수강하는 강의만 업데이트

**사용 시나리오**:
- 구매한 강의가 많지만, 현재 집중적으로 듣는 강의만 매일 업데이트하고 싶을 때
- DB의 `courses` 테이블에서 `is_target_course = 1`로 설정된 강의만 크롤링

**SQL로 목표 강의 설정**:
```sql
-- 특정 강의를 목표 강의로 설정
UPDATE courses SET is_target_course = 1 WHERE course_id = 214390;

-- 여러 강의를 목표 강의로 설정
UPDATE courses SET is_target_course = 1 WHERE course_id IN (214390, 123456, 789012);

-- 목표 강의 해제
UPDATE courses SET is_target_course = 0 WHERE course_id = 214390;
```

#### 2. `skip_recent=true`
**용도**: 불필요한 중복 크롤링 방지

**사용 시나리오**:
- 하루에 여러 번 크롤링을 실행하지만, 이미 최근에 업데이트된 강의는 건너뛰고 싶을 때
- 24시간 이내 업데이트된 강의는 자동으로 제외됨

**실행 예시**:
```bash
# 아침에 실행 (모든 강의 크롤링)
scrapy crawl fastcampus_daily

# 저녁에 실행 (아침에 업데이트한 강의는 건너뜀)
scrapy crawl fastcampus_daily -a skip_recent=true
```

#### 3. `course_id=강의ID`
**용도**: 특정 강의 하나만 업데이트

**사용 시나리오**:
- 방금 강의를 들었는데, 해당 강의의 진도만 빠르게 업데이트하고 싶을 때
- 특정 강의에 문제가 있어서 재크롤링이 필요할 때

**실행 예시**:
```bash
# course_id가 214390인 강의만 크롤링
scrapy crawl fastcampus_daily -a course_id=214390
```

**강의 ID 확인 방법**:
```sql
-- DB에서 강의 ID 조회
SELECT course_id, course_title, url FROM courses;

-- 또는 강의 URL에서 확인
-- 예: https://fastcampus.co.kr/classroom/214390
-- course_id = 214390
```

#### 옵션 조합 활용 예시

```bash
# 사용 예시 1: 목표 강의만 매일 업데이트 (추천)
scrapy crawl fastcampus_daily -a target_only=true

# 사용 예시 2: 목표 강의 + 최근 업데이트 제외 (하루 여러 번 실행 시)
scrapy crawl fastcampus_daily -a target_only=true -a skip_recent=true

# 사용 예시 3: 특정 강의만 빠르게 업데이트
scrapy crawl fastcampus_daily -a course_id=214390

# 사용 예시 4: 모든 강의 전체 업데이트 (주말에 1회)
scrapy crawl fastcampus_daily
```

## 프로젝트 구조

```
fastcampus-scrapping/
├── course_scraper/              # Scrapy 프로젝트
│   ├── scrapy.cfg              # Scrapy 설정 파일
│   └── course_scraper/
│       ├── __init__.py
│       ├── settings.py         # 프로젝트 설정
│       ├── items.py            # 데이터 모델
│       ├── pipelines.py        # MySQL 파이프라인
│       ├── middlewares.py      # 미들웨어
│       └── spiders/            # 스파이더
│           ├── fastcampus_spider.py
│           ├── inflearn_spider.py
│           └── udemy_spider.py
├── credentials.py              # 로그인 정보 (git에 업로드 안됨)
├── credentials_example.py      # 로그인 정보 템플릿
├── .gitignore
├── requirements.txt
└── README.md
```

## 데이터베이스 스키마

### courses 테이블
- 강의 기본 정보 저장
- course_id (PK), course_title, progress_rate, url 등

### lectures 테이블
- 강의 목차/커리큘럼 저장
- lecture_id (PK), course_id (FK), section_title, lecture_title 등

### crawl_logs 테이블
- 크롤링 로그 저장
- log_id (PK), course_id, crawl_status, error_message 등

## 주의사항

⚠️ **보안 경고**
- `credentials.py` 파일은 절대 Git에 커밋하지 마세요
- `.gitignore`에 `credentials.py`가 포함되어 있는지 확인하세요

⚠️ **크롤링 윤리**
- robots.txt를 준수하세요
- DOWNLOAD_DELAY를 적절히 설정하여 서버에 부하를 주지 않도록 하세요
- 수집한 데이터는 개인 학습 목적으로만 사용하세요

## 깃헙에 올리기

### 전체 프로젝트 올리기 (권장)

```bash
cd /Users/jennie/PycharmProjects/fastcampus-scrapping
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### course_scraper 폴더만 올리기

```bash
cd /Users/jennie/PycharmProjects/fastcampus-scrapping/course_scraper
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

**권장사항**: 전체 프로젝트를 올리는 것을 추천합니다. 이렇게 하면:
- README.md, .gitignore, requirements.txt 등이 함께 포함됨
- credentials_example.py를 통해 다른 사용자가 쉽게 설정 가능
- 프로젝트 전체 구조를 한눈에 파악 가능

## 라이선스

MIT License

## 문의

이슈나 질문이 있으시면 GitHub Issues를 이용해주세요.
