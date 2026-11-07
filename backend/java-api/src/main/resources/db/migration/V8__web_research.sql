ALTER TABLE research_task ADD COLUMN research_mode VARCHAR(16) NOT NULL DEFAULT 'wikipedia';
ALTER TABLE research_task ADD CONSTRAINT ck_research_mode CHECK (research_mode IN ('wikipedia', 'web'));
ALTER TABLE research_run ADD COLUMN web_result_json CLOB;
