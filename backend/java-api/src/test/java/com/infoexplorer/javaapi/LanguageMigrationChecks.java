package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.ResearchRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

class LanguageMigrationChecks {
    static String seed(JdbcTemplate jdbc, String language) {
        String id=UUID.randomUUID().toString();
        jdbc.update("INSERT INTO research_task(id,question,status,created_at,updated_at) VALUES (?, 'public topic','SUCCEEDED',1,2)",id);
        jdbc.update("INSERT INTO research_run(id,task_id,status,started_at,completed_at,answer,sources_json,report_provider) VALUES (?,?,'SUCCEEDED',1,2,'unchanged','[]',?)",UUID.randomUUID().toString(),id,"wikipedia-"+language);
        return id;
    }
    static void verify(ResearchRepository store, JdbcTemplate jdbc, String en, String zh) {
        assertEquals("en",store.find(en).orElseThrow().language());
        assertEquals("zh",store.find(zh).orElseThrow().language());
        assertEquals("unchanged",store.find(zh).orElseThrow().result().answer());
        assertThrows(org.springframework.dao.DataAccessException.class,()->jdbc.update("UPDATE research_task SET search_language='fr' WHERE id=?",en));
    }
}
