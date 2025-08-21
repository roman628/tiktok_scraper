-- Migration to add collector_status table for tracking collector.py execution status
-- This table helps the server know when the collector is running, stopped, or idle

CREATE TABLE IF NOT EXISTS collector_status (
    id INTEGER PRIMARY KEY DEFAULT 1,  -- Single row table (singleton pattern)
    status VARCHAR(20) DEFAULT 'stopped',  -- 'running', 'stopped', 'idle'
    started_at TIMESTAMP,  -- When the collector was last started
    stopped_at TIMESTAMP,  -- When the collector last stopped
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Last time collector processed URLs
    urls_processed INTEGER DEFAULT 0,  -- Total URLs processed in current session
    pid INTEGER,  -- Process ID of the running collector
    CONSTRAINT single_row CHECK (id = 1)  -- Ensure only one row
);

-- Insert initial row if it doesn't exist
INSERT INTO collector_status (id, status, stopped_at)
VALUES (1, 'stopped', CURRENT_TIMESTAMP)
ON CONFLICT (id) DO NOTHING;

-- Add index for quick status checks
CREATE INDEX IF NOT EXISTS idx_collector_status ON collector_status(status);

-- Grant permissions (adjust user as needed)
GRANT ALL PRIVILEGES ON TABLE collector_status TO ethan;