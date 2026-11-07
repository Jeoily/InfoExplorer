package com.infoexplorer.javaapi.service;

import com.infoexplorer.javaapi.client.AgentClient;
import com.infoexplorer.javaapi.dto.ChatRequest;
import com.infoexplorer.javaapi.dto.ChatResponse;
import org.springframework.stereotype.Service;

@Service
public class ChatService {
    private final AgentClient agentClient;

    public ChatService(AgentClient agentClient) {
        this.agentClient = agentClient;
    }

    public ChatResponse ask(ChatRequest request) {
        return agentClient.ask(request);
    }
}
