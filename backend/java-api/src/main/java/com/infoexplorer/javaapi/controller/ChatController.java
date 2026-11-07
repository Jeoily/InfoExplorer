package com.infoexplorer.javaapi.controller;

import com.infoexplorer.javaapi.dto.ChatRequest;
import com.infoexplorer.javaapi.dto.ChatResponse;
import com.infoexplorer.javaapi.service.ChatService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/chat")
public class ChatController {
    private final ChatService chatService;

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping("/ask")
    public ChatResponse ask(@Valid @RequestBody ChatRequest request) {

        return chatService.ask(request);
    }
}
