package com.infoexplorer.javaapi.client;

import com.infoexplorer.javaapi.research.WebReport;
import java.util.*;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;
import static org.junit.jupiter.api.Assertions.*;

class EvidenceCapacityTests {
    private final JsonMapper mapper = JsonMapper.builder().build();
    private final String run = UUID.randomUUID().toString();
    private WebReport report(int count) {
        String url="https://example.org/evidence", sid="S"+WebReportValidator.hash(url);
        var passages=new ArrayList<WebReport.Passage>();
        for(int i=0;i<count;i++) {
            String text="Distinct public evidence paragraph "+i, hash=WebReportValidator.hash(text);
            String key=WebReportValidator.hash(mapper.writeValueAsString(List.of(run,sid,i,0,hash)));
            passages.add(new WebReport.Passage("E"+(i+1),sid,i,0,text,hash,List.of("Q1"),1,false,key));
        }
        var candidate=new WebReport.Candidate(sid,url,url,"example.org","Source","",1,List.of("fixture"),null);
        var metadata=new WebReport.Metadata(url,url,"example.org","2026-10-25T00:00:00Z","text/html",1,"fixture",null,"unknown",false,WebReportValidator.hash("document"),"paragraph-json-v1");
        var outcome=new WebReport.Outcome("SUCCEEDED","COMPLETED","unknown","Answer [E1]",passages,
            List.of(new WebReport.Query("topic",0,"SUCCEEDED",List.of(sid),List.of(),null)),
            List.of(new WebReport.Source(candidate,"READ",null,metadata)),new WebReport.Usage(1,1,0,100,false),false,run,null);
        return new WebReport("web-research-v2","web-extract","en","direct",Map.of("Q1","topic"),outcome);
    }
    @Test void modelCapacityIsFourAndExtractRemainsTwo() {
        assertDoesNotThrow(()->WebReportValidator.validate(report(4),run,"topic","en",mapper,true));
        assertThrows(AgentException.class,()->WebReportValidator.validate(report(5),run,"topic","en",mapper,true));
        assertDoesNotThrow(()->WebReportValidator.validate(report(2),run,"topic","en",mapper));
        assertThrows(AgentException.class,()->WebReportValidator.validate(report(3),run,"topic","en",mapper));
    }
}
