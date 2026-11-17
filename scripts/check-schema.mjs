import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = new URL('../', import.meta.url);
const design = readFileSync(new URL('docs/04-database-design.md', root), 'utf8');
const ddl = [...design.matchAll(/```sql\r?\n([\s\S]*?)```/g)].map((match) => match[1]);
if (ddl.length === 0) throw new Error('No SQL blocks in database design');

// Roll back fixtures and schema, even on success. Use a disposable test database.
export const sql = [
  'BEGIN; CREATE SCHEMA compsphere_schema_regression;',
  'SET LOCAL search_path TO compsphere_schema_regression;',
  ...ddl,
  readFileSync(new URL('tests/schema_constraints.sql', root), 'utf8'),
  'ROLLBACK;',
].join('\n');

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = spawnSync('psql', ['-X', '--set=ON_ERROR_STOP=1', '--quiet'], {
    input: sql,
    encoding: 'utf8',
    env: { ...process.env, PGCLIENTENCODING: 'UTF8' },
  });
  if (result.error) throw result.error;
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);
  process.exitCode = result.status ?? 1;
}
