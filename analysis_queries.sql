-- FastCampus 학습 진도 분석 쿼리 모음
-- 주간 스냅샷 데이터를 활용한 학습 패턴 분석

-- ============================================
-- 1. 이번 주 학습 현황
-- ============================================
SELECT
    c.course_title AS '강의명',
    curr.progress_rate AS '현재진도(%)',
    curr.study_time AS '현재학습시간(분)',
    CONCAT(FLOOR(curr.study_time / 60), '시간 ',
           FLOOR(curr.study_time % 60), '분') AS '현재학습',
    curr.snapshot_date AS '스냅샷날짜'
FROM course_progress_snapshots curr
JOIN courses c ON curr.course_id = c.course_id
WHERE curr.snapshot_date = (
    SELECT MAX(snapshot_date) FROM course_progress_snapshots
)
ORDER BY curr.study_time DESC;


-- ============================================
-- 2. 이번 주 학습량 (지난주 대비)
-- ============================================
SELECT
    c.course_title AS '강의명',
    curr.study_time - IFNULL(prev.study_time, 0) AS '이번주학습(분)',
    CONCAT(
        FLOOR((curr.study_time - IFNULL(prev.study_time, 0)) / 60), '시간 ',
        FLOOR((curr.study_time - IFNULL(prev.study_time, 0)) % 60), '분'
    ) AS '이번주학습시간',
    curr.progress_rate - IFNULL(prev.progress_rate, 0) AS '진도증가(%)',
    curr.progress_rate AS '현재진도(%)',
    curr.total_lecture_time - curr.study_time AS '남은시간(분)'
FROM course_progress_snapshots curr
LEFT JOIN course_progress_snapshots prev
    ON curr.course_id = prev.course_id
    AND prev.snapshot_date = DATE_SUB(curr.snapshot_date, INTERVAL 7 DAY)
JOIN courses c ON curr.course_id = c.course_id
WHERE curr.snapshot_date = (
    SELECT MAX(snapshot_date) FROM course_progress_snapshots
)
    AND curr.study_time - IFNULL(prev.study_time, 0) > 0
ORDER BY curr.study_time - IFNULL(prev.study_time, 0) DESC;


-- ============================================
-- 3. 최근 4주간 전체 학습 추이
-- ============================================
SELECT
    snapshot_date AS '주차',
    COUNT(DISTINCT course_id) AS '학습강의수',
    SUM(study_time) AS '누적학습시간(분)',
    CONCAT(
        FLOOR(SUM(study_time) / 1440), '일 ',
        FLOOR((SUM(study_time) % 1440) / 60), '시간'
    ) AS '누적학습',
    ROUND(AVG(progress_rate), 2) AS '평균진도(%)'
FROM course_progress_snapshots
WHERE snapshot_date >= DATE_SUB(CURDATE(), INTERVAL 4 WEEK)
GROUP BY snapshot_date
ORDER BY snapshot_date DESC;


-- ============================================
-- 4. 최근 4주간 주간 학습량 변화
-- ============================================
WITH weekly_changes AS (
    SELECT
        curr.snapshot_date,
        curr.course_id,
        curr.study_time - IFNULL(prev.study_time, 0) AS weekly_study
    FROM course_progress_snapshots curr
    LEFT JOIN course_progress_snapshots prev
        ON curr.course_id = prev.course_id
        AND prev.snapshot_date = DATE_SUB(curr.snapshot_date, INTERVAL 7 DAY)
    WHERE curr.snapshot_date >= DATE_SUB(CURDATE(), INTERVAL 4 WEEK)
)
SELECT
    snapshot_date AS '주차',
    COUNT(CASE WHEN weekly_study > 0 THEN 1 END) AS '학습한강의수',
    SUM(weekly_study) AS '주간학습량(분)',
    CONCAT(
        FLOOR(SUM(weekly_study) / 60), '시간 ',
        FLOOR(SUM(weekly_study) % 60), '분'
    ) AS '주간학습시간',
    ROUND(AVG(CASE WHEN weekly_study > 0 THEN weekly_study END), 2) AS '평균학습량(분)'
FROM weekly_changes
GROUP BY snapshot_date
ORDER BY snapshot_date DESC;


-- ============================================
-- 5. 강의별 학습 패턴 (전체 기간)
-- ============================================
WITH study_stats AS (
    SELECT
        curr.course_id,
        curr.snapshot_date,
        curr.study_time - IFNULL(prev.study_time, 0) AS weekly_study
    FROM course_progress_snapshots curr
    LEFT JOIN course_progress_snapshots prev
        ON curr.course_id = prev.course_id
        AND prev.snapshot_date = DATE_SUB(curr.snapshot_date, INTERVAL 7 DAY)
)
SELECT
    c.course_title AS '강의명',
    COUNT(*) AS '기록주차',
    ROUND(AVG(CASE WHEN ss.weekly_study > 0 THEN ss.weekly_study END), 2) AS '주평균학습(분)',
    MAX(ss.weekly_study) AS '최대주간학습(분)',
    c.progress_rate AS '현재진도(%)',
    c.total_lecture_time - c.study_time AS '남은시간(분)',
    CONCAT(
        FLOOR((c.total_lecture_time - c.study_time) / 60), '시간 ',
        FLOOR((c.total_lecture_time - c.study_time) % 60), '분'
    ) AS '남은학습시간'
