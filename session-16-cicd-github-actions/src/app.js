// Session 16 – CI/CD demo app (Express)
// Small "task tracker" API used to demonstrate a GitHub Actions CI/CD pipeline.
const express = require('express');

const APP_VERSION = process.env.APP_VERSION || '1.0.0';

function createApp() {
  const app = express();
  app.use(express.json());

  const tasks = [];
  let nextId = 1;

  app.get('/', (req, res) => {
    res.json({
      app: 'session16-cicd-demo',
      message: 'Hello from the Session 16 CI/CD pipeline!',
      author: 'Saniya Sanjiv Patil',
      version: APP_VERSION,
    });
  });

  app.get('/health', (req, res) => {
    res.json({ status: 'ok', uptime_s: Math.round(process.uptime()) });
  });

  app.get('/api/tasks', (req, res) => {
    res.json(tasks);
  });

  app.post('/api/tasks', (req, res) => {
    const title = req.body && req.body.title;
    if (typeof title !== 'string' || title.trim() === '') {
      return res.status(400).json({ error: 'title is required' });
    }
    const task = { id: nextId++, title: title.trim(), done: false };
    tasks.push(task);
    return res.status(201).json(task);
  });

  app.patch('/api/tasks/:id/done', (req, res) => {
    const task = tasks.find((t) => t.id === Number(req.params.id));
    if (!task) {
      return res.status(404).json({ error: 'task not found' });
    }
    task.done = true;
    return res.json(task);
  });

  app.get('/api/add', (req, res) => {
    const a = Number(req.query.a);
    const b = Number(req.query.b);
    if (Number.isNaN(a) || Number.isNaN(b)) {
      return res.status(400).json({ error: 'a and b must be numbers' });
    }
    return res.json({ a, b, result: a + b });
  });

  return app;
}

module.exports = { createApp, APP_VERSION };
