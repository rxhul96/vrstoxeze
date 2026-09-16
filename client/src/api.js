const JSON_HEADERS = { 'Content-Type': 'application/json' };

async function handle(res) {
  if (!res.ok) {
    let detail = '';
    try {
      detail = (await res.json()).error ?? '';
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail || `Request failed with ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export const fetchTasks = () => fetch('/api/tasks').then(handle);

export const addTask = (title) =>
  fetch('/api/tasks', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ title }),
  }).then(handle);

export const updateTask = (id, done) =>
  fetch(`/api/tasks/${id}`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify({ done }),
  }).then(handle);

export const removeTask = (id) =>
  fetch(`/api/tasks/${id}`, { method: 'DELETE' }).then(handle);
