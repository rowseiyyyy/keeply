const express = require('express');
const { v4: uuid } = require('uuid');
const db = require('../db');
const { requireAuth } = require('../middleware/auth');
const { serializeNote, serializeVersion } = require('../utils/notes');

const router = express.Router();
router.use(requireAuth);

const MAX_VERSIONS = 20;

function getOwnedNote(noteId, userId) {
  return db.prepare('SELECT * FROM notes WHERE id = ? AND user_id = ?').get(noteId, userId);
}

// GET /api/notes — all of the user's notes (client filters into pinned/archive/trash/etc,
// mirroring the original localStorage-driven UI). Optional query params narrow server-side.
router.get('/', (req, res) => {
  const { trashed, archived, label, search } = req.query;
  let rows = db
    .prepare('SELECT * FROM notes WHERE user_id = ? ORDER BY position ASC, updated_at DESC')
    .all(req.userId);
  let notes = rows.map(serializeNote);

  if (trashed !== undefined) {
    const want = trashed === 'true' || trashed === '1';
    notes = notes.filter((n) => n.trashed === want);
  }
  if (archived !== undefined) {
    const want = archived === 'true' || archived === '1';
    notes = notes.filter((n) => n.archived === want);
  }
  if (label) {
    notes = notes.filter((n) => n.labels.some((l) => l === label || l.startsWith(label + '/')));
  }
  if (search) {
    const s = String(search).toLowerCase();
    notes = notes.filter(
      (n) =>
        n.title.toLowerCase().includes(s) ||
        n.body.toLowerCase().includes(s) ||
        n.labels.some((l) => l.toLowerCase().includes(s)) ||
        n.attachments.some((a) => (a.name || '').toLowerCase().includes(s))
    );
  }
  res.json({ notes });
});

router.get('/:id', (req, res) => {
  const row = getOwnedNote(req.params.id, req.userId);
  if (!row) return res.status(404).json({ error: 'Note not found' });
  res.json({ note: serializeNote(row) });
});

router.post('/', (req, res) => {
  const b = req.body || {};
  const id = uuid();
  const now = Date.now();
  const maxPos = db
    .prepare('SELECT COALESCE(MIN(position), 0) - 1 AS p FROM notes WHERE user_id = ?')
    .get(req.userId).p;

  db.prepare(
    `INSERT INTO notes
      (id, user_id, title, body, color, pinned, archived, trashed, labels, images, attachments, collapsed_sections, position, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?)`
  ).run(
    id,
    req.userId,
    b.title || '',
    b.body || '',
    b.color || 'default',
    b.pinned ? 1 : 0,
    JSON.stringify(b.labels || []),
    JSON.stringify(b.images || []),
    JSON.stringify(b.attachments || []),
    JSON.stringify(b.collapsedSections || []),
    maxPos,
    now,
    now
  );

  const row = getOwnedNote(id, req.userId);
  res.status(201).json({ note: serializeNote(row) });
});

// Full update — used when the editor closes ("Done"/"Save"). Records a version
// snapshot first if the title or body actually changed, same as the client used to.
router.put('/:id', (req, res) => {
  const existing = getOwnedNote(req.params.id, req.userId);
  if (!existing) return res.status(404).json({ error: 'Note not found' });
  const b = req.body || {};
  const now = Date.now();

  const newTitle = b.title !== undefined ? b.title : existing.title;
  const newBody = b.body !== undefined ? b.body : existing.body;

  if (newTitle !== existing.title || newBody !== existing.body) {
    db.prepare(
      'INSERT INTO note_versions (id, note_id, title, body, timestamp) VALUES (?, ?, ?, ?, ?)'
    ).run(uuid(), existing.id, existing.title, existing.body, existing.updated_at);
    const excess = db
      .prepare('SELECT id FROM note_versions WHERE note_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET ?')
      .all(existing.id, MAX_VERSIONS);
    if (excess.length) {
      const ids = excess.map((r) => r.id);
      db.prepare(`DELETE FROM note_versions WHERE id IN (${ids.map(() => '?').join(',')})`).run(...ids);
    }
  }

  db.prepare(
    `UPDATE notes SET
      title = ?, body = ?, color = ?, pinned = ?, archived = ?, trashed = ?,
      labels = ?, images = ?, attachments = ?, collapsed_sections = ?, updated_at = ?
     WHERE id = ? AND user_id = ?`
  ).run(
    newTitle,
    newBody,
    b.color !== undefined ? b.color : existing.color,
    b.pinned !== undefined ? (b.pinned ? 1 : 0) : existing.pinned,
    b.archived !== undefined ? (b.archived ? 1 : 0) : existing.archived,
    b.trashed !== undefined ? (b.trashed ? 1 : 0) : existing.trashed,
    b.labels !== undefined ? JSON.stringify(b.labels) : existing.labels,
    b.images !== undefined ? JSON.stringify(b.images) : existing.images,
    b.attachments !== undefined ? JSON.stringify(b.attachments) : existing.attachments,
    b.collapsedSections !== undefined ? JSON.stringify(b.collapsedSections) : existing.collapsed_sections,
    now,
    existing.id,
    req.userId
  );

  res.json({ note: serializeNote(getOwnedNote(existing.id, req.userId)) });
});

