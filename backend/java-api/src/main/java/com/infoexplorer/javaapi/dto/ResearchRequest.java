package com.infoexplorer.javaapi.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import jakarta.validation.constraints.Pattern;

public record ResearchRequest(
        @NotBlank @Size(max=4000) String question,
        @Pattern(regexp="en|zh") String language,
        @Pattern(regexp="wikipedia|web|web-model") String researchMode) {
    public ResearchRequest {
        if (language == null) language = "en";
        if (researchMode == null) researchMode = "wikipedia";
    }
    public ResearchRequest(String question, String language) { this(question, language, "wikipedia"); }
    public ResearchRequest(String question) { this(question, "en"); }
}
