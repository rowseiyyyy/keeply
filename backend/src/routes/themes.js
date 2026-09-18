const express = require('express');
const { v4: uuid } = require('uuid');
const db = require('../db');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();
router.use(requireAuth);

function serialize(row) {
  return { id: row.id, name: row.name, bg: row.bg, a: row.a, b: row.b, c: row.c };
}

router.get('/', (req, res) => {
  const rows = db
    .prepare('SELECT * FROM custom_themes WHERE user_id = ? ORDER BY created_at ASC')
    .all(req.userId);
  res.json({ themes: rows.map(serialize) });
});

router.post('/', (req, res) => {
  const { name, bg, a, b, c } = req.body || {};
  if (!bg || !a || !b || !c) {
    return res.status(400).json({ error: 'bg, a, b and c colors are required' });
  }
  const id = `custom-${uuid()}`;
  db.prepare(
    'INSERT INTO custom_themes (id, user_id, name, bg, a, b, c, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).run(id, req.userId, name || 'Custom theme', bg, a, b, c, Date.now());
  res.status(201).json({ theme: { id, name: name || 'Custom theme', bg, a, b, c } });
});

router.delete('/:id', (req, res) => {
  const result = db
    .prepare('DELETE FROM custom_themes WHERE id = ? AND user_id = ?')
    .run(req.params.id, req.userId);
  if (result.changes === 0) return res.status(404).json({ error: 'Theme not found' });
  res.status(204).end();
});

module.exports = router;
