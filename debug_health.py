import argparse
import os
import sys

sys.path.insert(0, '.')

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv(override=False)

# Now import after environment is loaded
from app.config import REPOS_DIR
from api.services.repository_health_engine import RepositoryHealthEngine
from supabase import create_client


def main():
    """
    Debug script to run health analysis on a repository.
    Usage: python debug_health.py --repo-id "repo-uuid-here"
    """
    parser = argparse.ArgumentParser(description='Run health analysis on a repository')
    parser.add_argument('--repo-id', required=True, help='Repository UUID to analyze')
    args = parser.parse_args()
    
    repo_id = args.repo_id
    
    # Get Supabase credentials
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')
    
    if not url or not key:
        print(f"Error: SUPABASE_URL and SUPABASE_SERVICE_KEY not found in .env")
        sys.exit(1)
    
    try:
        supabase = create_client(url, key)
        
        # Fetch repository metadata
        repo_response = supabase.table('repositories').select('id, name, index_name').eq('id', repo_id).single().execute()
        repo_data = repo_response.data
        repo_name = repo_data.get('name') or repo_data.get('index_name')
        
        print(f"\n{'='*60}")
        print(f"Running health check for repo: {repo_id}")
        print(f"{'='*60}\n")
        
        # Run health analysis using the correct engine.run() signature
        engine = RepositoryHealthEngine()
        
        # Build repo dict as expected by engine.run()
        repo_dict = {
            'id': repo_id,
            'name': repo_name,
            'index_name': repo_name,
        }
        
        result = engine.run(repo_dict)
        
        # Extract top-level score information
        top_level = result.get('top_level', {})
        repository_health = top_level.get('repository_health', 'N/A')
        grade = top_level.get('grade', 'N/A')
        status = top_level.get('status', 'N/A')
        trend = top_level.get('trend', 0)
        
        # Format and display output as per documentation
        print(f"Health Score: {repository_health}")
        print(f"Grade: {grade}")
        print(f"Status: {status}")
        print(f"Trend: {trend:+d}")
        print(f"Categories Analyzed: {len(result.get('categories', []))}")
        
        # Show category breakdown
        categories = result.get('categories', [])
        if categories:
            print(f"\n{'Category':<20} | {'Score':<6} | {'Grade':<6} | {'Trend':<7}")
            print("-" * 52)
            for cat in categories:
                category = cat.get('category', 'Unknown')[:19]
                score = cat.get('score', 0)
                cat_grade = cat.get('grade', 'N/A')
                cat_trend = f"{cat.get('trend', 0):+d}"
                print(f"{category:<20} | {score:>5} | {cat_grade:>5} | {cat_trend:>6}")
        
        print(f"\n{'='*60}")
        print("✓ Health analysis completed successfully")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