FROM study_stats ss
JOIN courses c ON ss.course_id = c.course_id
GROUP BY ss.course_id, c.course_title, c.progress_rate, c.total_lecture_time, c.study_time
HAVING COUNT(*) >= 2
ORDER BY AVG(CASE WHEN ss.weekly_study > 0 THEN ss.weekly_study END) DESC;


-- ============================================
-- 6. 학습 목표 대비 달성률 (주 3시간 목표 기준)
-- ============================================
WITH weekly_study AS (
    SELECT
        curr.snapshot_date,
        curr.course_id,
        c.course_title,
        curr.study_time - IFNULL(prev.study_time, 0) AS weekly_minutes
    FROM course_progress_snapshots curr
    LEFT JOIN course_progress_snapshots prev
        ON curr.course_id = prev.course_id
        AND prev.snapshot_date = DATE_SUB(curr.snapshot_date, INTERVAL 7 DAY)
    JOIN courses c ON curr.course_id = c.course_id
    WHERE curr.snapshot_date = (
        SELECT MAX(snapshot_date) FROM course_progress_snapshots
    )
)
SELECT
    snapshot_date AS '주차',
    SUM(weekly_minutes) AS '총학습시간(분)',
    CONCAT(
        FLOOR(SUM(weekly_minutes) / 60), '시간 ',
        FLOOR(SUM(weekly_minutes) % 60), '분'
    ) AS '총학습',
    180 AS '주목표(분)',
    ROUND(SUM(weekly_minutes) / 180 * 100, 2) AS '목표달성률(%)',
    CASE
        WHEN SUM(weekly_minutes) >= 180 THEN '✅ 목표달성'
        WHEN SUM(weekly_minutes) >= 120 THEN '⚠️ 양호'
        ELSE '❌ 미달성'
    END AS '상태'
FROM weekly_study;


-- ============================================
-- 7. 강의별 완강 예상 (최근 4주 평균 기준)
-- ============================================
WITH avg_weekly_study AS (
    SELECT
        curr.course_id,
        AVG(curr.study_time - IFNULL(prev.study_time, 0)) AS avg_weekly_minutes
    FROM course_progress_snapshots curr
    LEFT JOIN course_progress_snapshots prev
        ON curr.course_id = prev.course_id
        AND prev.snapshot_date = DATE_SUB(curr.snapshot_date, INTERVAL 7 DAY)
    WHERE curr.snapshot_date >= DATE_SUB(CURDATE(), INTERVAL 4 WEEK)
        AND curr.study_time > IFNULL(prev.study_time, 0)
    GROUP BY curr.course_id
)
SELECT
    c.course_title AS '강의명',
    c.progress_rate AS '현재진도(%)',
    c.total_lecture_time - c.study_time AS '남은시간(분)',
    ROUND(aws.avg_weekly_minutes, 2) AS '주평균학습(분)',
    CASE
        WHEN aws.avg_weekly_minutes > 0 THEN
            CEILING((c.total_lecture_time - c.study_time) / aws.avg_weekly_minutes)
        ELSE NULL
    END AS '완강예상주차',
    CASE
        WHEN aws.avg_weekly_minutes > 0 THEN
            DATE_ADD(CURDATE(),
                INTERVAL CEILING((c.total_lecture_time - c.study_time) / aws.avg_weekly_minutes) WEEK)
        ELSE NULL
    END AS '예상완강일'
FROM courses c
JOIN avg_weekly_study aws ON c.course_id = aws.course_id
WHERE c.total_lecture_time > c.study_time
ORDER BY CEILING((c.total_lecture_time - c.study_time) / aws.avg_weekly_minutes);


-- ============================================
-- 8. 전체 스냅샷 이력 조회 (디버깅용)
-- ============================================
SELECT
    s.snapshot_date AS '날짜',
    c.course_title AS '강의명',
    s.progress_rate AS '진도율',
    s.study_time AS '학습시간',
    s.total_lecture_time AS '총시간',
    s.created_at AS '기록시각'
FROM course_progress_snapshots s
JOIN courses c ON s.course_id = c.course_id
ORDER BY s.snapshot_date DESC, c.course_title;


-- ============================================
-- 9. 학습 안 한 강의 찾기 (최근 2주)
-- ============================================
SELECT
    c.course_title AS '강의명',
    c.progress_rate AS '진도율',
    c.total_lecture_time - c.study_time AS '남은시간(분)',
    MAX(s.snapshot_date) AS '마지막학습주차'
FROM courses c
LEFT JOIN course_progress_snapshots s ON c.course_id = s.course_id
WHERE c.total_lecture_time > c.study_time
GROUP BY c.course_id, c.course_title, c.progress_rate, c.total_lecture_time, c.study_time
HAVING MAX(s.snapshot_date) < DATE_SUB(CURDATE(), INTERVAL 2 WEEK)
    OR MAX(s.snapshot_date) IS NULL
ORDER BY c.progress_rate DESC;
