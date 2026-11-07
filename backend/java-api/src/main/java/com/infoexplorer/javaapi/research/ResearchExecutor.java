package com.infoexplorer.javaapi.research;

import com.infoexplorer.javaapi.client.AgentClient;
import com.infoexplorer.javaapi.client.AgentException;
import com.infoexplorer.javaapi.client.WebAgentClient;
import com.infoexplorer.javaapi.dto.ResearchRequest;
import org.springframework.stereotype.Service;

@Service
public class ResearchExecutor {
    private final ResearchRepository repository;
    private final AgentClient agent;
    private final WebAgentClient webAgent;

    public ResearchExecutor(ResearchRepository repository, AgentClient agent, WebAgentClient webAgent) {
        this.repository = repository;
        this.agent = agent;
        this.webAgent = webAgent;
    }

    // Network I/O is deliberately outside database transactions.
    public boolean runNext() {
        var next = repository.claimNext();
        if (next.isEmpty()) { return false; }
        var claim = next.get();
        if ("web-model".equals(claim.researchMode())) {
            runSession(claim);
            return true;
        }
        if ("web".equals(claim.researchMode())) {
            runWeb(claim);
            return true;
        }
        ResearchReport response;
        try {
            response = webAgent.wikiControlled(claim.runId(),claim.question(),claim.language(),()->progress(claim));
            agent.validateControlled(response,new ResearchRequest(claim.question(),claim.language()));
        } catch (AgentException exception) {
            String code = switch (exception.reason()) {
                case TIMEOUT -> "AGENT_TIMEOUT";
                case UNAVAILABLE -> "AGENT_UNAVAILABLE";
                case INVALID_RESPONSE -> "AGENT_INVALID_RESPONSE";
                case REJECTED -> "AGENT_ERROR";
            };
            repository.fail(claim, exception.providerCode() == null ? code : exception.providerCode());
            return true;
        } catch (RuntimeException exception) {
            repository.fail(claim, "EXECUTION_FAILED");
            return true;
        }
        repository.succeed(claim, response);
        return true;
    }

    private void runWeb(ResearchRepository.Claim claim) {
        WebReport response;
        try { response=webAgent.researchControlled(claim.runId(),claim.question(),claim.language(),repository.resumeFrom(claim),()->progress(claim)); }
        catch(AgentException e) {
            String code=e.providerCode()!=null?e.providerCode():switch(e.reason()) {
                case TIMEOUT -> "AGENT_TIMEOUT";
                case UNAVAILABLE -> "AGENT_UNAVAILABLE";
                case INVALID_RESPONSE -> "AGENT_INVALID_RESPONSE";
                case REJECTED -> "AGENT_ERROR";
            };
            repository.fail(claim,code);
            return;
        }
        try { repository.finishWeb(claim,response); }
        catch(RuntimeException failure) {
            // The result transaction rolled back. Never repeat the external request.
            // If the DB is still unavailable, the worker logs safely; startup recovery owns it.
            repository.fail(claim,"RESULT_PERSISTENCE_FAILED");
        }
    }

    private void runSession(ResearchRepository.Claim claim) {
        ModelSessionReport response;
        try { response=webAgent.sessionControlled(claim.runId(),claim.question(),claim.language(),repository.resumeFrom(claim),()->progress(claim)); }
        catch(AgentException e) {
            String code=e.providerCode()!=null?e.providerCode():switch(e.reason()) {
                case TIMEOUT -> "AGENT_TIMEOUT";
                case UNAVAILABLE -> "AGENT_UNAVAILABLE";
                case INVALID_RESPONSE -> "AGENT_INVALID_RESPONSE";
                case REJECTED -> "AGENT_ERROR";
            };
            repository.fail(claim,code); return;
        }
        try { repository.finishSession(claim,response); }
        catch(RuntimeException e) { repository.fail(claim,"RESULT_PERSISTENCE_FAILED"); }
    }
    private void progress(ResearchRepository.Claim claim) {
        if(repository.cancelled(claim.runId())) webAgent.progress(claim.runId(),true);
        var p=webAgent.progress(claim.runId(),false);
        if(p!=null) repository.recordProgress(claim.runId(),p.stage(),p.reused());
    }
    public void cancelInterrupted() {
        for(String runId:repository.interruptedRunIds()) webAgent.progress(runId,true);
    }
}
