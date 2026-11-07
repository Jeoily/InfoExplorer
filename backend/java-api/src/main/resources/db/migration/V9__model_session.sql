ALTER TABLE research_task DROP CONSTRAINT ck_research_mode;
ALTER TABLE research_task ADD CONSTRAINT ck_research_mode CHECK (research_mode IN ('wikipedia', 'web', 'web-model'));
ALTER TABLE research_run ADD COLUMN model_session_json CLOB;
