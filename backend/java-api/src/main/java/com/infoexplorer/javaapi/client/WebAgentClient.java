package com.infoexplorer.javaapi.client;

import com.infoexplorer.javaapi.research.WebReport;
import com.infoexplorer.javaapi.research.ModelSessionReport;
import java.io.ByteArrayOutputStream;
import java.net.URI;
import java.net.http.*;
import java.nio.ByteBuffer;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.Flow;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;

@Component
public class WebAgentClient {
    private final HttpClient client;
    private final URI endpoint;
    private final JsonMapper mapper;
    public WebAgentClient(@Value("${agent.service.base-url}") String base, JsonMapper mapper) {
        endpoint=URI.create(base.replaceAll("/$","")+"/internal/v2/research/run");
        if(!Set.of("http","https").contains(endpoint.getScheme()) || endpoint.getHost()==null || endpoint.getUserInfo()!=null
            || endpoint.getQuery()!=null || endpoint.getFragment()!=null) throw new IllegalArgumentException("Invalid Agent URL");
        this.mapper=mapper.rebuild().enable(tools.jackson.core.StreamReadFeature.STRICT_DUPLICATE_DETECTION).build();
        client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).followRedirects(HttpClient.Redirect.NEVER).build();
    }
    public WebReport research(String runId,String question,String language) {
        WebReport result=call(endpoint,runId,question,language,WebReport.class);
        WebReportValidator.validate(result,runId,question,language,mapper);
        return result;
    }
    public ModelSessionReport researchSession(String runId,String question,String language) {
        URI sessionEndpoint=URI.create(endpoint.toString().replace("/internal/v2/research/run","/internal/v3/research/run"));
        ModelSessionReport result=call(sessionEndpoint,runId,question,language,ModelSessionReport.class);
        ModelSessionValidator.validate(result,runId,question,language,mapper);
        return result;
    }
    public WebReport researchControlled(String runId,String question,String language,String resumeFrom,Runnable tick) {
        var result=call(endpoint,runId,question,language,WebReport.class,resumeFrom,tick);
        WebReportValidator.validate(result,runId,question,language,mapper);
        return result;
    }
    public ModelSessionReport sessionControlled(String runId,String question,String language,String resumeFrom,Runnable tick) {
        var uri=URI.create(endpoint.toString().replace("/internal/v2/research/run","/internal/v3/research/run"));
        var result=call(uri,runId,question,language,ModelSessionReport.class,resumeFrom,tick);
        ModelSessionValidator.validate(result,runId,question,language,mapper);
        return result;
    }
    public record Progress(String runId,String state,String stage,boolean cancelRequested,long updatedAt,int reused) {}
    public com.infoexplorer.javaapi.research.ResearchReport wikiControlled(String runId,String question,String language,Runnable tick) {
        return call(URI.create(endpoint.toString().replace("/internal/v2/research/run","/internal/v1/research/run")),
            runId,question,language,com.infoexplorer.javaapi.research.ResearchReport.class,null,tick);
    }
    public Progress progress(String runId,boolean cancel) {
        var uri=URI.create(endpoint.toString().replace("/internal/v2/research/run","/internal/research/executions/"+runId+(cancel?"/cancel":"")));
        var builder=HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(2));
        if(cancel) builder.POST(HttpRequest.BodyPublishers.noBody());
        try {
            var response=client.send(builder.build(),info->new LimitedBody(2048));
            if(response.statusCode()!=200 || cancel) return null;
            var p=mapper.readValue(response.body(),Progress.class);
            return runId.equals(p.runId())?p:null;
        } catch(InterruptedException e) { Thread.currentThread().interrupt(); return null; }
        catch(Exception e) { return null; }
    }
    private <T> T call(URI target,String runId,String question,String language,Class<T> type) {
        return call(target,runId,question,language,type,null,()->{});
    }
    private <T> T call(URI target,String runId,String question,String language,Class<T> type,String resumeFrom,Runnable tick) {
        var body=new HashMap<String,Object>();
        body.put("runId",runId); body.put("question",question); body.put("language",language);
        if(resumeFrom!=null) body.put("resumeFrom",resumeFrom);
        if(type==com.infoexplorer.javaapi.research.ResearchReport.class) body.remove("runId");
        var request=HttpRequest.newBuilder(target).timeout(Duration.ofSeconds(175))
            .header("Content-Type","application/json").header("Accept","application/json")
            .header("X-Research-Run-Id",runId)
            .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body))).build();
        var pending=client.sendAsync(request, info->new LimitedBody(info.statusCode()==200?512*1024:2048));
        try {
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(175);
            HttpResponse<byte[]> response;
            while(true) {
                long remaining=deadline-System.nanoTime();
                if(remaining<=0) throw new TimeoutException();
                try { response=pending.get(Math.min(remaining,TimeUnit.SECONDS.toNanos(1)),TimeUnit.NANOSECONDS); break; }
                catch(TimeoutException waiting) { tick.run(); }
            }
            tick.run();
            if(response.statusCode()!=200) {
                String code=null;
                try {
                    String candidate=mapper.readTree(response.body()).path("detail").path("code").asText();
                    if(candidate.isEmpty()) candidate=mapper.readTree(response.body()).path("code").asText();
                    if(Set.of("WEB_DISABLED","WEB_MODEL_DISABLED","WEB_BUSY","WEB_RESPONSE_TOO_LARGE","MODEL_CONFIG_ERROR","MODEL_AUTH_ERROR","EXECUTION_CANCELLED","EXECUTION_DEADLINE","EXECUTION_ALREADY_STARTED","EXECUTION_ID_CONFLICT","RESUME_ID_CONFLICT").contains(candidate)) code=candidate;
                    if(type==com.infoexplorer.javaapi.research.ResearchReport.class && Set.of("SEARCH_TIMEOUT","SEARCH_UNAVAILABLE","SEARCH_INVALID_RESPONSE","SEARCH_RATE_LIMITED",
                        "MODEL_TIMEOUT","MODEL_UNAVAILABLE","MODEL_INVALID_RESPONSE","MODEL_RATE_LIMITED","MODEL_AUTH_ERROR","MODEL_CONFIG_ERROR","MODEL_INPUT_TOO_LARGE","MODEL_BUSY").contains(candidate)) code=candidate;
                } catch(RuntimeException ignored) { }
                throw new AgentException(AgentException.Reason.REJECTED,null,code);
            }
            if(!response.headers().firstValue("content-type").orElse("").split(";",2)[0].equalsIgnoreCase("application/json"))
                throw new AgentException(AgentException.Reason.INVALID_RESPONSE,null);
            T result=mapper.readerFor(type).with(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                .with(DeserializationFeature.FAIL_ON_MISSING_CREATOR_PROPERTIES)
                .with(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES).without(DeserializationFeature.ACCEPT_FLOAT_AS_INT).readValue(response.body());
            return result;
        } catch(TimeoutException e) { pending.cancel(true); progress(runId,true); throw new AgentException(AgentException.Reason.TIMEOUT,e); }
        catch(InterruptedException e) { pending.cancel(true); progress(runId,true); Thread.currentThread().interrupt(); throw new AgentException(AgentException.Reason.UNAVAILABLE,e); }
        catch(ExecutionException e) {
            if(e.getCause() instanceof HttpTimeoutException) throw new AgentException(AgentException.Reason.TIMEOUT,e);
            if(e.getCause() instanceof IllegalArgumentException) throw new AgentException(AgentException.Reason.INVALID_RESPONSE,e);
            throw new AgentException(AgentException.Reason.UNAVAILABLE,e);
        } catch(AgentException e) { throw e; }
        catch(RuntimeException e) { pending.cancel(true); progress(runId,true); throw new AgentException(AgentException.Reason.INVALID_RESPONSE,e); }
    }
    /** Cancels upstream before accumulating more than the permitted byte count. */
    static final class LimitedBody implements HttpResponse.BodySubscriber<byte[]> {
        private final CompletableFuture<byte[]> result=new CompletableFuture<>();
        private final ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        private final int limit;
        private Flow.Subscription subscription;
        LimitedBody(int limit) { this.limit=limit; }
        public CompletionStage<byte[]> getBody() { return result; }
        public void onSubscribe(Flow.Subscription s) { subscription=s; s.request(1); }
        public void onNext(List<ByteBuffer> chunks) {
            for(var chunk:chunks) {
                if(chunk.remaining()>limit-bytes.size()) {
                    subscription.cancel(); result.completeExceptionally(new IllegalArgumentException("Agent response exceeds limit")); return;
                }
                byte[] copy=new byte[chunk.remaining()]; chunk.get(copy); bytes.writeBytes(copy);
            }
            subscription.request(1);
        }
        public void onError(Throwable error) { result.completeExceptionally(error); }
        public void onComplete() { result.complete(bytes.toByteArray()); }
    }
}
