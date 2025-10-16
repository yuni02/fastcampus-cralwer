-- 매일 새로 완료한 강의 조회 쿼리 모음

-- 1. 오늘 완료한 강의 목록
SELECT
    c.course_title AS '강의명',
    l.section_title AS '섹션',
    l.lecture_title AS '강의',
    l.lecture_time AS '강의시간(분)',
    l.completed_at AS '완료시각'
FROM lectures l
JOIN courses c ON l.course_id = c.course_id
WHERE DATE(l.completed_at) = CURDATE()
ORDER BY l.completed_at DESC;


-- 2. 오늘 완료한 강의 통계
SELECT
    COUNT(*) AS '완료한_강의수',
    SUM(l.lecture_time) AS '총_학습시간(분)',
    ROUND(SUM(l.lecture_time) / 60, 2) AS '총_학습시간(시간)'
FROM lectures l
WHERE DATE(l.completed_at) = CURDATE();


-- 3. 오늘 강의별 완료 현황
SELECT
    c.course_title AS '강의명',
    COUNT(*) AS '오늘_완료한_강의수',
    SUM(l.lecture_time) AS '학습시간(분)',
    ROUND(SUM(l.lecture_time) / 60, 2) AS '학습시간(시간)'
FROM lectures l
JOIN courses c ON l.course_id = c.course_id
WHERE DATE(l.completed_at) = CURDATE()
GROUP BY c.course_id, c.course_title
ORDER BY COUNT(*) DESC;


-- 4. 최근 7일간 완료한 강의 목록
SELECT
    DATE(l.completed_at) AS '날짜',
    c.course_title AS '강의명',
    l.section_title AS '섹션',
    l.lecture_title AS '강의',
    l.lecture_time AS '강의시간(분)'
FROM lectures l
JOIN courses c ON l.course_id = c.course_id
WHERE l.completed_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
ORDER BY l.completed_at DESC;


-- 5. 최근 7일간 일별 학습 통계
SELECT
    DATE(l.completed_at) AS '날짜',
    DAYNAME(l.completed_at) AS '요일',
    COUNT(*) AS '완료_강의수',
    SUM(l.lecture_time) AS '학습시간(분)',
    ROUND(SUM(l.lecture_time) / 60, 2) AS '학습시간(시간)'
FROM lectures l
WHERE l.completed_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
GROUP BY DATE(l.completed_at), DAYNAME(l.completed_at)
ORDER BY DATE(l.completed_at) DESC;


-- 6. 특정 날짜에 완료한 강의 목록 (날짜 직접 입력)
SELECT
    c.course_title AS '강의명',
    l.section_title AS '섹션',
    l.lecture_title AS '강의',
    l.lecture_time AS '강의시간(분)',
    TIME(l.completed_at) AS '완료시각'
FROM lectures l
JOIN courses c ON l.course_id = c.course_id
WHERE DATE(l.completed_at) = '2025-10-16'  -- 원하는 날짜로 변경
ORDER BY l.completed_at;


-- 7. 이번 달 완료한 강의 통계
SELECT
    COUNT(*) AS '완료_강의수',
    SUM(l.lecture_time) AS '총_학습시간(분)',
    ROUND(SUM(l.lecture_time) / 60, 2) AS '총_학습시간(시간)',
    ROUND(COUNT(*) / DAY(LAST_DAY(CURDATE())), 1) AS '하루평균_강의수'
FROM lectures l
WHERE YEAR(l.completed_at) = YEAR(CURDATE())
  AND MONTH(l.completed_at) = MONTH(CURDATE());


-- 8. 강의별 최근 완료한 강의 (강의당 최대 5개)
SELECT
    c.course_title AS '강의명',
    l.section_title AS '섹션',
    l.lecture_title AS '강의',
    DATE(l.completed_at) AS '완료일',
    l.lecture_time AS '강의시간(분)'
FROM lectures l
JOIN courses c ON l.course_id = c.course_id
WHERE l.is_completed = TRUE
  AND l.completed_at IS NOT NULL
ORDER BY c.course_id, l.completed_at DESC
LIMIT 50;


-- 9. 오늘과 어제 비교
SELECT
    '오늘' AS '구분',
    COUNT(*) AS '완료_강의수',
    ROUND(SUM(l.lecture_time) / 60, 2) AS '학습시간(시간)'
FROM lectures l
WHERE DATE(l.completed_at) = CURDATE()

UNION ALL

SELECT
    '어제' AS '구분',
    COUNT(*) AS '완료_강의수',
    ROUND(SUM(l.lecture_time) / 60, 2) AS '학습시간(시간)'
FROM lectures l
WHERE DATE(l.completed_at) = DATE_SUB(CURDATE(), INTERVAL 1 DAY);


-- 10. 주간 학습 패턴 분석 (요일별)
SELECT
    DAYNAME(l.completed_at) AS '요일',
    COUNT(*) AS '평균_완료_강의수',
    ROUND(AVG(l.lecture_time), 2) AS '평균_강의시간(분)'
FROM lectures l
WHERE l.completed_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DAYOFWEEK(l.completed_at), DAYNAME(l.completed_at)
ORDER BY DAYOFWEEK(l.completed_at);
