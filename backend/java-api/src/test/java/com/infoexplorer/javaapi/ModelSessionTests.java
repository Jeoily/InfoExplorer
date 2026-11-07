package com.infoexplorer.javaapi;
import com.infoexplorer.javaapi.client.*;
import com.infoexplorer.javaapi.research.*;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;
import static org.junit.jupiter.api.Assertions.*;

class ModelSessionTests extends WebResearchTests {
    @Test void auditedVersionRequiresSuccessfulFinalAudit() {
        var mapper=JsonMapper.builder().build();
        var tree=(tools.jackson.databind.node.ObjectNode)mapper.readTree(
            mapper.writeValueAsString(SessionFixtures.report("public-topic",SessionFixtures.ID,"en")));
        var session=(tools.jackson.databind.node.ObjectNode)tree.get("session");
        session.put("version","web-model-session-v2");
        ((tools.jackson.databind.node.ObjectNode)session.get("usage")).put("modelCalls",4);
        ((tools.jackson.databind.node.ObjectNode)session.get("outcome").get("usage")).put("modelCalls",4);
        assertThrows(AgentException.class,()->ModelSessionValidator.validate(mapper.treeToValue(tree,ModelSessionReport.class),SessionFixtures.ID,"public topic","en",mapper));
        var events=(tools.jackson.databind.node.ArrayNode)session.get("events");
        var audit=mapper.createObjectNode().put("stage","verify").put("status","SUCCEEDED").putNull("code").put("inputHash","a".repeat(64));
        events.add(audit);
        assertDoesNotThrow(()->ModelSessionValidator.validate(mapper.treeToValue(tree,ModelSessionReport.class),SessionFixtures.ID,"public topic","en",mapper));
        audit.put("status","FAILED").put("code","MODEL_TIMEOUT");
        assertThrows(AgentException.class,()->ModelSessionValidator.validate(mapper.treeToValue(tree,ModelSessionReport.class),SessionFixtures.ID,"public topic","en",mapper));
    }
    @Test void acceptsPythonGeneratedSnapshotsAndRejectsForgedDecisions() {
        var mapper=JsonMapper.builder().build();
        for(String variant:List.of("public-topic","supplement","fail-report","fallback","auth-failure","empty")) {
            var report=SessionFixtures.report(variant,SessionFixtures.ID,"en");
            assertDoesNotThrow(()->ModelSessionValidator.validate(report,SessionFixtures.ID,variant.replace('-',' '),"en",mapper),variant);
        }
        String raw=mapper.writeValueAsString(SessionFixtures.report("public-topic",SessionFixtures.ID,"en"));
        for(String bad:List.of(raw.replace("EVIDENCE_SUFFICIENT","SUPPLEMENT_ROUND_LIMIT"),
            raw.replace("\"text\":\"A bounded inference\"","\"text\":\"Mismatched answer\""),raw.replace("\"modelCalls\":3","\"modelCalls\":1"),
            raw.replace("\"evidenceIds\":[\"E1\"]","\"evidenceIds\":[\"E16\"]"),
            raw.replace("\"inputHash\":\"","\"inputHash\":\"x"))) {
            assertThrows(AgentException.class,()->ModelSessionValidator.validate(mapper.readValue(bad,ModelSessionReport.class),SessionFixtures.ID,"public topic","en",mapper));
        }
    }
    @Test void sessionPersistsFailureHistoryAndRestartWithoutReexecution() {
        String id,first,second;
        try(var app=open()) {
            var service=app.getBean(ResearchService.class); var repo=app.getBean(ResearchRepository.class);
            id=service.create("public topic","model-key","en","web-model").id();
            assertEquals(id,service.create("public topic","model-key","en","web-model").id());
            assertThrows(ResearchException.class,()->service.create("public topic","model-key","en","web"));
            var a=repo.claimNext().orElseThrow(); first=a.runId();
            repo.finishSession(a,SessionFixtures.report("fail-report",first,"en"));
            assertFalse(repo.find(id).orElseThrow().modelSession().session().outcome().evidence().isEmpty());
            repo.retry(id,first); var b=repo.claimNext().orElseThrow(); second=b.runId();
            assertEquals("web-model",b.researchMode());
            repo.finishSession(b,SessionFixtures.report("public-topic",second,"en"));
            assertThrows(RuntimeException.class,()->repo.finishSession(a,SessionFixtures.report("public-topic",first,"en")));
            assertTrue(repo.sessionRun(UUID.randomUUID().toString(),first).isEmpty());
        }
        try(var app=open()) {
            var repo=app.getBean(ResearchRepository.class);
            assertEquals("MODEL_INVALID_RESPONSE",repo.sessionRun(id,first).orElseThrow().session().stopReason());
            assertEquals(second,repo.find(id).orElseThrow().modelSession().session().runId());
            assertEquals(2,repo.history(id).size()); assertFalse(app.getBean(ResearchExecutor.class).runNext());
        }
    }
    @Test void sessionHttpRejectsMissingFieldsAndWrongIdentity() throws Exception {
        var mapper=JsonMapper.builder().build();
        String raw=mapper.writeValueAsString(SessionFixtures.report("public-topic",SessionFixtures.ID,"en"));
        var response=new AtomicReference<>(raw);
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/internal/v3/research/run",e->{
            byte[] bytes=response.get().getBytes(StandardCharsets.UTF_8);
            e.getResponseHeaders().set("Content-Type","application/json"); e.sendResponseHeaders(200,bytes.length);
            try {e.getResponseBody().write(bytes);} finally {e.close();}
        });server.start();
        try {
            var client=new WebAgentClient("http://127.0.0.1:"+server.getAddress().getPort(),mapper);
            assertEquals("web-model",client.researchSession(SessionFixtures.ID,"public topic","en").mode());
            for(String bad:List.of(raw.replace(SessionFixtures.ID,UUID.randomUUID().toString()),raw.replace("\"modelCalls\":3,",""),
                raw.replace("\"schemaVersion\":","\"tools\":[],\"schemaVersion\":"),
                raw.replace("\"modelCalls\":3","\"modelCalls\":0,\"modelCalls\":3")," ".repeat(524289))) {
                response.set(bad); assertThrows(AgentException.class,()->client.researchSession(SessionFixtures.ID,"public topic","en"));
            }
        } finally {server.stop(0);}
    }
}
