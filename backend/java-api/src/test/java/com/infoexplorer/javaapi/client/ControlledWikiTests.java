package com.infoexplorer.javaapi.client;
import org.junit.jupiter.api.Test;
import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import tools.jackson.databind.json.JsonMapper;
import static org.junit.jupiter.api.Assertions.*;

class ControlledWikiTests {
    @Test void preservesLegacySafeErrorAndPassesExecutionIdentity() throws Exception {
        var server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/internal/v1/research/run",exchange->{
            assertEquals("11111111-1111-4111-8111-111111111111",exchange.getRequestHeaders().getFirst("X-Research-Run-Id"));
            String body=new String(exchange.getRequestBody().readAllBytes(),StandardCharsets.UTF_8);
            assertFalse(body.contains("runId"));
            byte[] bytes="{\"code\":\"SEARCH_TIMEOUT\"}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(504,bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });
        server.start();
        try {
            var client=new WebAgentClient("http://127.0.0.1:"+server.getAddress().getPort(),JsonMapper.builder().build());
            var e=assertThrows(AgentException.class,()->client.wikiControlled("11111111-1111-4111-8111-111111111111","public topic","en",()->{}));
            assertEquals("SEARCH_TIMEOUT",e.providerCode());
        } finally {server.stop(0);}
    }
}
