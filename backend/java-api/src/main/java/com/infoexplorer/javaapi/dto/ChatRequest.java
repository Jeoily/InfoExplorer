package com.infoexplorer.javaapi.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChatRequest(
        @NotBlank(message = "Question cannot be blank")
        @Size(max = 4000, message = "Question cannot exceed 4000 UTF-16 code units")
        String question
) {
}
