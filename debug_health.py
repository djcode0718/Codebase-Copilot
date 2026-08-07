import os
import shutil
import sys
import uuid

sys.path.insert(0, '.')


def _set_debug_env_defaults() -> None:
    os.environ.setdefault('LLM_PROVIDER', 'groq')
    # Keep test key values clearly non-secret and scanner-safe.
    os.environ.setdefault('GROQ_API_KEY', 'debug-placeholder-key')
    os.environ.setdefault('SUPABASE_URL', 'https://example.supabase.co')
    os.environ.setdefault('SUPABASE_SERVICE_KEY', 'debug-placeholder-service-key')
    os.environ.setdefault('OLLAMA_EMBED_MODEL', 'nomic-embed-text')
    os.environ.setdefault('USE_FAST_LLM', 'false')
    os.environ.setdefault('USE_COLBERT', 'false')


def _create_sample_service(repo_path: str) -> None:
    sample_key_var = 'debug_token'
    with open(os.path.join(repo_path, 'services', 'payments.py'), 'w', encoding='utf-8') as f:
        f.write(f"TEST_CREDENTIAL = '{sample_key_var}'\n")
        f.write('def charge(items):\n')
        f.write('    return sum(items)\n')


_set_debug_env_defaults()

from app.config import REPOS_DIR
from api.services.repository_health_engine import RepositoryHealthEngine, _resolve_repos_dir

repo_name = 'debug-health-' + uuid.uuid4().hex[:6]
repo_path = os.path.join(REPOS_DIR, repo_name)
os.makedirs(os.path.join(repo_path, 'services'), exist_ok=True)

_create_sample_service(repo_path)

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

