# AI News Scraper to n8n Webhook

This repository runs an AI news scraper via GitHub Actions and sends the normalized JSON results to an n8n Cloud webhook. This is the first step in an automated AI newsletter generation and distribution pipeline.

## Architecture

1. **GitHub Actions**: Runs the scraper every Monday at 03:00 UTC (07:00 Dubai time) or manually.
2. **Python Scraper (`src/unified_ai_news_collector.py`)**: Uses Python and Playwright/Crawl4AI/Scrapling to scrape the latest AI news based on an intelligent fallback system.
3. **JSON Report**: The scraper outputs a JSON report into `ai_news_collection_output/`.
4. **Webhook Sender (`src/send_to_n8n.py`)**: Reads the latest JSON report, normalizes it for Supabase/n8n, and posts it to the n8n Cloud webhook.
5. **n8n Cloud**: Receives the payload and orchestrates the downstream tasks.

## Why n8n Cloud and GitHub Actions?

n8n Cloud has limitations on running local Python scripts that require complex system dependencies like Playwright browsers or Crawl4AI directly. Therefore, GitHub Actions handles the heavy scraping environment, while n8n manages the database storage, agentic deduplication, and newsletter generation logic.

## Setup Instructions

1. **Create an n8n Webhook Node**:
   - Method: `POST`
   - Path: `ai-news-intake`
2. **Copy the Production URL**: Get the test or production URL of your new n8n Webhook node.
3. **Add GitHub Secret**: Go to your repository settings -> Secrets and variables -> Actions, and add a new secret called `N8N_WEBHOOK_URL` with your webhook URL.
4. **Trigger Workflow**: Go to the Actions tab and manually run the "Run AI News Scraper" workflow.
5. **Verify**: Ensure the n8n webhook successfully receives the payload.

## Local Testing

You can run the pipeline locally for testing.

1. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   python -m playwright install chromium
   ```
2. Set environment variables (or use a `.env` file):
   ```powershell
   $env:N8N_WEBHOOK_URL="https://your-n8n-url/webhook-test/ai-news-intake"
   ```
3. Run the scraper:
   ```powershell
   python src/unified_ai_news_collector.py
   ```
   *Expect output to be generated in `ai_news_collection_output/`.*
4. Send to n8n:
   ```powershell
   python src/send_to_n8n.py
   ```

## Expected n8n Payload

The payload is normalized and strictly prepared for insertion into Supabase tables via n8n.

It contains:
- `run`: Metadata about the scraper run.
- `articles`: Array of parsed articles ready for the `raw_articles` table.
- `source_results`: Original raw extraction results for auditing.

### Future n8n Stages (To be built in n8n)
- Validate incoming payload.
- Insert run metadata into `workflow_runs`.
- Insert article data into `raw_articles`.
- Use OpenAI agents for deduplication and ranking.
- Generate and distribute the HTML newsletter.
