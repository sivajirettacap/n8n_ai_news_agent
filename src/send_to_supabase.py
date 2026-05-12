import os
import sys
import json
import uuid
import glob
import hashlib
import datetime as dt
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from supabase import create_client, Client

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "ai_news_collection_output"

def generate_article_id(url: str, title: str) -> str:
    unique_string = f"{url}_{title}".encode('utf-8')
    return hashlib.sha256(unique_string).hexdigest()

def find_latest_report() -> Path | None:
    if not OUTPUT_DIR.exists():
        return None
    
    json_files = glob.glob(str(OUTPUT_DIR / "ai_news_access_report_*.json"))
    if not json_files:
        return None
        
    return Path(max(json_files, key=os.path.getctime))

def normalize_payload(raw_report: dict) -> dict:
    run_id = str(uuid.uuid4())
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    
    results = raw_report.get("results", [])
    total_sources = len(results)
    accessible_sources = sum(1 for r in results if r.get("ok"))
    inaccessible_sources = total_sources - accessible_sources
    
    normalized_articles = []
    
    for source_res in results:
        source_name = source_res.get("source", "Unknown")
        category = source_res.get("category", "")
        priority = source_res.get("priority", "")
        success_mode = "success" if source_res.get("ok") else "failed"
        framework = source_res.get("framework_used", "")
        
        articles = source_res.get("articles", [])
        if not articles and "entries" in source_res:
            articles = source_res.get("entries", [])
            
        if not isinstance(articles, list):
            continue
            
        for art in articles:
            if not isinstance(art, dict):
                continue
            url = art.get("link", "") or art.get("url", "")
            title = art.get("title", "")
            if not url or not title:
                continue
                
            published_at = art.get("published", "") or art.get("published_at", "")
            
            norm_art = {
                "article_id": generate_article_id(url, title),
                "run_id": run_id,
                "source": source_name,
                "category": category,
                "priority": priority,
                "title": title,
                "url": url,
                "published_at": published_at,
                "summary": art.get("summary", "") or art.get("description", ""),
                "success_mode": success_mode,
                "selected_framework": framework,
                "scraped_at": now_iso,
                "raw_metadata": {
                    "author": art.get("author", ""),
                    "id": art.get("id", ""),
                }
            }
            normalized_articles.append(norm_art)
            
    payload = {
        "run": {
            "run_id": run_id,
            "runner": "github_actions",
            "repo": "capgemini_ai_newsletter_n8n",
            "status": "completed",
            "total_sources": total_sources,
            "accessible_sources": accessible_sources,
            "inaccessible_sources": inaccessible_sources,
            "total_articles": len(normalized_articles)
        },
        "articles": normalized_articles
    }
    
    return payload

def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")
        sys.exit(1)
        
    latest_report_path = find_latest_report()
    if not latest_report_path:
        print(f"ERROR: No JSON reports found in {OUTPUT_DIR}")
        sys.exit(1)
        
    print(f"Found latest report: {latest_report_path}")
    
    try:
        with open(latest_report_path, "r", encoding="utf-8") as f:
            raw_report = json.load(f)
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON in report file {latest_report_path}")
        sys.exit(1)
        
    payload = normalize_payload(raw_report)
    
    run_info = payload["run"]
    articles = payload["articles"]
    
    print(f"Total Sources: {run_info['total_sources']}")
    print(f"Accessible Sources: {run_info['accessible_sources']}")
    print(f"Inaccessible Sources: {run_info['inaccessible_sources']}")
    print(f"Total Normalized Articles: {run_info['total_articles']}")
    
    print("Connecting to Supabase...")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    print("Inserting run metadata into workflow_runs...")
    try:
        supabase.table("workflow_runs").upsert(run_info).execute()
        print("Run metadata inserted.")
    except Exception as e:
        print(f"Error inserting run metadata: {e}")
        sys.exit(1)
        
    if articles:
        print(f"Inserting {len(articles)} articles into raw_articles...")
        try:
            supabase.table("raw_articles").upsert(articles).execute()
            print("Articles inserted successfully.")
        except Exception as e:
            print(f"Error inserting articles: {e}")
            sys.exit(1)
    else:
        print("No articles to insert.")
        
    print("Successfully completed Supabase export.")

if __name__ == "__main__":
    main()