// Partial update — used for quick actions (pin, color, archive, trash, restore,
// checkbox toggles, section collapse) that shouldn't create a version snapshot.
router.patch('/:id', (req, res) => {
  const existing = getOwnedNote(req.params.id, req.userId);
  if (!existing) return res.status(404).json({ error: 'Note not found' });
  const b = req.body || {};

  const fieldMap = {
    title: 'title',
    body: 'body',
    color: 'color',
    pinned: 'pinned',
    archived: 'archived',
    trashed: 'trashed',
    labels: 'labels',
    images: 'images',
    attachments: 'attachments',
    collapsedSections: 'collapsed_sections',
  };
  const sets = [];
  const values = [];
  for (const [key, column] of Object.entries(fieldMap)) {
    if (b[key] === undefined) continue;
    sets.push(`${column} = ?`);
    if (['pinned', 'archived', 'trashed'].includes(key)) values.push(b[key] ? 1 : 0);
    else if (['labels', 'images', 'attachments', 'collapsedSections'].includes(key))
      values.push(JSON.stringify(b[key]));
    else values.push(b[key]);
  }
  if (!sets.length) return res.json({ note: serializeNote(existing) });

  sets.push('updated_at = ?');
  values.push(Date.now());
  values.push(existing.id, req.userId);

  db.prepare(`UPDATE notes SET ${sets.join(', ')} WHERE id = ? AND user_id = ?`).run(...values);
  res.json({ note: serializeNote(getOwnedNote(existing.id, req.userId)) });
});

router.delete('/:id', (req, res) => {
  const existing = getOwnedNote(req.params.id, req.userId);
  if (!existing) return res.status(404).json({ error: 'Note not found' });
  db.prepare('DELETE FROM notes WHERE id = ? AND user_id = ?').run(existing.id, req.userId);
  res.status(204).end();
});

// POST /api/notes/reorder { orderedIds: [id, id, ...] } — persists drag-and-drop order.
router.post('/reorder', (req, res) => {
  const { orderedIds } = req.body || {};
  if (!Array.isArray(orderedIds)) {
    return res.status(400).json({ error: 'orderedIds must be an array of note ids' });
  }
  const update = db.prepare('UPDATE notes SET position = ? WHERE id = ? AND user_id = ?');
  const tx = db.transaction((ids) => {
    ids.forEach((id, index) => update.run(index, id, req.userId));
  });
  tx(orderedIds);
  res.json({ ok: true });
});

router.get('/:id/versions', (req, res) => {
  const existing = getOwnedNote(req.params.id, req.userId);
  if (!existing) return res.status(404).json({ error: 'Note not found' });
  const rows = db
    .prepare('SELECT * FROM note_versions WHERE note_id = ? ORDER BY timestamp DESC')
    .all(existing.id);
  res.json({ versions: rows.map(serializeVersion) });
});

router.post('/:id/versions/:versionId/restore', (req, res) => {
  const existing = getOwnedNote(req.params.id, req.userId);
  if (!existing) return res.status(404).json({ error: 'Note not found' });
  const version = db
    .prepare('SELECT * FROM note_versions WHERE id = ? AND note_id = ?')
    .get(req.params.versionId, existing.id);
  if (!version) return res.status(404).json({ error: 'Version not found' });

  db.prepare(
    'INSERT INTO note_versions (id, note_id, title, body, timestamp) VALUES (?, ?, ?, ?, ?)'
  ).run(uuid(), existing.id, existing.title, existing.body, existing.updated_at);

  db.prepare('UPDATE notes SET title = ?, body = ?, updated_at = ? WHERE id = ? AND user_id = ?').run(
    version.title,
    version.body,
    Date.now(),
    existing.id,
    req.userId
  );

  res.json({ note: serializeNote(getOwnedNote(existing.id, req.userId)) });
});

module.exports = router;
