import os
import sys
import json
import uuid
import glob
import hashlib
import datetime as dt
import urllib.request
import urllib.error
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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
        "pipeline": "capgemini_ai_newsletter",
        "stage": "scraper_completed",
        "schema_version": "v1",
        "generated_at": raw_report.get("run_timestamp", now_iso),
        "sent_at": now_iso,
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
        "articles": normalized_articles,
        "source_results": results,
        "metadata": {
            "intended_database": "supabase_postgres",
            "n8n_next_stage": "store_raw_articles_then_agentic_processing"
        }
    }
    
    return payload

def send_to_n8n(payload: dict, webhook_url: str):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={'Content-Type': 'application/json', 'User-Agent': 'AINewsScraper/1.0'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            return status_code, response_body
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.reason}")
        print(f"Response: {e.read().decode('utf-8')}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URLError: {e.reason}")
        sys.exit(1)

def main():
    webhook_url = os.environ.get("N8N_WEBHOOK_URL")
    if not webhook_url:
        print("ERROR: N8N_WEBHOOK_URL environment variable is missing.")
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
    print(f"Total Sources: {run_info['total_sources']}")
    print(f"Accessible Sources: {run_info['accessible_sources']}")
    print(f"Inaccessible Sources: {run_info['inaccessible_sources']}")
    print(f"Total Normalized Articles: {run_info['total_articles']}")
    
    print("Sending payload to n8n webhook...")
    status_code, response_body = send_to_n8n(payload, webhook_url)
    
    print(f"n8n Response Status Code: {status_code}")
    if not (200 <= status_code < 300):
        print(f"ERROR: Non-2xx status code from n8n: {status_code}")
        print(response_body)
        sys.exit(1)
        
    print("Successfully sent to n8n.")

if __name__ == "__main__":
    main()
