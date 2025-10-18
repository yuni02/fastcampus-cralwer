-- Add chapter fields to lectures table
-- This migration adds chapter_number and chapter_title fields to track the chapter hierarchy
-- Hierarchy: Part (section) -> Chapter -> Lecture

ALTER TABLE `lectures`
ADD COLUMN `chapter_number` int DEFAULT NULL COMMENT '챕터 번호 (섹션 내)' AFTER `section_title`,
ADD COLUMN `chapter_title` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '챕터 제목' AFTER `chapter_number`;

-- Add index for chapter queries
ALTER TABLE `lectures`
ADD KEY `idx_chapter` (`course_id`, `section_number`, `chapter_number`);

-- Update the unique constraint to include chapter (optional - only if you want uniqueness at chapter level)
-- First drop the old constraint
ALTER TABLE `lectures`
DROP KEY `unique_course_section_lecture`;

-- Add new constraint that includes chapter
ALTER TABLE `lectures`
ADD UNIQUE KEY `unique_course_section_chapter_lecture` (`course_id`, `section_number`, `chapter_number`, `lecture_number`);
