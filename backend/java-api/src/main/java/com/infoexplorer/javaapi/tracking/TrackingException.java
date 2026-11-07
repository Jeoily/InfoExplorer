package com.infoexplorer.javaapi.tracking;

public class TrackingException extends RuntimeException {
    private final String code;
    private final int status;
    public TrackingException(String code, int status) { super(code); this.code=code; this.status=status; }
    public String code() { return code; }
    public int status() { return status; }
}
