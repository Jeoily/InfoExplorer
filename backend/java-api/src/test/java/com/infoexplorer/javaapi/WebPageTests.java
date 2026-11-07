package com.infoexplorer.javaapi;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import java.net.URI;
import java.net.http.*;
import static org.junit.jupiter.api.Assertions.*;

@ActiveProfiles("test")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class WebPageTests {
    @Value("${local.server.port}") int port;
    @Test void servesWorkspaceAndAssetsWithBrowserProtection() throws Exception {
        var http=HttpClient.newHttpClient();
        for (String path : new String[]{"/", "/app.js", "/app.css"}) {
            var response=http.send(HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path)).GET().build(), HttpResponse.BodyHandlers.ofString());
            assertEquals(200,response.statusCode());
            assertTrue(response.headers().firstValue("Content-Security-Policy").orElseThrow().contains("frame-ancestors 'none'"));
            assertEquals("nosniff",response.headers().firstValue("X-Content-Type-Options").orElseThrow());
            if(path.equals("/")) { assertTrue(response.body().contains("create-form")); assertTrue(response.body().contains("retry-dialog")); }
        }
    }
}
