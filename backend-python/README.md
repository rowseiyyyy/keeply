# Keeply Backend — FastAPI

Python/FastAPI rewrite of the Express backend. **Drop-in replacement**: it uses the
same API routes, the same JWT auth, and reuses the existing SQLite database
(`backend/data/keeply.db`) and uploads folder (`backend/uploads`) — the Node backend
can be stopped and this started without any data migration.

## Setup

```powershell
cd backend-python
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Run

```powershell
.venv\Scripts\python -m uvicorn app.main:app --port 4000
```

Same env vars as the Node version (`PORT`, `JWT_SECRET`, `JWT_EXPIRES_IN`,
`CORS_ORIGIN`, `MAX_UPLOAD_BYTES`), loaded from `.env` via python-dotenv.
Optional: `DATA_DIR` / `UPLOAD_DIR` override the shared data locations.

Interactive API docs: http://localhost:4000/api/docs

## Verify

```powershell
.venv\Scripts\python smoke_test.py   # requires the server running on :4100
```

## Notes / differences from the Express version

- Request-body size limit: Express capped JSON bodies at 2 MB; FastAPI has no
  built-in equivalent. Uploads are still capped by `MAX_UPLOAD_BYTES` (15 MB).
- Password hashes: both use bcrypt, but hashes created by `bcryptjs` are read
  fine by Python's `bcrypt`, and vice versa — existing users can log in unchanged.
- Endpoints are sync `def`, so SQLite runs in FastAPI's threadpool with a
  connection per request (WAL mode, same as before).
