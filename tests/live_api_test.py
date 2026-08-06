import os, requests, json
from dotenv import load_dotenv
load_dotenv("/Users/sj/Documents/AI-Copilot/codebase-copilot/.env")
from supabase import create_client

BASE = "http://localhost:8000"
url = os.getenv("SUPABASE_URL"); key = os.getenv("SUPABASE_SERVICE_KEY")
client = create_client(url, key)

# Get token
res = client.auth.sign_in_with_password({"email": "apitest@copilot.dev", "password": "Test@12345"})
TOKEN = res.session.access_token
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
USER_ID = res.user.id
print(f"Signed in as {USER_ID}\n")

PASS, FAIL = 0, 0
def check(label, resp, expected_status, check_fn=None):
    global PASS, FAIL
    status_ok = resp.status_code == expected_status
    body = None
    try:
        body = resp.json()
    except:
        body = resp.text
    body_ok = check_fn(body) if check_fn and status_ok else True
    ok = status_ok and body_ok
    symbol = "PASS" if ok else "FAIL"
    print(f"  [{symbol}] [{resp.status_code}] {label}")
    if not ok:
        print(f"         Expected {expected_status}, got {resp.status_code}: {str(body)[:200]}")
    if ok: PASS += 1
    else:  FAIL += 1
    return ok

print("═"*55)
print("  LIVE API ENDPOINT TEST")
print("═"*55)


def test_health():
    print("\n── Health ──────────────────────────────────────────────")
    r = requests.get(f"{BASE}/api/health")
    check("GET /api/health", r, 200, lambda b: b.get("status") == "ok")


def test_auth_guards():
    print("\n── Auth Guards (no token) ──────────────────────────────")
    r = requests.get(f"{BASE}/api/repo/list")
    check("GET /api/repo/list (no auth) → 401", r, 401)
    r = requests.post(f"{BASE}/api/repo/index", json={"source": "https://x.com"})
    check("POST /api/repo/index (no auth) → 401", r, 401)
    r = requests.post(f"{BASE}/api/chat/session", json={"repo_id": "x"})
    check("POST /api/chat/session (no auth) → 401", r, 401)


def test_input_validation():
    print("\n── Input Validation (422) ──────────────────────────────")
    r = requests.post(f"{BASE}/api/repo/index", headers=HEADERS, json={"source": ""})
    check("POST /api/repo/index (empty source) → 422", r, 422)
    r = requests.post(f"{BASE}/api/repo/index", headers=HEADERS, json={"source": "   "})
    check("POST /api/repo/index (whitespace) → 422", r, 422)
    r = requests.post(f"{BASE}/api/repo/index", headers=HEADERS, json={})
    check("POST /api/repo/index (missing field) → 422", r, 422)
    r = requests.post(f"{BASE}/api/chat/session", headers=HEADERS, json={})
    check("POST /api/chat/session (missing repo_id) → 422", r, 422)
    r = requests.post(f"{BASE}/api/eval/run", headers=HEADERS, json={"repo_id": "x"})
    check("POST /api/eval/run (missing index_name) → 422", r, 422)


def test_repo_crud():
    print("\n── Repository CRUD ─────────────────────────────────────")
    r = requests.get(f"{BASE}/api/repo/list", headers=HEADERS)
    check("GET /api/repo/list → 200", r, 200, lambda b: isinstance(b, list))
    initial_count = len(r.json()) if r.status_code == 200 else 0
    print(f"         (user has {initial_count} existing repos)")

    r = requests.post(f"{BASE}/api/repo/index", headers=HEADERS,
                      json={"source": "https://github.com/openai/whisper"})
    check("POST /api/repo/index (whisper.git) → 200", r, 200,
          lambda b: b.get("status") == "indexing" and b.get("index_name") == "whisper")
    repo_id = r.json().get("repo_id") if r.status_code == 200 else None

    r = requests.post(f"{BASE}/api/repo/index", headers=HEADERS,
                      json={"source": "https://github.com/openai/gpt-2.git"})
    check("POST /api/repo/index (.git suffix stripped) → 200", r, 200,
          lambda b: b.get("index_name") == "gpt-2")
    repo_id2 = r.json().get("repo_id") if r.status_code == 200 else None

    if repo_id:
        r = requests.get(f"{BASE}/api/repo/{repo_id}", headers=HEADERS)
        check("GET /api/repo/{id} → 200", r, 200,
              lambda b: b.get("id") == repo_id and b.get("status") == "indexing")

    r = requests.get(f"{BASE}/api/repo/00000000-0000-0000-0000-000000000000", headers=HEADERS)
    check("GET /api/repo/nonexistent → 404", r, 404)

    r = requests.get(f"{BASE}/api/repo/list", headers=HEADERS)
    new_count = len(r.json()) if r.status_code == 200 else 0
    check("GET /api/repo/list (count increased) → 200", r, 200,
          lambda b: len(b) == initial_count + 2)
    print(f"         (now {new_count} repos, was {initial_count})")

    return repo_id, repo_id2


