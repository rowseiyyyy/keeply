function safeParse(json, fallback) {
  try {
    const v = JSON.parse(json);
    return v === undefined ? fallback : v;
  } catch {
    return fallback;
  }
}

// Convert a DB row (snake_case, JSON-as-text) into the shape the frontend expects.
function serializeNote(row) {
  return {
    id: row.id,
    title: row.title,
    body: row.body,
    color: row.color,
    pinned: !!row.pinned,
    archived: !!row.archived,
    trashed: !!row.trashed,
    labels: safeParse(row.labels, []),
    images: safeParse(row.images, []),
    attachments: safeParse(row.attachments, []),
    collapsedSections: safeParse(row.collapsed_sections, []),
    position: row.position,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function serializeVersion(row) {
  return {
    id: row.id,
    title: row.title,
    body: row.body,
    timestamp: row.timestamp,
  };
}

// Mirrors the frontend's allLabelPaths(): every ancestor path of every label,
// each with a count of notes matching that path or any of its descendants.
function computeLabelTree(notes) {
  const allPaths = new Set();
  notes.forEach((n) => {
    (n.labels || []).forEach((l) => {
      const parts = l.split('/').filter(Boolean);
      let cur = '';
      parts.forEach((p) => {
        cur = cur ? `${cur}/${p}` : p;
        allPaths.add(cur);
      });
    });
  });
  const paths = Array.from(allPaths).sort();
  return paths.map((path) => ({
    path,
    name: path.split('/').filter(Boolean).pop(),
    depth: path.split('/').filter(Boolean).length - 1,
    count: notes.filter(
      (n) => (n.labels || []).some((l) => l === path || l.startsWith(path + '/'))
    ).length,
  }));
}

module.exports = { safeParse, serializeNote, serializeVersion, computeLabelTree };
