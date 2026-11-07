package com.infoexplorer.javaapi;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.beans.factory.annotation.Value;
import java.net.URI;
import java.net.http.*;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;

@ActiveProfiles("test")
@SpringBootTest(webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT)
class TrackingApiTests {
 @Value("${local.server.port}") int port;
 final HttpClient client=HttpClient.newHttpClient();
 HttpResponse<String> post(String body,String key) throws Exception {
  var request=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+"/api/v1/tracking-topics"))
    .header("Content-Type","application/json").header("Idempotency-Key",key)
    .POST(HttpRequest.BodyPublishers.ofString(body)).build();
  return client.send(request,HttpResponse.BodyHandlers.ofString());
 }
 @Test void validatesInputsAndReplaysCreation() throws Exception {
  String key=UUID.randomUUID().toString();
  String body="""
   {"name":"Public topic","question":"public question","language":"en","researchMode":"web","scheduleMinutes":0}
   """;
  var first=post(body,key); assertEquals(200,first.statusCode());
  assertEquals(first.body(),post(body,key).body());
  assertEquals(409,post(body.replace("Public topic","Other topic"),key).statusCode());
  assertEquals(400,post(body.replace("public question"," "),UUID.randomUUID().toString()).statusCode());
  assertEquals(400,post(body.replace("\"web\"","\"web-model\"").replace(":0",":60"),UUID.randomUUID().toString()).statusCode());
  assertEquals(400,post(body,"bad key").statusCode());
 }
}
