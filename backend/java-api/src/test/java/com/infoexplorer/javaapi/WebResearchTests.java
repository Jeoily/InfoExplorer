package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.client.*;
import com.infoexplorer.javaapi.research.*;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;
import tools.jackson.databind.json.JsonMapper;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.*;

class WebResearchTests {
    @TempDir Path directory;
    ConfigurableApplicationContext open() {
        return new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run(
            "--spring.profiles.active=test","--research.worker.enabled=false",
            "--spring.datasource.url=jdbc:h2:file:"+directory.resolve("web").toString().replace('\\','/')+";DB_CLOSE_ON_EXIT=FALSE");
    }
    @Test void preservesFailedEvidenceAcrossRetryAndRestartAndSeparatesModes() {
        String taskId, runId, secondId;
        try(var app=open()) {
            var service=app.getBean(ResearchService.class); var repo=app.getBean(ResearchRepository.class);
            var task=service.create("public topic","web-key","en","web"); taskId=task.id();
            assertEquals(taskId,service.create("public topic","web-key","en","web").id());
            assertThrows(RuntimeException.class,()->service.create("public topic","web-key","en","wikipedia"));
            var claim=repo.claimNext().orElseThrow();runId=claim.runId();
            repo.finishWeb(claim,WebFixtures.report(runId,claim.question(),"en",true));
            assertEquals(1,repo.find(taskId).orElseThrow().webResult().outcome().evidence().size());
            repo.retry(taskId,runId); var second=repo.claimNext().orElseThrow();secondId=second.runId();
            repo.finishWeb(second,WebFixtures.report(secondId,second.question(),"en",false));
            assertThrows(RuntimeException.class,()->repo.finishWeb(claim,WebFixtures.report(runId,claim.question(),"en",false)));
            assertTrue(repo.webRun(UUID.randomUUID().toString(),runId).isEmpty());
            assertEquals("wikipedia",service.create("legacy",null).researchMode());
        }
        try(var app=open()) {
            var repo=app.getBean(ResearchRepository.class);
            assertEquals("FAILED",repo.webRun(taskId,runId).orElseThrow().outcome().status());
            assertEquals(secondId,repo.find(taskId).orElseThrow().webResult().outcome().runId());
            assertEquals(2,repo.history(taskId).size());
            assertNull(repo.find(taskId).orElseThrow().result());
        }
    }
    @Test void enforcesWireIdentityIntegrityLimitsAndRequiredFields() throws Exception {
        var mapper=JsonMapper.builder().build(); String run=UUID.randomUUID().toString();
        String valid=mapper.writeValueAsString(WebFixtures.report(run,"public topic","en",false));
        var response=new AtomicReference<>(valid);
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/internal/v2/research/run",exchange->{
            var request=mapper.readTree(exchange.getRequestBody().readAllBytes());
            assertEquals(run,request.path("runId").asText());
            byte[] bytes=response.get().getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type","application/json");
            exchange.sendResponseHeaders(200,bytes.length);
            try {exchange.getResponseBody().write(bytes);} finally {exchange.close();}
        });server.start();
        try {
            var client=new WebAgentClient("http://127.0.0.1:"+server.getAddress().getPort(),mapper);
            assertEquals(run,client.research(run,"public topic","en").outcome().runId());
            for(String bad:java.util.List.of(valid.replace(run,UUID.randomUUID().toString()),
                valid.replace("Public evidence <img","Changed evidence <img"),
                valid.replace("\"modelCalls\":0,",""), valid.replace("\"modelCalls\":0","\"modelCalls\":1"),
                valid.replace("\"schemaVersion\":","\"unknownField\":true,\"schemaVersion\":")," ".repeat(512*1024+1))) {
                response.set(bad);
                assertEquals(AgentException.Reason.INVALID_RESPONSE,assertThrows(AgentException.class,()->client.research(run,"public topic","en")).reason());
            }
            response.set(mapper.writeValueAsString(WebFixtures.report(run,"public topic","en",true)));
            assertEquals(1,client.research(run,"public topic","en").outcome().evidence().size());
        } finally {server.stop(0);}
    }
}
