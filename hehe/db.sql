-- Database schema for Vuforia target management

-- Targets table
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT UNIQUE NOT NULL,  -- Vuforia target ID
    name TEXT NOT NULL,
    width REAL NOT NULL,
    image_path TEXT NOT NULL,
    metadata TEXT,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Target summaries table
CREATE TABLE IF NOT EXISTS target_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT UNIQUE NOT NULL,
    summary_data TEXT NOT NULL,  -- JSON data of the target summary
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (target_id) REFERENCES targets(target_id) ON DELETE CASCADE
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_targets_target_id ON targets(target_id);
CREATE INDEX IF NOT EXISTS idx_summaries_target_id ON target_summaries(target_id);