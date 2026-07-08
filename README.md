# Dark Pattern Recognizer

A tool that scans web pages — especially e-commerce sites — to detect **dark patterns**:
manipulative design tactics used to deceive users into unwanted actions. Such manipulation
can lead to excessive and unwanted financial expenditure, a risk that falls hardest on
vulnerable users such as the elderly. This project aims to surface those tactics automatically.

## Architecture

The pipeline runs end to end in four stages:

1. **Fetch** — Playwright loads the target URL.
2. **Capture** — extract the page's HTML and visible text, and take a full-page screenshot.
3. **Analyze** — send the extracted text to the Gemini API to identify dark patterns.
4. **Store** — save the scan (URL, file pointers, and the generated report) as a row in Supabase.

## Tech Stack

- **Playwright** — headless browser automation for scraping
- **Google Gemini** (`gemini-3.1-flash-lite`) — dark-pattern analysis
- **Supabase / PostgreSQL** — data storage
- **psycopg** — PostgreSQL driver for Python

## Setup

1. Clone the repository:
git clone <repo-url>
cd darkPatternRecognizer
2. Create and activate a virtual environment:
python -m venv venv
source venv/Scripts/activate      # Windows (Git Bash)
source venv/bin/activate         # macOS / Linux 
3. Install dependencies and browser binaries:
pip install -r requirements.txt
playwright install
4. Configure environment variables — copy the example file and fill in your own credentials:
cp .env.example .env
Then set `DATABASE_URL` (Supabase connection string) and `GEMINI_API_KEY` in `.env`.
5. Create the database table by running the contents of `schema.sql` in the Supabase SQL editor.

## Project Status

A working end-to-end skeleton has been built: it scrapes a single page, analyzes it with
Gemini, and stores the result in Supabase. Each stage is intentionally minimal and will be
expanded in later phases (real classifier, geometry-aware analysis, storage integration, UI).