package com.infoexplorer.javaapi.research;

public class ResearchException extends RuntimeException {
    public enum Reason { NOT_FOUND, INVALID_ID, INVALID_KEY, KEY_CONFLICT, INVALID_QUERY, INVALID_RETRY, RETRY_CONFLICT, RETRY_LIMIT }
    private final Reason reason;

    public ResearchException(Reason reason) {
        super(reason.name());
        this.reason = reason;
    }

    public Reason reason() { return reason; }
}
