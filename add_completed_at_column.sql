-- lectures 테이블에 completed_at 컬럼 추가
-- 강의를 완료한 일시를 기록하여 매일 새로 들은 강의를 추적할 수 있습니다.

ALTER TABLE lectures
ADD COLUMN completed_at TIMESTAMP NULL COMMENT '완료 일시',
ADD INDEX idx_completed_at (completed_at);

-- 확인
DESCRIBE lectures;
