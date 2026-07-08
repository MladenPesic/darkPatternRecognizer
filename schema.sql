CREATE TABLE IF NOT EXISTS scans (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_time timestamptz NOT NULL DEFAULT now(),
    url TEXT NOT NULL,
    html_pointer TEXT NOT NULL,
    screenshot_pointer TEXT NOT NULL,
    llm_report TEXT NOT NULL
    );