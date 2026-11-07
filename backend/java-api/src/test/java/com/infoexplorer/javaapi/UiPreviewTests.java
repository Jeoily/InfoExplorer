package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.*;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.builder.SpringApplicationBuilder;
import tools.jackson.databind.json.JsonMapper;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import static org.junit.jupiter.api.Assertions.*;

/** Explicit, temporary browser verification harness: real Java/H2, local Agent fixture; no external calls. */
@EnabledIfEnvironmentVariable(named="INFOEXPLORER_UI_PREVIEW",matches="1")
class UiPreviewTests {
    @Test void preview() throws Exception {
        var json=JsonMapper.builder().build();
        var failures=new AtomicInteger();
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/internal/v1/research/run", exchange->{
            var request=json.readTree(new String(exchange.getRequestBody().readAllBytes(),StandardCharsets.UTF_8));
            String question=request.get("question").asText();
            int status=200;
            String body;
            if(question.equals("RETRY_ONCE") && failures.getAndIncrement()==0) {status=502;body="{\"code\":\"MODEL_TIMEOUT\",\"message\":\"Offline fixture\"}";}
            else if(question.equals("EMPTY_RESULT")) {body=json.writeValueAsString(new ResearchReport("No evidence",List.of(),"wikipedia-"+request.get("language").asText(),question,java.time.Instant.now(),List.of()));}
            else if(question.equals("PLAN_FIXTURE")) {
                var base=ReportFixtures.planned(ReportFixtures.report("离线规划报告 [E1]",List.of("https://example.org/evidence")));
                var plan=base.plan();
                var q=plan.queries().getFirst();
                var localized=new SearchPlan(plan.mode(),plan.intent(),null,List.of(new SearchPlan.Query(q.query(),request.get("language").asText(),q.status(),q.resultCount(),q.evidenceIds(),null)),plan.generation());
                body=json.writeValueAsString(new ResearchReport(base.answer(),base.sources(),base.provider(),base.query(),base.retrievedAt(),base.evidence(),null,localized));
            }
            else {
                body=json.writeValueAsString(ReportFixtures.report("离线演示报告 [E1]\n公开资料示例。<img src=x onerror=alert(1)>",List.of("https://example.org/evidence")));
            }
            byte[] bytes=body.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type","application/json");
            exchange.sendResponseHeaders(status,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });
        server.createContext("/internal/v2/research/run", exchange->{
            var request=json.readTree(exchange.getRequestBody().readAllBytes());
            byte[] bytes=json.writeValueAsBytes(WebFixtures.report(request.path("runId").asText(),request.path("question").asText(),request.path("language").asText(),false));
            exchange.getResponseHeaders().set("Content-Type","application/json");
            exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });
        server.createContext("/internal/v3/research/run", exchange->{
            var request=json.readTree(exchange.getRequestBody().readAllBytes());
            String variant=request.path("question").asText().equals("fail report")?"fail-report":"supplement";
            byte[] bytes=json.writeValueAsBytes(SessionFixtures.report(variant,request.path("runId").asText(),request.path("language").asText()));
            exchange.getResponseHeaders().set("Content-Type","application/json");
            exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });
        server.start();
        Path stop=Path.of("target/ui-preview.stop"); Files.deleteIfExists(stop);
        try(var context=new SpringApplicationBuilder(JavaApiApplication.class).run(
                "--spring.profiles.active=test", "--server.address=127.0.0.1", "--server.port=18080",
                "--spring.datasource.url=jdbc:h2:mem:ui_preview_"+java.util.UUID.randomUUID(),
                "--agent.service.base-url=http://127.0.0.1:"+server.getAddress().getPort(),
                "--research.worker.enabled=true", "--research.worker.poll-delay-ms=100")) {
            System.out.println("UI_PREVIEW_READY http://127.0.0.1:18080 (offline fixtures, isolated H2)");
            long until=System.nanoTime()+java.time.Duration.ofMinutes(10).toNanos();
            while(!Files.exists(stop)&&System.nanoTime()<until) Thread.sleep(200);
            assertTrue(Files.exists(stop),"Browser verification did not signal completion within ten minutes");
        } finally {server.stop(0);Files.deleteIfExists(stop);}
    }
}
