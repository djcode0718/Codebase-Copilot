import sys, os, uuid, shutil
sys.path.insert(0, '.')
os.environ.setdefault('LLM_PROVIDER', 'groq')
os.environ.setdefault('GROQ_API_KEY', 'test-groq-key')
os.environ.setdefault('SUPABASE_URL', 'https://fake.supabase.co')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'fake-service-key')
os.environ.setdefault('OLLAMA_EMBED_MODEL', 'nomic-embed-text')
os.environ.setdefault('USE_FAST_LLM', 'false')
os.environ.setdefault('USE_COLBERT', 'false')

from app.config import REPOS_DIR
from api.services.repository_health_engine import RepositoryHealthEngine, _resolve_repos_dir

repo_name = 'debug-health-' + uuid.uuid4().hex[:6]
repo_path = os.path.join(REPOS_DIR, repo_name)
os.makedirs(os.path.join(repo_path, 'services'), exist_ok=True)

with open(os.path.join(repo_path, 'services', 'payments.py'), 'w') as f:
    f.write("API_KEY = 'hardcoded_super_secret_123456'\n")
    f.write("def charge(items):\n    return sum(items)\n")

print('REPOS_DIR:', REPOS_DIR)
print('_resolve_repos_dir():', _resolve_repos_dir())

engine = RepositoryHealthEngine()
print('engine._repos_dir:', engine._repos_dir)

result = engine.run(repo={'id': 'r1', 'name': repo_name, 'index_name': repo_name})
sec = next(c for c in result['categories'] if c['category'] == 'Security')
print('Security score:', sec['score'])
print('detected_problems:', sec['detected_problems'])
print('findings:', [(f['title'], f['finding_type']) for f in result['findings'][:5]])

shutil.rmtree(repo_path, ignore_errors=True)

