"""
Indexing pipeline runner — streams SSE from /api/repo/{repo_id}/index-progress
and prints live progress to the terminal.
"""
import os, requests, json, sys
from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

BASE = "http://localhost:8000"
REPO_ID = "23fabf57-12cb-4428-b6e8-997bae5f540a"

client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
res = client.auth.sign_in_with_password({"email": "apitest@copilot.dev", "password": "Test@12345"})
TOKEN = res.session.access_token
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

print(f"\nOpening SSE stream for repo: {REPO_ID}")
print("Repo: https://github.com/djcode0718/InstagramCarouselSplitter")
print("="*60)

with requests.get(
    f"{BASE}/api/repo/{REPO_ID}/index-progress",
    headers=HEADERS,
    stream=True,
    timeout=600,
) as resp:
    for line in resp.iter_lines():
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                try:
                    event = json.loads(line[6:])
                    step = event.get("step", "")
                    msg  = event.get("message", "")
                    prog = event.get("progress", "")

                    if step == "done":
                        fc = event.get("file_count", "?")
                        nc = event.get("node_count", "?")
                        print(f"\n DONE! files={fc}  nodes={nc}  progress={prog}%")
                    elif step == "error":
                        print(f"\n ERROR: {msg}")
                    else:
                        print(f"  [{prog:>3}%] {step:<14} {msg}")

                    sys.stdout.flush()

                    if step in ("done", "error"):
                        break
                except json.JSONDecodeError:
                    print(f"  Raw: {line}")

print("="*60)
print("Pipeline complete.\n")
