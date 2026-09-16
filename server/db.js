import Database from 'better-sqlite3';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Persist the database under ./data (gitignored). Allow override for tests.
const DB_PATH =
  process.env.DB_PATH ?? join(__dirname, '..', 'data', 'tasks.sqlite');

if (DB_PATH !== ':memory:') {
  mkdirSync(dirname(DB_PATH), { recursive: true });
}

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
  );
`);

const rowToTask = (row) => ({
  id: row.id,
  title: row.title,
  done: Boolean(row.done),
  createdAt: row.created_at,
});

const statements = {
  all: db.prepare('SELECT * FROM tasks ORDER BY done ASC, id DESC'),
  get: db.prepare('SELECT * FROM tasks WHERE id = ?'),
  insert: db.prepare('INSERT INTO tasks (title) VALUES (?)'),
  setDone: db.prepare('UPDATE tasks SET done = ? WHERE id = ?'),
  delete: db.prepare('DELETE FROM tasks WHERE id = ?'),
};

export const listTasks = () => statements.all.all().map(rowToTask);

export const createTask = (title) => {
  const info = statements.insert.run(title);
  return rowToTask(statements.get.get(info.lastInsertRowid));
};

export const setTaskDone = (id, done) => {
  const result = statements.setDone.run(done ? 1 : 0, id);
  if (result.changes === 0) return null;
  return rowToTask(statements.get.get(id));
};

export const deleteTask = (id) => statements.delete.run(id).changes > 0;

export default db;
