const express = require('express');
const db = require('../db');
const { requireAuth } = require('../middleware/auth');
const { serializeNote, computeLabelTree } = require('../utils/notes');

const router = express.Router();
router.use(requireAuth);

function activeNotesFor(userId) {
  return db
    .prepare('SELECT * FROM notes WHERE user_id = ? AND trashed = 0')
    .all(userId)
    .map(serializeNote);
}

// GET /api/labels — every label path (including implied parent paths) with a note count,
// mirroring the frontend's sidebar label tree.
router.get('/', (req, res) => {
  res.json({ labels: computeLabelTree(activeNotesFor(req.userId)) });
});

// POST /api/labels/reparent { from: "Work/Old", to: "Personal" | null }
// Renames/moves a label path across every note that uses it or a sub-label of it.
router.post('/reparent', (req, res) => {
  const { from, to } = req.body || {};
  if (!from) return res.status(400).json({ error: 'from is required' });
  if (to && (to === from || to.startsWith(from + '/'))) {
    return res.status(400).json({ error: 'Cannot move a label into its own descendant' });
  }

  const lastSegment = from.split('/').filter(Boolean).pop();
  const newPrefix = to ? `${to}/${lastSegment}` : lastSegment;
  if (newPrefix === from) return res.json({ ok: true, newPath: newPrefix });

  const rows = db.prepare('SELECT * FROM notes WHERE user_id = ? AND trashed = 0').all(req.userId);
  const update = db.prepare('UPDATE notes SET labels = ?, updated_at = ? WHERE id = ?');
  const tx = db.transaction(() => {
    rows.forEach((row) => {
      let labels;
      try {
        labels = JSON.parse(row.labels);
      } catch {
        labels = [];
      }
      let changed = false;
      const next = labels.map((l) => {
        if (l === from) {
          changed = true;
          return newPrefix;
        }
        if (l.startsWith(from + '/')) {
          changed = true;
          return newPrefix + l.slice(from.length);
        }
        return l;
      });
      if (changed) update.run(JSON.stringify(next), Date.now(), row.id);
    });
  });
  tx();

  res.json({ ok: true, newPath: newPrefix });
});

module.exports = router;
