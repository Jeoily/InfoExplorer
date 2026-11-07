package com.infoexplorer.javaapi;
import org.junit.jupiter.api.Test;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.builder.SpringApplicationBuilder;

class TrackingTests {
    @Test void changes() {
        try(var app=new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run("--spring.profiles.active=test")) {
            TrackingChecks.changes(app);
        }
    }
    @Test void lifecycle() throws Exception {
        try(var app=new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run("--spring.profiles.active=test")) {
            TrackingChecks.lifecycle(app);
        }
    }
    @Test void scheduling() {
        try(var app=new SpringApplicationBuilder(JavaApiApplication.class).web(WebApplicationType.NONE).run("--spring.profiles.active=test")) {
            TrackingChecks.scheduler(app);
        }
    }
}
