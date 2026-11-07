package com.infoexplorer.javaapi.client;

import com.infoexplorer.javaapi.research.*;
import java.util.*;
import tools.jackson.databind.DeserializationFeature;
import tools.jackson.databind.json.JsonMapper;
import static com.infoexplorer.javaapi.client.WebReportValidator.*;

/** Cross-field validation, including the evidence set that the reviewer actually saw. */
public final class ModelSessionValidator {
    private ModelSessionValidator() {}
    public record ReviewItem(String questionId,String state,List<String> evidenceIds) {}
    public record Review(List<ReviewItem> coverage,List<String> extraQueries) {}
    public record Snapshot(int round,List<WebReport.Passage> evidence,Review decision) {}
    private static final Set<String> TERMINAL=Set.of("MODEL_AUTH_ERROR","MODEL_CONFIG_ERROR","MODEL_BUSY",
        "MODEL_INPUT_TOO_LARGE","EXECUTION_DEADLINE","EXECUTION_BUDGET_EXHAUSTED","EXECUTION_CANCELLED");
    private static boolean code(String s) { return s!=null && s.matches("[A-Z][A-Z0-9_]{0,79}"); }
    private static void strings(List<String> xs,int min,int max,int length) {
        require(xs!=null && xs.size()>=min && xs.size()<=max && xs.stream().allMatch(x->text(x,length)));
        require(xs.stream().map(x->x.toLowerCase(Locale.ROOT)).distinct().count()==xs.size());
    }
    private static void refs(List<String> xs,Set<String> ids,int min) {
        require(xs!=null && xs.size()>=min && xs.size()<=8 && new HashSet<>(xs).size()==xs.size() && ids.containsAll(xs));
    }
    public static void validate(ModelSessionReport r,String runId,String question,String language,JsonMapper mapper) {
        try {
            require(r!=null && "web-research-v3".equals(r.schemaVersion()) && "web-model".equals(r.mode()) && language.equals(r.language()));
            var s=r.session();
            require(s!=null && Set.of("web-model-session-v1","web-model-session-v2").contains(s.version()) && runId.equals(s.runId())
                && Set.of("model","direct").contains(s.planMode()) && code(s.stopReason()));
            var u=s.usage();
            boolean audited="web-model-session-v2".equals(s.version());
            require(u!=null && u.searches()>=0 && u.searches()<=5 && u.documents()>=0 && u.documents()<=8
                && u.modelCalls()>=0 && u.modelCalls()<=(audited?4:3) && Double.isFinite(u.remainingSeconds()) && u.remainingSeconds()>=0 && u.remainingSeconds()<=150);
            require(s.events()!=null && s.events().size()<=u.modelCalls());
            int previous=-1;
            Set<String> succeeded=new HashSet<>();
            for(var e:s.events()) {
                int index=(audited?List.of("plan","review","report","verify"):List.of("plan","review","report")).indexOf(e.stage());
                require(index>previous && e.inputHash()!=null && e.inputHash().matches("[a-f0-9]{64}")); previous=index;
                require(Set.of("SUCCEEDED","FAILED").contains(e.status()));
                require("SUCCEEDED".equals(e.status())?e.code()==null:code(e.code()));
                if("SUCCEEDED".equals(e.status())) succeeded.add(e.stage());
            }
            Map<String,String> questions=new LinkedHashMap<>();
            List<String> initial;
            if(s.plan()!=null) {
                require("model".equals(s.planMode()) && s.planReason()==null && succeeded.contains("plan"));
                var p=s.plan(); require(text(p.scope(),500) && p.questions()!=null && !p.questions().isEmpty() && p.questions().size()<=8);
                for(var q:p.questions()) require(q.id()!=null && q.id().matches("Q[1-8]") && text(q.question(),500)
                    && text(q.evidenceNeed(),300) && questions.put(q.id(),q.question())==null);
                strings(p.queries(),1,3,200); initial=p.queries();
            } else {
                questions.put("Q1",question.strip().replaceAll("(?U)\\s+"," "));
                initial=List.of(questions.get("Q1"));
                require(!succeeded.contains("plan"));
                if("direct".equals(s.planMode())) require(code(s.planReason()));
            }
            var o=s.outcome();
            if(o==null) {
                require(TERMINAL.contains(s.stopReason()) && u.searches()==0 && u.documents()==0
                    && s.decision()==null && s.report()==null && !succeeded.contains("review") && !succeeded.contains("report"));
                return;
            }
            require(s.plan()!=null || "direct".equals(s.planMode()));
            validateOutcome(o,questions,runId,question,language,mapper);
            require(u.searches()==o.usage().searches() && u.documents()==o.usage().documents()
                && u.modelCalls()==o.usage().modelCalls() && u.cancelled()==o.usage().cancelled()
                && u.remainingSeconds()<=o.usage().remainingSeconds());
            Set<String> finalIds=new HashSet<>(); o.evidence().forEach(e->finalIds.add(e.evidenceId()));
            var d=s.decision();
            require((d!=null)==succeeded.contains("review"));
            boolean hasSnapshot=o.reviewSnapshot()!=null && !o.reviewSnapshot().isNull();
            require((d!=null)==hasSnapshot && (d!=null)==o.reviewApplied());
            if("sufficient".equals(o.coverage())) require(d!=null && "finish".equals(d.action())
                && d.coverage()!=null && d.coverage().stream().allMatch(c->"covered".equals(c.state())));
            if(d!=null) {
                require(Set.of("finish","supplement").contains(d.action()) && text(d.reason(),500));
                var snapshot=mapper.readerFor(Snapshot.class).with(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                    .with(DeserializationFeature.FAIL_ON_MISSING_CREATOR_PROPERTIES).with(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES)
                    .without(DeserializationFeature.ACCEPT_FLOAT_AS_INT).readValue(o.reviewSnapshot().toString());
                Snapshot snap=(Snapshot)snapshot;
                require(snap.round()==0 && snap.decision()!=null);
                // Validate initial evidence identity and source bindings even if supplementation replaced it.
                var original=new WebReport.Outcome("SUCCEEDED",snap.evidence().isEmpty()?"NO_USABLE_EVIDENCE":"COMPLETED","partial","Evidence snapshot",snap.evidence(),
                    o.queries(),o.sources(),o.usage(),false,runId,null);
                validateOutcome(original,questions,runId,question,language,mapper);
                Map<String,WebReport.Passage> initialEvidence=new HashMap<>(); snap.evidence().forEach(e->initialEvidence.put(e.evidenceId(),e));
                for(var e:o.evidence()) if(initialEvidence.containsKey(e.evidenceId())) require(initialEvidence.get(e.evidenceId()).equals(e));
                require(d.coverage()!=null && d.coverage().size()==questions.size());
                Set<String> qids=new HashSet<>(); List<ReviewItem> expected=new ArrayList<>();
                for(var c:d.coverage()) {
                    require(questions.containsKey(c.questionId()) && qids.add(c.questionId()) && Set.of("covered","partial","missing").contains(c.state()));
                    refs(c.evidenceIds(),initialEvidence.keySet(),"missing".equals(c.state())?0:1);
                    require(c.gap()!=null && c.gap().length()<=500 && ("covered".equals(c.state()) || text(c.gap(),500)));
                    expected.add(new ReviewItem(c.questionId(),c.state(),c.evidenceIds()));
                }
                boolean all=d.coverage().stream().allMatch(c->"covered".equals(c.state()));
                strings(d.queries(),"supplement".equals(d.action())?1:0,"supplement".equals(d.action())?2:0,200);
                require(!"supplement".equals(d.action()) || !all);
                require(d.queries().stream().noneMatch(q->initial.stream().anyMatch(i->i.equalsIgnoreCase(q))));
                require(expected.equals(snap.decision().coverage()) && d.queries().equals(snap.decision().extraQueries()));
                if("SUCCEEDED".equals(o.status()) && "COMPLETED".equals(o.completionReason()))
                    require(s.stopReason().equals("supplement".equals(d.action())?"SUPPLEMENT_ROUND_LIMIT":all?"EVIDENCE_SUFFICIENT":"NO_PRODUCTIVE_SEARCH"));
                if("supplement".equals(d.action())) require(!"sufficient".equals(o.coverage()));
            }
            Set<String> queries=new HashSet<>(); int lastRound=0;
            for(var q:o.queries()) {
                require(queries.add(q.query().toLowerCase(Locale.ROOT)) && q.round()>=lastRound); lastRound=q.round();
                require(q.round()==0?initial.contains(q.query()):d!=null && "supplement".equals(d.action()) && d.queries().contains(q.query()));
            }
            require((s.report()!=null)==succeeded.contains(audited?"verify":"report"));
            if(succeeded.contains("verify")) require(succeeded.contains("report"));
            if("FAILED".equals(o.status()) || !"COMPLETED".equals(o.completionReason())) require(s.stopReason().equals(o.completionReason()));
            if(s.report()!=null) {
                var report=s.report(); require(report.claims()!=null && report.claims().size()<=12);
                require(report.limitations()!=null && !report.limitations().isEmpty() && report.limitations().size()<=8);
                List<String> lines=new ArrayList<>();
                for(var c:report.claims()) {
                    require(Set.of("source_statement","inference").contains(c.kind()) && text(c.text(),1000));
                    String text=("inference".equals(c.kind())?"推断：":"")+c.text();
                    require(text(text,1000) && !text.matches("(?s).*\\[E[0-9]+\\].*")); refs(c.evidenceIds(),finalIds,1);
                    lines.add(text+" "+String.join("",c.evidenceIds().stream().map(id->"["+id+"]").toList()));
                }
                for(String limit:report.limitations()) {
                    require(text(limit,500) && !limit.matches("(?s).*\\[E[0-9]+\\].*")); lines.add("限制："+limit);
                }
                if("SUCCEEDED".equals(o.status())) require(String.join("\n\n",lines).equals(o.answer()));
            } else require(!"COMPLETED".equals(o.completionReason()));
        } catch(Exception e) { throw new AgentException(AgentException.Reason.INVALID_RESPONSE,e); }
    }
    private static void validateOutcome(WebReport.Outcome o,Map<String,String> qs,String id,String q,String lang,JsonMapper mapper) {
        WebReportValidator.validate(new WebReport("web-research-v3","web-model",lang,"model",qs,o),id,q,lang,mapper,true);
    }
}
