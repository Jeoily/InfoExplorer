package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.*;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.server.context.WebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import tools.jackson.databind.json.JsonMapper;
import java.net.*;
import java.net.http.*;
import java.nio.file.Path;
import java.time.Duration;
import static org.junit.jupiter.api.Assertions.*;

/** Explicit public-search test. No model and no daily database. */
@EnabledIfEnvironmentVariable(named="INFOEXPLORER_WEB_LIVE_TEST",matches="1")
class WebLiveIntegrationTests {
    @TempDir Path directory;
    ConfigurableApplicationContext open() {
        String agent=System.getenv("INFOEXPLORER_TEST_AGENT_URL");
        if(agent==null || !agent.matches("http://127\\.0\\.0\\.1:[0-9]+")) throw new IllegalArgumentException("Local test server required");
        return new SpringApplicationBuilder(JavaApiApplication.class).run(
            "--spring.profiles.active=test","--server.address=127.0.0.1","--server.port=0",
            "--research.worker.enabled=false","--agent.service.base-url="+agent,
            "--spring.datasource.url=jdbc:h2:file:"+directory.resolve("web").toString().replace('\\','/')+";DB_CLOSE_ON_EXIT=FALSE");
    }
    String base(ConfigurableApplicationContext app) {
        return "http://127.0.0.1:"+((WebServerApplicationContext)app).getWebServer().getPort()+"/api/v1/research-tasks";
    }
    @Test void publicSearchPersistsAcrossRestartAndIdempotentReplay() throws Exception {
        var http=HttpClient.newHttpClient(); var mapper=JsonMapper.builder().build();
        String payload="{\"question\":\"Python http.client documentation\",\"language\":\"en\",\"researchMode\":\"web\"}";
        String taskId,runId; WebReport expected;
        try(var app=open()) {
            var accepted=http.send(HttpRequest.newBuilder(URI.create(base(app))).header("Content-Type","application/json")
                .header("Idempotency-Key","live-web-replay").POST(HttpRequest.BodyPublishers.ofString(payload)).build(),HttpResponse.BodyHandlers.ofString());
            assertEquals(202,accepted.statusCode()); taskId=mapper.readTree(accepted.body()).path("id").asText();
            assertTrue(app.getBean(ResearchExecutor.class).runNext());
            var response=http.send(HttpRequest.newBuilder(URI.create(base(app)+"/"+taskId)).timeout(Duration.ofSeconds(5)).GET().build(),HttpResponse.BodyHandlers.ofString());
            var task=app.getBean(JsonMapper.class).readValue(response.body(),ResearchTask.class);
            assertEquals(ResearchTask.Status.SUCCEEDED,task.status(),task.errorCode());
            expected=task.webResult(); runId=task.runId();
            assertFalse(expected.outcome().evidence().isEmpty());
            assertEquals(0,expected.outcome().usage().modelCalls());
            System.out.println("LIVE_WEB_CHECK evidence="+expected.outcome().evidence().size()+" readSources="+expected.outcome().sources().stream().filter(s->"READ".equals(s.status())).count()+" modelCalls=0");
        }
        try(var app=open()) {
            var response=http.send(HttpRequest.newBuilder(URI.create(base(app)+"/"+taskId+"/runs/"+runId+"/web-result")).GET().build(),HttpResponse.BodyHandlers.ofString());
            assertEquals(200,response.statusCode()); assertEquals(expected,mapper.readValue(response.body(),WebReport.class));
            var replay=http.send(HttpRequest.newBuilder(URI.create(base(app))).header("Content-Type","application/json")
                .header("Idempotency-Key","live-web-replay").POST(HttpRequest.BodyPublishers.ofString(payload)).build(),HttpResponse.BodyHandlers.ofString());
            assertEquals(202,replay.statusCode());assertEquals(taskId,mapper.readTree(replay.body()).path("id").asText());
            assertEquals(1,app.getBean(ResearchRepository.class).history(taskId).size());
            assertFalse(app.getBean(ResearchExecutor.class).runNext());
            System.out.println("LIVE_WEB_CHECK restart=passed idempotentReplay=passed runs=1");
        }
    }
}
