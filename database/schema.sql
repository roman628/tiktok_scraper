-- TikTok Scraper PostgreSQL Schema
-- Version: 1.0
-- Description: Database schema for storing TikTok video metadata, transcriptions, and comments

-- Create database (run as superuser)
-- CREATE DATABASE tiktok_scraper;
-- \c tiktok_scraper;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Core video table
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    video_id VARCHAR(100) UNIQUE NOT NULL,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    description TEXT,
    duration INTEGER,
    uploader VARCHAR(255),
    uploader_id VARCHAR(100),
    uploader_url TEXT,
    view_count BIGINT,
    like_count BIGINT,
    comment_count BIGINT,
    repost_count BIGINT,
    save_count BIGINT,
    share_count BIGINT,
    upload_date DATE,
    timestamp BIGINT,
    width INTEGER,
    height INTEGER,
    fps INTEGER,
    filesize BIGINT,
    format VARCHAR(50),
    downloaded_at TIMESTAMP WITH TIME ZONE,
    downloaded_with VARCHAR(100),
    platform VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Hashtags table (normalized)
CREATE TABLE IF NOT EXISTS hashtags (
    id SERIAL PRIMARY KEY,
    tag VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Video-hashtag relationship (many-to-many)
CREATE TABLE IF NOT EXISTS video_hashtags (
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    hashtag_id INTEGER REFERENCES hashtags(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, hashtag_id)
);

-- Transcriptions table
CREATE TABLE IF NOT EXISTS transcriptions (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    whisper_transcription TEXT,
    transcription_timestamp TIMESTAMP WITH TIME ZONE,
    model_used VARCHAR(50),
    language VARCHAR(10),
    confidence FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(video_id)
);

-- Comments table
CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    comment_id VARCHAR(100) UNIQUE NOT NULL,
    username VARCHAR(255),
    display_name VARCHAR(255),
    comment_text TEXT,
    like_count INTEGER DEFAULT 0,
    timestamp BIGINT,
    is_top_comment BOOLEAN DEFAULT FALSE,
    parent_comment_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    extracted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Processing status table (track what's been processed)
CREATE TABLE IF NOT EXISTS processing_status (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    comments_extracted BOOLEAN DEFAULT FALSE,
    comments_extracted_at TIMESTAMP WITH TIME ZONE,
    transcription_completed BOOLEAN DEFAULT FALSE,
    transcription_completed_at TIMESTAMP WITH TIME ZONE,
    ml_processed BOOLEAN DEFAULT FALSE,
    ml_processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(video_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_videos_url ON videos(url);
CREATE INDEX IF NOT EXISTS idx_videos_video_id ON videos(video_id);
CREATE INDEX IF NOT EXISTS idx_videos_downloaded_at ON videos(downloaded_at);
CREATE INDEX IF NOT EXISTS idx_videos_uploader_id ON videos(uploader_id);
CREATE INDEX IF NOT EXISTS idx_videos_upload_date ON videos(upload_date);

CREATE INDEX IF NOT EXISTS idx_comments_video_id ON comments(video_id);
CREATE INDEX IF NOT EXISTS idx_comments_username ON comments(username);
CREATE INDEX IF NOT EXISTS idx_comments_timestamp ON comments(timestamp);
CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_comment_id);

CREATE INDEX IF NOT EXISTS idx_transcriptions_video_id ON transcriptions(video_id);
CREATE INDEX IF NOT EXISTS idx_video_hashtags_video_id ON video_hashtags(video_id);
CREATE INDEX IF NOT EXISTS idx_video_hashtags_hashtag_id ON video_hashtags(hashtag_id);

CREATE INDEX IF NOT EXISTS idx_processing_status_video_id ON processing_status(video_id);
CREATE INDEX IF NOT EXISTS idx_processing_status_ml_processed ON processing_status(ml_processed);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_status_updated_at BEFORE UPDATE ON processing_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for ML training data
CREATE OR REPLACE VIEW ml_training_data AS
SELECT 
    v.*,
    t.whisper_transcription,
    t.transcription_timestamp,
    ps.comments_extracted,
    ps.comments_extracted_at,
    COALESCE(
        (SELECT json_agg(
            json_build_object(
                'comment_id', c.comment_id,
                'username', c.username,
                'display_name', c.display_name,
                'comment_text', c.comment_text,
                'like_count', c.like_count,
                'timestamp', c.timestamp
            ) ORDER BY c.like_count DESC
        ) 
        FROM comments c 
        WHERE c.video_id = v.id AND c.is_top_comment = true
        ), '[]'::json
    ) as top_comments,
    COALESCE(
        (SELECT array_agg(h.tag ORDER BY h.tag)
        FROM hashtags h
        JOIN video_hashtags vh ON vh.hashtag_id = h.id
        WHERE vh.video_id = v.id
        ), ARRAY[]::varchar[]
    ) as hashtags
FROM videos v
LEFT JOIN transcriptions t ON t.video_id = v.id
LEFT JOIN processing_status ps ON ps.video_id = v.id;

-- Collector status tracking table
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

-- Create statistics view
CREATE OR REPLACE VIEW database_statistics AS
SELECT 
    (SELECT COUNT(*) FROM videos) as total_videos,
    (SELECT COUNT(*) FROM comments) as total_comments,
    (SELECT COUNT(*) FROM transcriptions) as total_transcriptions,
    (SELECT COUNT(*) FROM hashtags) as unique_hashtags,
    (SELECT COUNT(DISTINCT uploader_id) FROM videos) as unique_uploaders,
    (SELECT pg_size_pretty(pg_database_size(current_database()))) as database_size,
    (SELECT MIN(downloaded_at) FROM videos) as earliest_download,
    (SELECT MAX(downloaded_at) FROM videos) as latest_download;

-- Grant permissions (adjust user as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tiktok_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tiktok_user;
-- GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO tiktok_user;