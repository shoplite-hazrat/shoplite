// Runs database migrations, then exits. In Kubernetes this runs as a separate
// Job before the new version rolls out, never inside the app's startup: with
// several replicas starting at once, each one would race to migrate.
import { fileURLToPath } from 'node:url';
import { runner } from 'node-pg-migrate';

const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  console.error('Missing required environment variable DATABASE_URL');
  process.exit(1);
}

try {
  const applied = await runner({
    databaseUrl,
    dir: fileURLToPath(new URL('../migrations', import.meta.url)),
    direction: 'up',
    migrationsTable: 'pgmigrations',
    // Advisory lock: if two migrators run anyway, the second one waits.
    noLock: false,
    log: (msg) => console.log(JSON.stringify({ level: 'info', msg })),
  });
  console.log(JSON.stringify({ level: 'info', msg: 'migrations complete', applied: applied.map((m) => m.name) }));
} catch (err) {
  console.error(JSON.stringify({ level: 'error', msg: 'migration failed', err: err.message }));
  process.exit(1);
}
