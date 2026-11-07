package com.infoexplorer.javaapi;

import com.infoexplorer.javaapi.research.WebReport;
import com.infoexplorer.javaapi.client.WebReportValidator;
import tools.jackson.databind.json.JsonMapper;
import java.util.*;

final class WebFixtures {
    static WebReport report(String runId, String question, String language, boolean failed) {
        return report(runId,question,language,failed,"https://example.org/evidence","Public evidence <img src=x onerror=alert(1)>","fixture");
    }
    static WebReport report(String runId,String question,String language,boolean failed,String url,String excerpt,String extractor) {
        String source="S"+WebReportValidator.hash(url);
        String hash=WebReportValidator.hash(excerpt);
        String key=WebReportValidator.hash(JsonMapper.builder().build().writeValueAsString(List.of(runId,source,0,0,hash)));
        var passage=new WebReport.Passage("E1",source,0,0,excerpt,hash,List.of("Q1"),1,false,key);
        var candidate=new WebReport.Candidate(source,url,url,"example.org","Example source","",1,List.of("fixture"),null);
        var metadata=new WebReport.Metadata(url,url,"example.org","2026-10-19T00:00:00Z","text/html",1,extractor,null,"unknown",false,hash,"paragraph-json-v1");
        question=question.strip().replaceAll("(?U)\\s+"," ");
        return new WebReport("web-research-v2","web-extract",language,"direct",Map.of("Q1",question),
            new WebReport.Outcome(failed?"FAILED":"SUCCEEDED",failed?"EXECUTION_DEADLINE":"COMPLETED","unknown",failed?null:"Public evidence [E1]",
                List.of(passage),List.of(new WebReport.Query(question,0,"SUCCEEDED",List.of(source),List.of(),null)),
                List.of(new WebReport.Source(candidate,"READ",null,metadata)),new WebReport.Usage(1,1,0,100,false),false,runId,null));
    }
}
