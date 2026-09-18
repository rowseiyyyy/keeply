# Keeply Backend

A REST API for **Keeply**, matching the note shape the existing frontend already uses
(`title`, `body`, `color`, `pinned`, `archived`, `trashed`, `labels`, `images`, `attachments`,
`collapsedSections`, version history) so it's a drop-in replacement for the current
`localStorage`-only version.

Stack: **Express** + **SQLite** (via `better-sqlite3`, a single file on disk — no separate
database server to run) + **JWT** auth + **multer** for file uploads.

## Setup

```bash
cd keeply-backend
npm install
cp .env.example .env   # then edit JWT_SECRET and CORS_ORIGIN
npm start               # or `npm run dev` for auto-reload
```

The API listens on `http://localhost:4000` by default. Data is stored in `data/keeply.db`
and uploaded files in `uploads/` — both are created automatically on first run.

## Auth

All endpoints except `/api/auth/register` and `/api/auth/login` require a header:

```
Authorization: Bearer <token>
```

The token is returned by register/login and expires per `JWT_EXPIRES_IN` (default 30 days).

| Method | Path                | Body                        | Notes                          |
|--------|---------------------|------------------------------|---------------------------------|
| POST   | `/api/auth/register`| `{ email, password }`        | password ≥ 8 chars              |
| POST   | `/api/auth/login`   | `{ email, password }`        |                                  |
| GET    | `/api/auth/me`      | —                             | current user from the token     |

## Notes

Note JSON shape (matches the frontend object exactly, aside from `id`/`position`):

```json
{
  "id": "uuid",
  "title": "string",
  "body": "markdown string",
  "color": "default | coral | amber | ...",
  "pinned": false,
  "archived": false,
  "trashed": false,
  "labels": ["Work/Projects"],
  "images": [{ "id": "img123", "src": "https://.../uploads/xyz.png", "position": "inline" }],
  "attachments": [{ "id": "att123", "name": "file.pdf", "size": 1234, "type": "application/pdf", "url": "/uploads/xyz.pdf" }],
  "collapsedSections": [2],
  "position": 0,
  "createdAt": 1690000000000,
  "updatedAt": 1690000000000
}
```

| Method | Path                                   | Notes                                                                 |
|--------|-----------------------------------------|------------------------------------------------------------------------|
| GET    | `/api/notes`                           | All notes for the user. Optional query params: `trashed`, `archived`, `label`, `search` |
| GET    | `/api/notes/:id`                       | Single note                                                            |
| POST   | `/api/notes`                           | Create a note                                                          |
| PUT    | `/api/notes/:id`                       | Full update — snapshots a version if title/body changed (used on "Done"/"Save") |
| PATCH  | `/api/notes/:id`                       | Partial update, no version snapshot (pin, color, archive, trash, checkbox toggles) |
| DELETE | `/api/notes/:id`                       | Permanently delete ("Delete forever")                                  |
| POST   | `/api/notes/reorder`                   | `{ orderedIds: [id, id, ...] }` — persists drag-and-drop custom order  |
| GET    | `/api/notes/:id/versions`              | Version history, newest first (capped at 20)                           |
| POST   | `/api/notes/:id/versions/:versionId/restore` | Restores a version's title/body onto the note                     |

## Labels

| Method | Path                     | Notes                                                                 |
|--------|--------------------------|------------------------------------------------------------------------|
| GET    | `/api/labels`           | `{ labels: [{ path, name, depth, count }] }` — includes implied parent paths, like the sidebar tree |
| POST   | `/api/labels/reparent`  | `{ from, to }` (`to: null` moves it to the root) — same drag-to-reparent behavior as the sidebar |

## Uploads

| Method | Path            | Notes                                                                 |
|--------|-----------------|------------------------------------------------------------------------|
| POST   | `/api/uploads`  | `multipart/form-data`, field name `file`. Returns `{ id, name, size, type, url }`. Files are served from `/uploads/<filename>`. |

This replaces storing images/attachments as base64 `dataUrl` strings — upload the file first,
then put the returned metadata straight into a note's `images` or `attachments` array.

## Themes & Settings

| Method | Path                | Notes                                                     |
|--------|---------------------|------------------------------------------------------------|
| GET    | `/api/themes`      | Custom themes created via the theme editor                 |
| POST   | `/api/themes`      | `{ name, bg, a, b, c }`                                     |
| DELETE | `/api/themes/:id`  |                                                              |
| GET    | `/api/settings`    | View/sort/density/theme/tweak/split-view/workspace prefs   |
| PUT    | `/api/settings`    | Partial update of the same fields                           |

## Wiring up the existing frontend

The frontend currently reads/writes everything through `localStorage` (`loadNotes`,
`saveNotes`, etc.). To point it at this API:

1. After login, store the JWT (e.g. in memory or `sessionStorage`) and send it as
   `Authorization: Bearer <token>` on every request.
2. Replace `loadNotes()` with `GET /api/notes` on page load.
3. Replace every `saveNotes()` call with the matching endpoint:
   - closing the composer → `POST /api/notes` (new) or `PUT /api/notes/:id` (edit)
   - pin/color/archive/trash/restore/checkbox toggle → `PATCH /api/notes/:id`
   - permanent delete → `DELETE /api/notes/:id`
   - drag-reorder → `POST /api/notes/reorder`
4. Replace the `FileReader` → base64 `dataUrl` flow for images/attachments with
   `POST /api/uploads`, and store the returned `url` instead of `dataUrl`.
5. Swap `loadCustomThemes()`/`saveCustomThemes()` for the `/api/themes` endpoints, and the
   various `localStorage.setItem('kp_*', …)` calls for `GET`/`PUT /api/settings`.

Happy to do this integration pass on the HTML file directly if you'd like — just say the word.
