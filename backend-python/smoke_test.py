import io
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:4100"
suffix = int(time.time() * 1000)
EMAIL = f"smoke-{suffix}@example.com"
PASSWORD = "password123"
token = None


def call(method, path, body=None, auth=False, raw=None, content_type=None, expect=None):
    global token
    headers = {}
    if auth:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if raw is not None:
        data = raw
        headers["Content-Type"] = content_type
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            code, text = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        code, text = e.code, e.read().decode()
    try:
        payload = json.loads(text) if text else None
    except json.JSONDecodeError:
        payload = text
    label = f"{method} {path}"
    if expect and code != expect:
        print(f"FAIL {label}: got {code}: {payload}")
        raise SystemExit(1)
    print(f"ok   {label} -> {code}")
    return code, payload


call("GET", "/api/health", expect=200)
_, reg = call("POST", "/api/auth/register", {"email": EMAIL, "password": PASSWORD}, expect=201)
token = reg["token"]
_, login = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD}, expect=200)
_, me = call("GET", "/api/auth/me", auth=True, expect=200)
assert me["user"]["email"] == EMAIL

call("GET", "/api/auth/me", expect=401)  # no token
call("POST", "/api/auth/register", {"email": EMAIL, "password": PASSWORD}, expect=409)  # duplicate

_, n1 = call("POST", "/api/notes", {"title": "First", "body": "Hello", "labels": ["Work/Projects"]}, auth=True, expect=201)
_, n2 = call("POST", "/api/notes", {"title": "Second", "body": "World"}, auth=True, expect=201)
note_id = n1["note"]["id"]

_, listed = call("GET", "/api/notes", auth=True, expect=200)
assert len(listed["notes"]) == 2, listed
_, filtered = call("GET", "/api/notes?search=hello", auth=True, expect=200)
assert len(filtered["notes"]) == 1
_, labeled = call("GET", "/api/notes?label=Work", auth=True, expect=200)
assert len(labeled["notes"]) == 1

call("GET", f"/api/notes/{note_id}", auth=True, expect=200)
call("PATCH", f"/api/notes/{note_id}", {"pinned": True, "color": "blue"}, auth=True, expect=200)
_, upd = call("PUT", f"/api/notes/{note_id}", {"title": "First v2", "body": "Hello 2"}, auth=True, expect=200)
_, vers = call("GET", f"/api/notes/{note_id}/versions", auth=True, expect=200)
assert len(vers["versions"]) == 1, vers
v_id = vers["versions"][0]["id"]
_, restored = call("POST", f"/api/notes/{note_id}/versions/{v_id}/restore", auth=True, expect=200)
assert restored["note"]["title"] == "First"

_, labels = call("GET", "/api/labels", auth=True, expect=200)
assert any(l["path"] == "Work" for l in labels["labels"]), labels
call("POST", "/api/labels/reparent", {"from": "Work", "to": "Personal"}, auth=True, expect=200)

call("POST", "/api/themes", {"name": "T", "bg": "#111", "a": "#222", "b": "#333", "c": "#444"}, auth=True, expect=201)
_, themes = call("GET", "/api/themes", auth=True, expect=200)
theme_id = themes["themes"][0]["id"]
call("DELETE", f"/api/themes/{theme_id}", auth=True, expect=204)

_, settings = call("GET", "/api/settings", auth=True, expect=200)
call("PUT", "/api/settings", {"view": "list", "splitView": True}, auth=True, expect=200)

png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
multipart = (
    b"--B\r\nContent-Disposition: form-data; name=\"file\"; filename=\"pic.png\"\r\n"
    b"Content-Type: image/png\r\n\r\n" + png + b"\r\n--B--\r\n"
)
code, up = call("POST", "/api/uploads", auth=True, raw=multipart,
                content_type="multipart/form-data; boundary=B", expect=201)
assert up["name"] == "pic.png"
with urllib.request.urlopen(BASE + up["url"]) as resp:
    assert resp.read() == png
print("ok   GET " + up["url"] + " -> 200 (file served)")

call("POST", "/api/notes/reorder", {"orderedIds": [note_id, n2["note"]["id"]]}, auth=True, expect=200)
call("DELETE", f"/api/notes/{n2['note']['id']}", auth=True, expect=204)

print("\nALL SMOKE TESTS PASSED")
