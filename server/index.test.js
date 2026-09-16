import assert from 'node:assert/strict';
import { after, test } from 'node:test';

// Use an in-memory database so tests never touch the real data file.
process.env.DB_PATH = ':memory:';

const { app } = await import('./index.js');

let server;
const base = await new Promise((resolve) => {
  server = app.listen(0, () => {
    const { port } = server.address();
    resolve(`http://localhost:${port}`);
  });
});

after(() => server.close());

test('health check responds ok', async () => {
  const res = await fetch(`${base}/api/health`);
  assert.equal(res.status, 200);
  assert.equal((await res.json()).status, 'ok');
});

test('tasks CRUD lifecycle', async () => {
  // Starts empty
  let res = await fetch(`${base}/api/tasks`);
  assert.deepEqual(await res.json(), []);

  // Create
  res = await fetch(`${base}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Write tests' }),
  });
  assert.equal(res.status, 201);
  const created = await res.json();
  assert.equal(created.title, 'Write tests');
  assert.equal(created.done, false);

  // Toggle done
  res = await fetch(`${base}/api/tasks/${created.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ done: true }),
  });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).done, true);

  // Delete
  res = await fetch(`${base}/api/tasks/${created.id}`, { method: 'DELETE' });
  assert.equal(res.status, 204);

  // Empty again
  res = await fetch(`${base}/api/tasks`);
  assert.deepEqual(await res.json(), []);
});

test('rejects empty title', async () => {
  const res = await fetch(`${base}/api/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: '   ' }),
  });
  assert.equal(res.status, 400);
});
