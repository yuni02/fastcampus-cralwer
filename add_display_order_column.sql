-- courses 테이블에 display_order 컬럼 추가
-- 강의가 /me/courses 페이지에서 표시되는 순서를 저장

ALTER TABLE courses
ADD COLUMN display_order INT NULL COMMENT '강의 표시 순서 (작을수록 위에 표시)',
ADD INDEX idx_display_order (display_order);

-- 기존 데이터에 대해 display_order를 NULL로 유지 (자동으로 NULL이 됨)
-- 다음 fastcampus_discover 실행 시 순서가 자동으로 저장됨
