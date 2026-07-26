CREATE TABLE IF NOT EXISTS scans (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_time timestamptz NOT NULL DEFAULT now(),
    url TEXT NOT NULL,
    html_pointer TEXT,
    screenshot_pointer TEXT,
    llm_report TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
    );


CREATE TABLE IF NOT EXISTS elements(
    id BIGINT  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scan_id BIGINT  NOT NULL REFERENCES scans(id),
    element_type TEXT NOT NULL,
    element_text TEXT,
    geometry_x REAL,
    geometry_y REAL,
    geometry_width REAL,
    geometry_height REAL,
    darkpattern_label SMALLINT,
    confidence REAL,
    llm_label SMALLINT,
    llm_category TEXT,
    llm_reason TEXT
);