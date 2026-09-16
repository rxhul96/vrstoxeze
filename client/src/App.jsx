import { useEffect, useMemo, useState } from 'react';
import { addTask, fetchTasks, removeTask, updateTask } from './api.js';

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTasks()
      .then(setTasks)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const remaining = useMemo(() => tasks.filter((t) => !t.done).length, [tasks]);

  async function handleAdd(event) {
    event.preventDefault();
    const value = title.trim();
    if (!value) return;
    setError('');
    try {
      const created = await addTask(value);
      setTasks((prev) => [created, ...prev]);
      setTitle('');
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggle(task) {
    setError('');
    try {
      const updated = await updateTask(task.id, !task.done);
      setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRemove(task) {
    setError('');
    try {
      await removeTask(task.id);
      setTasks((prev) => prev.filter((t) => t.id !== task.id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app">
      <header className="app__header">
        <h1>Task Board</h1>
        <p className="app__subtitle">
          {loading
            ? 'Loading…'
            : `${remaining} open · ${tasks.length} total`}
        </p>
      </header>

      <form className="composer" onSubmit={handleAdd}>
        <input
          className="composer__input"
          type="text"
          placeholder="Add a new task…"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          aria-label="New task title"
        />
        <button className="composer__button" type="submit">
          Add
        </button>
      </form>

      {error && <p className="app__error" role="alert">{error}</p>}

      <ul className="tasks">
        {tasks.map((task) => (
          <li key={task.id} className={`task ${task.done ? 'task--done' : ''}`}>
            <label className="task__label">
              <input
                type="checkbox"
                checked={task.done}
                onChange={() => handleToggle(task)}
              />
              <span className="task__title">{task.title}</span>
            </label>
            <button
              className="task__delete"
              type="button"
              onClick={() => handleRemove(task)}
              aria-label={`Delete ${task.title}`}
            >
              ✕
            </button>
          </li>
        ))}
        {!loading && tasks.length === 0 && (
          <li className="tasks__empty">No tasks yet — add your first one above.</li>
        )}
      </ul>
    </main>
  );
}
