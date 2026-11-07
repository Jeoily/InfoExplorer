package com.infoexplorer.javaapi;
import com.infoexplorer.javaapi.research.*;
import com.infoexplorer.javaapi.client.WebReportValidator;
import tools.jackson.databind.json.JsonMapper;
import java.nio.charset.StandardCharsets;
import java.util.List;

final class SessionFixtures {
    static final String ID="11111111-1111-4111-8111-111111111111";
    static ModelSessionReport report(String variant,String runId,String language) {
        var mapper=JsonMapper.builder().build();
        try(var stream=SessionFixtures.class.getResourceAsStream("/model-sessions/"+variant+".json")) {
            String raw=new String(stream.readAllBytes(),StandardCharsets.UTF_8);
            var original=mapper.readValue(raw,ModelSessionReport.class);
            if(original.session().outcome()!=null) for(var e:original.session().outcome().evidence()) {
                String key=WebReportValidator.hash(mapper.writeValueAsString(List.of(runId,e.sourceId(),e.paragraphIndex(),e.offsetUtf16(),e.contentHash())));
                raw=raw.replace(e.evidenceKey(),key);
            }
            return mapper.readValue(raw.replace(ID,runId).replace("\"language\":\"en\"","\"language\":\""+language+"\""),ModelSessionReport.class);
        } catch(Exception e) { throw new IllegalStateException(e); }
    }
}
