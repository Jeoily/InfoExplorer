ALTER TABLE research_task ADD COLUMN search_language VARCHAR(2) NOT NULL DEFAULT 'en' CHECK (search_language IN ('en', 'zh'));
UPDATE research_task SET search_language = 'zh' WHERE EXISTS (
 SELECT 1 FROM research_run r WHERE r.task_id = research_task.id AND r.report_provider = 'wikipedia-zh'
);
