CREATE TABLE IF NOT EXISTS scans (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_time timestamptz NOT NULL DEFAULT now(),
    url TEXT NOT NULL,
    html_pointer TEXT,
    screenshot_pointer TEXT,
    llm_report TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
    );
