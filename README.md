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

### 패스트캠퍼스 강의 크롤링

```bash
cd course_scraper
scrapy crawl fastcampus
```

### 인프런 강의 크롤링

```bash
scrapy crawl inflearn
```

### Udemy 강의 크롤링

```bash
scrapy crawl udemy
```

### 결과를 JSON으로 저장

```bash
scrapy crawl fastcampus -o output.json
```

### 로그 레벨 조정

```bash
scrapy crawl fastcampus -L INFO
scrapy crawl fastcampus -L ERROR
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
