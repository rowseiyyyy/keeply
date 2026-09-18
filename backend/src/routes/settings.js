const express = require('express');
const db = require('../db');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();
router.use(requireAuth);

function serialize(row) {
  return {
    view: row.view,
    sort: row.sort,
    density: row.density,
    theme: row.theme,
    tweak: row.tweak,
    splitView: !!row.split_view,
    workspace: JSON.parse(row.workspace || '[]'),
  };
}

router.get('/', (req, res) => {
  let row = db.prepare('SELECT * FROM user_settings WHERE user_id = ?').get(req.userId);
  if (!row) {
    db.prepare('INSERT INTO user_settings (user_id) VALUES (?)').run(req.userId);
    row = db.prepare('SELECT * FROM user_settings WHERE user_id = ?').get(req.userId);
  }
  res.json({ settings: serialize(row) });
});

router.put('/', (req, res) => {
  const b = req.body || {};
  const existing = db.prepare('SELECT * FROM user_settings WHERE user_id = ?').get(req.userId);
  if (!existing) db.prepare('INSERT INTO user_settings (user_id) VALUES (?)').run(req.userId);

  db.prepare(
    `UPDATE user_settings SET
      view = ?, sort = ?, density = ?, theme = ?, tweak = ?, split_view = ?, workspace = ?
     WHERE user_id = ?`
  ).run(
    b.view || existing?.view || 'grid',
    b.sort || existing?.sort || 'updated',
    b.density || existing?.density || 'comfortable',
    b.theme || existing?.theme || 'aurora',
    b.tweak || existing?.tweak || 'normal',
    b.splitView !== undefined ? (b.splitView ? 1 : 0) : existing?.split_view || 0,
    b.workspace !== undefined ? JSON.stringify(b.workspace) : existing?.workspace || '[]',
    req.userId
  );

  const row = db.prepare('SELECT * FROM user_settings WHERE user_id = ?').get(req.userId);
  res.json({ settings: serialize(row) });
});

module.exports = router;
