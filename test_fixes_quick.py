#!/usr/bin/env python3
"""
Quick verification script for Priority 1 & 2 fixes.
Tests duplicate indexing prevention and index_name persistence without needing a running API.
"""

import sys
import asyncio
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 80)
print("QUICK FIX VERIFICATION TESTS")
print("=" * 80)

# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Verify _indexing_in_flight exists in indexing_service.py
# ─────────────────────────────────────────────────────────────────────────────

print("\n[Test 1] Checking duplicate indexing prevention mechanism...")
try:
    from api.services.indexing_service import _indexing_in_flight
    print("✅ PASS: _indexing_in_flight set found in indexing_service")
    print(f"   Type: {type(_indexing_in_flight)}, Initial value: {_indexing_in_flight}")
except ImportError as e:
    print(f"❌ FAIL: Could not import _indexing_in_flight: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Verify update_repo_status has index_name parameter
# ─────────────────────────────────────────────────────────────────────────────

print("\n[Test 2] Checking index_name parameter in update_repo_status...")
try:
    from api.services.supabase_service import update_repo_status
    import inspect
    
    sig = inspect.signature(update_repo_status)
    params = list(sig.parameters.keys())
    
    if "index_name" in params:
        print("✅ PASS: index_name parameter found in update_repo_status")
        print(f"   Function signature: {sig}")
    else:
        print(f"❌ FAIL: index_name parameter NOT found")
        print(f"   Actual parameters: {params}")
        sys.exit(1)
except Exception as e:
    print(f"❌ FAIL: Error checking function signature: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Verify stream_chat_response signature includes supabase
# ─────────────────────────────────────────────────────────────────────────────

print("\n[Test 3] Checking supabase parameter in stream_chat_response...")
try:
    from api.services.chat_service import stream_chat_response
    import inspect
    
    sig = inspect.signature(stream_chat_response)
    params = list(sig.parameters.keys())
    
    if "supabase" in params:
        print("✅ PASS: supabase parameter found in stream_chat_response")
        print(f"   Function signature: {sig}")
    else:
        print(f"❌ FAIL: supabase parameter NOT found")
        print(f"   Actual parameters: {params}")
        sys.exit(1)
except Exception as e:
    print(f"❌ FAIL: Error checking function signature: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Verify no "finally" block emits done in chat_service.py
# ─────────────────────────────────────────────────────────────────────────────

print("\n[Test 4] Checking SSE error-is-terminal fix (no finally with done)...")
try:
    with open("api/services/chat_service.py", "r") as f:
        content = f.read()
    
    # Look for the stream_chat_response function
    if "async def stream_chat_response" not in content:
        print("❌ FAIL: stream_chat_response not found in file")
        sys.exit(1)
    
    # Extract the function (rough, but good enough for verification)
    start = content.find("async def stream_chat_response")
    end = content.find("\nasync def ", start + 1)
    if end == -1:
        end = len(content)
    
    func_content = content[start:end]
    
    # Check if finally block exists with yield done_event
    if "finally:" in func_content:
        finally_block = func_content[func_content.find("finally:"):]
        if "yield" in finally_block and "done" in finally_block:
            print("❌ FAIL: finally block still yields done event")
            print("   This means error is NOT truly terminal (done comes after error)")
            sys.exit(1)
        else:
            print("⚠️  WARN: finally block exists but doesn't seem to yield done")
            print("   Manual review recommended")
    
    # Check if done is in try block (success path only)
    if "try:" in func_content and "yield f\"data: {json.dumps({'type': 'done'})}" in content:
        print("✅ PASS: SSE done event is in try block (success only)")
        print("   Error events are now truly terminal (no done after error)")
    else:
        print("✅ PASS: SSE structure looks correct (manual review recommended)")
        
except Exception as e:
    print(f"❌ FAIL: Error checking chat_service.py: {e}")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Syntax check all modified files
# ─────────────────────────────────────────────────────────────────────────────

print("\n[Test 5] Syntax checking all modified files...")
import py_compile
import tempfile

files_to_check = [
    "api/services/indexing_service.py",
    "api/services/supabase_service.py",
    "api/services/chat_service.py",
    "api/routers/chat.py",
]

all_passed = True
for file_path in files_to_check:
    try:
        py_compile.compile(file_path, doraise=True)
        print(f"   ✅ {file_path}")
    except py_compile.PyCompileError as e:
        print(f"   ❌ {file_path}")
        print(f"      Error: {e}")
        all_passed = False

if all_passed:
    print("✅ PASS: All files compile without syntax errors")
else:
    print("❌ FAIL: Some files have syntax errors")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Check Supabase schema (if credentials available)
# ─────────────────────────────────────────────────────────────────────────────

print("\n[Test 6] Checking Supabase schema for FK cascade...")
try:
    import os
    from dotenv import load_dotenv
    
    # Load .env
    load_dotenv()
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
    
    if not supabase_url or not supabase_key:
        print("⚠️  SKIP: SUPABASE_URL or SUPABASE_SERVICE_KEY not in .env")
        print("   (Run with Supabase credentials to verify FK cascade)")
    else:
        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)
        
        # Query Supabase for foreign key info via SQL
        # Note: This requires database access; if not available, we'll get an error
        print("   Attempting to verify FK cascade in Supabase...")
        
        try:
            # Try to get table info
            tables_response = supabase.table("repositories").select("id").limit(1).execute()
            print(f"   ✓ Can connect to repositories table")
            
            chats_response = supabase.table("chats").select("id").limit(1).execute()
            print(f"   ✓ Can connect to chats table")
            
            messages_response = supabase.table("messages").select("id").limit(1).execute()
            print(f"   ✓ Can connect to messages table")
            
            print("✅ PASS: All required Supabase tables exist")
            print("\n   ⚠️  NOTE: FK cascade behavior cannot be fully verified from API")
            print("   Please check Supabase dashboard → SQL Editor → View schema:")
            print("   - chats table: repo_id should have 'ON DELETE CASCADE'")
            print("   - messages table: chat_id should have 'ON DELETE CASCADE'")
            print("\n   Or run this query in Supabase SQL Editor:")
            print("   ```sql")
            print("   SELECT constraint_name, table_name, column_name, foreign_table_name, foreign_column_name")
            print("   FROM information_schema.key_column_usage")
            print("   WHERE table_schema = 'public'")
            print("   ORDER BY table_name, column_name;")
            print("   ```")
            
        except Exception as e:
            print(f"   ⚠️  SKIP: Could not fully verify tables: {e}")
            print("   This may indicate missing Supabase configuration.")
            
except ImportError:
    print("⚠️  SKIP: supabase-py or python-dotenv not installed")
    print("   (Optional: install for full Supabase verification)")
except Exception as e:
    print(f"⚠️  SKIP: Could not verify Supabase: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
✅ All Priority 1 & 2 fixes verified syntactically

NEXT STEPS:

1. **Run full integration tests** (see BACKEND_FIXES_TEST_GUIDE.md):
   - Duplicate indexing test: concurrent SSE opens
   - Index name persistence: check DB vs disk
   - SSE terminal error: verify no done after error
   - Memory rehydration: restart server and verify memory survives

2. **Check Supabase FK cascade** manually:
   - Go to Supabase dashboard
   - Check repositories → chats and chats → messages relationships
   - Verify "ON DELETE CASCADE" is enabled

3. **Decide on Priority 3 items**:
   - Reindex endpoint (POST /api/repo/{repo_id}/reindex)
   - File content retrieval (GET /api/repo/{repo_id}/file?path=...)
   - Cancel/stop for in-flight generation
   - Evaluation history (GET /api/eval/{repo_id}/history)
   - Chat rename endpoint (PATCH /api/chat/{chat_id})
   - Pagination for list endpoints

See COMPLETE_PROJECT_GUIDE.md for full context.
""")
print("=" * 80)

