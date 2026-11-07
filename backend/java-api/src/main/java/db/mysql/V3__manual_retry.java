package db.mysql;

import org.flywaydb.core.api.migration.BaseJavaMigration;
import org.flywaydb.core.api.migration.Context;
import com.infoexplorer.javaapi.migration.RetryMigration;

public class V3__manual_retry extends BaseJavaMigration {
    @Override public Integer getChecksum() { return 1; }
    @Override public void migrate(Context context) throws Exception { RetryMigration.migrate(context.getConnection(), true); }
}
