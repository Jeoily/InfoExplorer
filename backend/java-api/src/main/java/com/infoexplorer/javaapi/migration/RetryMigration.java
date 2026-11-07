package com.infoexplorer.javaapi.migration;

import java.sql.Connection;
import java.sql.SQLException;

/** Shared by new vendor-specific Flyway versions; old migrations remain immutable. */
public final class RetryMigration {
    private RetryMigration() {}
    public static void migrate(Connection connection, boolean mysql) throws SQLException {
        String schema = mysql ? connection.getCatalog() : connection.getSchema();
        String table = mysql ? "research_run" : "RESEARCH_RUN";
        String column = mysql ? "task_id" : "TASK_ID";
        String constraint;
        // H2 assigns an installation-specific name to the old inline UNIQUE constraint.
        try (var query = connection.prepareStatement("""
                SELECT tc.CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k
                ON tc.CONSTRAINT_SCHEMA=k.CONSTRAINT_SCHEMA AND tc.CONSTRAINT_NAME=k.CONSTRAINT_NAME
                  AND tc.TABLE_NAME=k.TABLE_NAME
                WHERE tc.TABLE_SCHEMA=? AND tc.TABLE_NAME=? AND tc.CONSTRAINT_TYPE='UNIQUE'
                GROUP BY tc.CONSTRAINT_NAME HAVING COUNT(*)=1 AND MAX(k.COLUMN_NAME)=?
                """)) {
            query.setString(1, schema); query.setString(2, table); query.setString(3, column);
            try (var rows = query.executeQuery()) {
                if (!rows.next()) { throw new SQLException("Expected one legacy run uniqueness constraint"); }
                constraint = rows.getString(1);
                if (rows.next() || !constraint.matches("[A-Za-z0-9_]+")) {
                    throw new SQLException("Unexpected legacy run constraint metadata");
                }
            }
        }
        try (var statement = connection.createStatement()) {
            if (!mysql) {
                // H2 may reuse the old unique index for this FK and retain it after DROP UNIQUE.
                // Remove/recreate only the run->task FK so the obsolete unique index is released.
                String foreignKey;
                try (var query = connection.prepareStatement("SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=? AND TABLE_NAME='RESEARCH_RUN' AND CONSTRAINT_TYPE='FOREIGN KEY'")) {
                    query.setString(1, schema);
                    try (var rows = query.executeQuery()) {
                        if (!rows.next()) { throw new SQLException("Expected legacy run foreign key"); }
                        foreignKey = rows.getString(1);
                        if (rows.next() || !foreignKey.matches("[A-Za-z0-9_]+")) { throw new SQLException("Unexpected run foreign key metadata"); }
                    }
                }
                statement.executeUpdate("ALTER TABLE research_run DROP CONSTRAINT \"" + foreignKey + "\"");
            }
            statement.executeUpdate("ALTER TABLE research_task ADD COLUMN attempt_no INTEGER NOT NULL DEFAULT 1 CHECK (attempt_no BETWEEN 1 AND 5)");
            statement.executeUpdate("ALTER TABLE research_run ADD COLUMN attempt_no INTEGER NOT NULL DEFAULT 1 CHECK (attempt_no BETWEEN 1 AND 5)");
            statement.executeUpdate("ALTER TABLE research_run ADD COLUMN retry_accepted BOOLEAN NOT NULL DEFAULT FALSE");
            // The replacement index also supports the MySQL task foreign key before the old index is removed.
            statement.executeUpdate("ALTER TABLE research_run ADD CONSTRAINT uq_run_attempt UNIQUE(task_id, attempt_no)");
            statement.executeUpdate("ALTER TABLE research_run " + (mysql ? "DROP INDEX `" + constraint + "`"
                    : "DROP CONSTRAINT \"" + constraint + "\""));
            if (!mysql) { statement.executeUpdate("ALTER TABLE research_run ADD CONSTRAINT fk_run_task FOREIGN KEY(task_id) REFERENCES research_task(id)"); }
        }
    }
}
