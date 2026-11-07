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
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

/** Real Java and Python HTTP, synthetic external tools, isolated persistent H2. */
@EnabledIfEnvironmentVariable(named="INFOEXPLORER_SESSION_HTTP_TEST",matches="1")
class SessionHttpIntegrationTests {
    @TempDir Path directory;
    ConfigurableApplicationContext open() {
        String agent=System.getenv("INFOEXPLORER_TEST_AGENT_URL");
        if(agent==null || !agent.matches("http://127\\.0\\.0\\.1:[0-9]+")) throw new IllegalArgumentException("Local test server required");
        return new SpringApplicationBuilder(JavaApiApplication.class).run(
            "--spring.profiles.active=test","--server.address=127.0.0.1","--server.port=0","--research.worker.enabled=false",
            "--agent.service.base-url="+agent,"--spring.datasource.url=jdbc:h2:file:"+directory.resolve("sessions").toString().replace('\\','/')+";DB_CLOSE_ON_EXIT=FALSE");
    }
    String base(ConfigurableApplicationContext app) {return "http://127.0.0.1:"+((WebServerApplicationContext)app).getWebServer().getPort()+"/api/v1/research-tasks";}
    @Test void allOutcomesSurviveHttpPersistenceAndRestart() throws Exception {
        var http=HttpClient.newHttpClient(); var mapper=JsonMapper.builder().build();
        Map<String,ResearchTask> saved=new LinkedHashMap<>();
        try(var app=open()) {
            for(String question:List.of("public topic","supplement","fail report","fallback","auth failure","empty")) {
                String body=mapper.writeValueAsString(Map.of("question",question,"language","en","researchMode","web-model"));
                var accepted=http.send(HttpRequest.newBuilder(URI.create(base(app))).header("Content-Type","application/json")
                    .header("Idempotency-Key",question.replace(' ','-')).POST(HttpRequest.BodyPublishers.ofString(body)).build(),HttpResponse.BodyHandlers.ofString());
                assertEquals(202,accepted.statusCode()); String id=mapper.readTree(accepted.body()).path("id").asText();
                assertTrue(app.getBean(ResearchExecutor.class).runNext());
                var got=http.send(HttpRequest.newBuilder(URI.create(base(app)+"/"+id)).GET().build(),HttpResponse.BodyHandlers.ofString());
                var task=mapper.readValue(got.body(),ResearchTask.class);
                assertNotNull(task.modelSession(),question+": "+task.errorCode());
                assertEquals(question.equals("fail report")||question.equals("auth failure")?ResearchTask.Status.FAILED:ResearchTask.Status.SUCCEEDED,task.status());
                saved.put(question,task);
            }
        }
        try(var app=open()) {
            for(var task:saved.values()) {
                var got=http.send(HttpRequest.newBuilder(URI.create(base(app)+"/"+task.id()+"/runs/"+task.runId()+"/model-session")).GET().build(),HttpResponse.BodyHandlers.ofString());
                assertEquals(200,got.statusCode()); assertEquals(task.modelSession(),mapper.readValue(got.body(),ModelSessionReport.class));
                String body=mapper.writeValueAsString(Map.of("question",task.question(),"language","en","researchMode","web-model"));
                var replay=http.send(HttpRequest.newBuilder(URI.create(base(app))).header("Content-Type","application/json")
                    .header("Idempotency-Key",task.question().replace(' ','-')).POST(HttpRequest.BodyPublishers.ofString(body)).build(),HttpResponse.BodyHandlers.ofString());
                assertEquals(202,replay.statusCode()); assertEquals(task.id(),mapper.readTree(replay.body()).path("id").asText());
                assertEquals(1,app.getBean(ResearchRepository.class).history(task.id()).size());
            }
            assertFalse(app.getBean(ResearchExecutor.class).runNext());
            System.out.println("SESSION_HTTP_CHECK outcomes=6 restart=passed replay=passed externalCalls=0");
        }
    }
}
