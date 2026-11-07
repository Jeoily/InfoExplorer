package com.infoexplorer.javaapi.client;

public class AgentException extends RuntimeException {
    public enum Reason { UNAVAILABLE, TIMEOUT, INVALID_RESPONSE, REJECTED }

    private final Reason reason;
    private final String providerCode;

    public AgentException(Reason reason, Throwable cause) {
        this(reason, cause, null);
    }

    public AgentException(Reason reason, Throwable cause, String providerCode) {
        super(reason.name(), cause);
        this.reason = reason;
        this.providerCode = providerCode;
    }

    public String providerCode() { return providerCode; }

    public Reason reason() {
        return reason;
    }
}
