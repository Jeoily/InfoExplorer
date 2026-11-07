package com.infoexplorer.javaapi;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.context.ConfigurableApplicationContext;

/** Inherits the actual HTTP/worker/model/restart checks, using only a fresh owned MySQL schema. */
@EnabledIfEnvironmentVariable(named = "INFOEXPLORER_MYSQL_TEST", matches = "1")
@EnabledIfEnvironmentVariable(named = "INFOEXPLORER_TEST_AGENT_MODE", matches = "live-model")
@EnabledIfEnvironmentVariable(named = "INFOEXPLORER_TEST_AGENT_URL", matches = "http://127\\.0\\.0\\.1:[0-9]+")
class MySqlLiveModelIntegrationTests extends LiveModelIntegrationTests {
    private final MySqlIntegrationTests database = new MySqlIntegrationTests();

    @BeforeEach
    void createDatabase() throws Exception {
        try (var connection = database.admin(); var statement = connection.createStatement()) {
            statement.executeUpdate("CREATE DATABASE `" + database.schema
                    + "` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin");
            database.created = true;
        }
    }

    @AfterEach
    void removeOwnedDatabase() throws Exception {
        database.cleanup();
    }

    @Override
    ConfigurableApplicationContext open(boolean worker) {
        return new SpringApplicationBuilder(JavaApiApplication.class).run(
                "--spring.profiles.active=mysql", "--server.address=127.0.0.1", "--server.port=0",
                "--spring.datasource.url=" + database.url(database.schema),
                "--agent.service.base-url=" + System.getenv("INFOEXPLORER_TEST_AGENT_URL"),
                "--research.worker.enabled=" + worker, "--research.worker.poll-delay-ms=100",
                "--spring.main.banner-mode=off");
    }
}
