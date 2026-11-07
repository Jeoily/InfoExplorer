package com.infoexplorer.javaapi.research;

import java.time.Instant;

public record Evidence(String id, String url, String title, String excerpt,
                       Instant retrievedAt, String contentHash) {}
