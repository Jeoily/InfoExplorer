package com.infoexplorer.javaapi;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.io.IOException;
import java.net.ServerSocket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

@org.springframework.test.context.ActiveProfiles("test")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class UnavailableAgentApiTests {
    @Value("${local.server.port}") int port;

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry registry) throws IOException {
        int unusedPort;
        try (var socket = new ServerSocket(0)) { unusedPort = socket.getLocalPort(); }
        registry.add("agent.service.base-url", () -> "http://127.0.0.1:" + unusedPort);
        registry.add("agent.service.connect-timeout-ms", () -> 500);
    }

    @Test
    void returns502WhenAgentIsNotRunning() throws Exception {
        var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/api/v1/chat/ask"))
                .timeout(Duration.ofSeconds(5)).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString("{\"question\":\"hello\"}")).build();
        var response = HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofString());
        assertEquals(502, response.statusCode());
        assertTrue(response.body().contains("AGENT_UNAVAILABLE"));
    }
}