def test_chat_endpoints(repo_id):
    print("\n── Chat Endpoints ──────────────────────────────────────")
    if repo_id:
        r = requests.post(f"{BASE}/api/chat/session", headers=HEADERS, json={"repo_id": repo_id})
        check("POST /api/chat/session (repo not ready → 400)", r, 400,
              lambda b: "not ready" in str(b.get("detail", "")).lower())

    r = requests.post(f"{BASE}/api/chat/session", headers=HEADERS, json={"repo_id": "non-existent"})
    check("POST /api/chat/session (missing repo → 404)", r, 404)

    if repo_id:
        r = requests.get(f"{BASE}/api/chat/list?repo_id={repo_id}", headers=HEADERS)
        check("GET /api/chat/list → 200 (empty)", r, 200, lambda b: b == [])

    r = requests.get(f"{BASE}/api/chat/00000000-0000-0000-0000-000000000000/messages", headers=HEADERS)
    check("GET /api/chat/nonexistent/messages → 404", r, 404)

    r = requests.post(f"{BASE}/api/chat/fake-id/message/stream", headers=HEADERS, json={"query": "   "})
    check("POST stream (empty query → 400)", r, 400)

    r = requests.delete(f"{BASE}/api/chat/00000000-0000-0000-0000-000000000000", headers=HEADERS)
    check("DELETE /api/chat/nonexistent → 404", r, 404)


def test_suggestions(repo_id):
    print("\n── Suggestions Endpoints ───────────────────────────────")
    r = requests.get(f"{BASE}/api/repo/00000000-0000-0000-0000-000000000000/suggestions", headers=HEADERS)
    check("GET /api/repo/nonexistent/suggestions → 404", r, 404)

    if repo_id:
        r = requests.get(f"{BASE}/api/repo/{repo_id}/suggestions", headers=HEADERS)
        check("GET /api/repo/{id}/suggestions (not ready → defaults)", r, 200,
              lambda b: "questions" in b and len(b["questions"]) == 6)


def test_eval(repo_id):
    print("\n── Eval Endpoints ──────────────────────────────────────")
    r = requests.get(f"{BASE}/api/eval/00000000-0000-0000-0000-000000000000/latest", headers=HEADERS)
    check("GET /api/eval/nonexistent/latest → 404", r, 404)

    if repo_id:
        r = requests.get(f"{BASE}/api/eval/{repo_id}/latest", headers=HEADERS)
        check("GET /api/eval/{id}/latest (new repo, no eval) → 200/null", r, 200, lambda b: b is None)

    r = requests.post(f"{BASE}/api/eval/run", headers=HEADERS, json={"repo_id": "bad", "index_name": "bad"})
    check("POST /api/eval/run (not found → 404)", r, 404)


def test_cleanup(repo_id, repo_id2):
    print("\n── Cleanup ─────────────────────────────────────────────")
    for rid in [repo_id, repo_id2]:
        if rid:
            r = requests.delete(f"{BASE}/api/repo/{rid}", headers=HEADERS)
            check(f"DELETE /api/repo/{rid[:8]}... → 200", r, 200)


# Run all tests
test_health()
test_auth_guards()
test_input_validation()
REPO_ID, REPO_ID2 = test_repo_crud()
test_chat_endpoints(REPO_ID)
test_suggestions(REPO_ID)
test_eval(REPO_ID)
test_cleanup(REPO_ID, REPO_ID2)

print(f"\n{'═'*55}")
print(f"  FINAL: {PASS} passed  |  {FAIL} failed  |  {PASS+FAIL} total")
print(f"{'═'*55}\n")
