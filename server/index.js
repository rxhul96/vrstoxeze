import express from 'express';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createTask, deleteTask, listTasks, setTaskDone } from './db.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT) || 3001;

export const app = express();
app.use(express.json());

app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', time: new Date().toISOString() });
});

app.get('/api/tasks', (_req, res) => {
  res.json(listTasks());
});

app.post('/api/tasks', (req, res) => {
  const title = typeof req.body?.title === 'string' ? req.body.title.trim() : '';
  if (!title) {
    return res.status(400).json({ error: 'title is required' });
  }
  res.status(201).json(createTask(title));
});

app.patch('/api/tasks/:id', (req, res) => {
  const id = Number(req.params.id);
  if (!Number.isInteger(id)) {
    return res.status(400).json({ error: 'invalid id' });
  }
  const updated = setTaskDone(id, Boolean(req.body?.done));
  if (!updated) {
    return res.status(404).json({ error: 'task not found' });
  }
  res.json(updated);
});

app.delete('/api/tasks/:id', (req, res) => {
  const id = Number(req.params.id);
  if (!Number.isInteger(id)) {
    return res.status(400).json({ error: 'invalid id' });
  }
  if (!deleteTask(id)) {
    return res.status(404).json({ error: 'task not found' });
  }
  res.status(204).end();
});

// In production, serve the built client from ./client/dist.
const clientDist = join(__dirname, '..', 'client', 'dist');
if (existsSync(clientDist)) {
  app.use(express.static(clientDist));
  app.get('*', (_req, res) => {
    res.sendFile(join(clientDist, 'index.html'));
  });
}

// Only listen when run directly (not when imported by tests).
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  app.listen(PORT, () => {
    console.log(`[server] Task Board API listening on http://localhost:${PORT}`);
  });
}

export default app;
