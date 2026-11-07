package com.infoexplorer.javaapi.controller;

import com.infoexplorer.javaapi.client.AgentException;
import com.infoexplorer.javaapi.research.ResearchException;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {
    public record ApiError(String code, String message) {}

    @ExceptionHandler(com.infoexplorer.javaapi.tracking.TrackingException.class)
    public ResponseEntity<ApiError> trackingFailure(com.infoexplorer.javaapi.tracking.TrackingException e) {
        return ResponseEntity.status(e.status()).body(new ApiError(e.code(),"Tracking operation could not be completed"));
    }

    @ExceptionHandler(ResearchException.class)
    public ResponseEntity<ApiError> researchFailure(ResearchException exception) {
        return switch (exception.reason()) {
            case NOT_FOUND -> ResponseEntity.status(404).body(new ApiError("TASK_NOT_FOUND", "Research task does not exist"));
            case INVALID_ID -> ResponseEntity.badRequest().body(new ApiError("INVALID_TASK_ID", "Task ID must be a UUID"));
            case INVALID_KEY -> ResponseEntity.badRequest().body(new ApiError("INVALID_IDEMPOTENCY_KEY", "Key must contain 1-128 letters, digits, dots, underscores, colons or hyphens"));
            case KEY_CONFLICT -> ResponseEntity.status(409).body(new ApiError("IDEMPOTENCY_CONFLICT", "This key was used with a different question"));
            case INVALID_RETRY -> ResponseEntity.badRequest().body(new ApiError("INVALID_RETRY", "Provide failedRunId as a UUID"));
            case RETRY_CONFLICT -> ResponseEntity.status(409).body(new ApiError("RETRY_CONFLICT", "Only the current failed execution can be retried"));
            case RETRY_LIMIT -> ResponseEntity.status(409).body(new ApiError("RETRY_LIMIT_EXCEEDED", "A task allows at most five executions"));
            case INVALID_QUERY -> ResponseEntity.badRequest().body(new ApiError("INVALID_QUERY", "Use page 0-10000, size 1-100, and optional status PENDING, RUNNING, SUCCEEDED or FAILED; each parameter may appear once"));
        };
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<ApiError> storageFailure(DataAccessException exception) {
        return ResponseEntity.status(503).body(new ApiError("STORAGE_UNAVAILABLE", "Task storage is unavailable"));
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, HttpMessageNotReadableException.class})
    public ResponseEntity<ApiError> invalidRequest(Exception exception) {
        return ResponseEntity.badRequest().body(new ApiError("INVALID_REQUEST",
                "Provide a non-blank question of at most 4000 UTF-16 code units in a JSON object"));
    }

    @ExceptionHandler(AgentException.class)
    public ResponseEntity<ApiError> agentFailure(AgentException exception) {
        return switch (exception.reason()) {
            case TIMEOUT -> ResponseEntity.status(504)
                    .body(new ApiError("AGENT_TIMEOUT", "Agent service timed out"));
            case UNAVAILABLE -> ResponseEntity.status(502)
                    .body(new ApiError("AGENT_UNAVAILABLE", "Agent service is unavailable"));
            case INVALID_RESPONSE -> ResponseEntity.status(502)
                    .body(new ApiError("AGENT_INVALID_RESPONSE", "Agent returned an invalid response"));
            case REJECTED -> ResponseEntity.status(502)
                    .body(new ApiError("AGENT_ERROR", "Agent could not complete the request"));
        };
    }
}
