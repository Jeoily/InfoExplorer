package com.infoexplorer.javaapi.dto;

import java.util.List;

public record ChatResponse(
        String answer,
        List<String> sources
) {
}