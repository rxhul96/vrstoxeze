# vrstoxeze — Task Board

A small full-stack demo application used to exercise the Cloud Agent development
environment end to end.

- **Backend:** [Express](https://expressjs.com/) REST API with a
  [better-sqlite3](https://github.com/WiseLibs/better-sqlite3) database.
- **Frontend:** [React](https://react.dev/) + [Vite](https://vitejs.dev/) single-page app.

## Requirements

- Node.js >= 22 (pinned in `package.json` `engines`)

## Getting started

```bash
npm install        # install dependencies
npm run dev        # start API (port 3001) + Vite dev server (port 5173)
```

Then open http://localhost:5173. The Vite dev server proxies `/api/*` requests
to the Express server on port 3001.

### Production-style run

```bash
npm run build      # build the client into client/dist
npm start          # Express serves the API and the built client on port 3001
```

## Testing

```bash
npm test           # runs the Node.js built-in test runner against the API
```

## API

| Method | Path              | Description               |
| ------ | ----------------- | ------------------------- |
| GET    | `/api/health`     | Health check              |
| GET    | `/api/tasks`      | List tasks                |
| POST   | `/api/tasks`      | Create a task (`{title}`) |
| PATCH  | `/api/tasks/:id`  | Toggle done (`{done}`)    |
| DELETE | `/api/tasks/:id`  | Delete a task             |

## Project layout

```
client/          React + Vite single-page app
  src/App.jsx    Task Board UI
server/          Express API
  index.js       Routes + static serving
  db.js          SQLite schema and queries
data/            SQLite database file (gitignored, created at runtime)
```
