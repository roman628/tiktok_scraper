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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- New metadata columns
    track_name TEXT,
    track_artist TEXT,
    upload_hour INTEGER CHECK (upload_hour >= 0 AND upload_hour <= 23),
    upload_minute INTEGER CHECK (upload_minute >= 0 AND upload_minute <= 59),
    onscreen_text TEXT,
    has_text_overlay BOOLEAN DEFAULT FALSE,
    creator_follower_count BIGINT,
    creator_is_verified BOOLEAN
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
CREATE INDEX IF NOT EXISTS idx_videos_track_name ON videos(track_name);
CREATE INDEX IF NOT EXISTS idx_videos_track_artist ON videos(track_artist);
CREATE INDEX IF NOT EXISTS idx_videos_upload_hour ON videos(upload_hour);
CREATE INDEX IF NOT EXISTS idx_videos_has_text_overlay ON videos(has_text_overlay);

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

-- =====================================================================
-- MEDALLION ARCHITECTURE IMPLEMENTATION
-- =====================================================================
-- Bronze Layer: Raw data storage
-- Silver Layer: Cleaned and validated data
-- Gold Layer: Aggregated ML-ready features
-- =====================================================================

-- Create medallion schemas
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- =====================================================================
-- BRONZE LAYER - Raw Data Storage
-- =====================================================================
-- Store raw, unprocessed data exactly as collected

-- Raw video data ingestion table
CREATE TABLE IF NOT EXISTS bronze.raw_videos (
    ingestion_id SERIAL PRIMARY KEY,
    video_url TEXT NOT NULL,
    video_id VARCHAR(100),
    raw_metadata JSONB,  -- Complete raw response from yt-dlp/API
    raw_transcript TEXT,  -- Raw Whisper output
    raw_comments JSONB,  -- Raw comments data if available
    ingestion_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_batch_id VARCHAR(100),  -- Track which collector batch this came from
    collector_version VARCHAR(50),
    error_message TEXT,  -- Store any errors during collection
    retry_count INTEGER DEFAULT 0
);

-- Index for efficient lookups
CREATE INDEX IF NOT EXISTS idx_bronze_raw_videos_url ON bronze.raw_videos(video_url);
CREATE INDEX IF NOT EXISTS idx_bronze_raw_videos_ingestion ON bronze.raw_videos(ingestion_timestamp);
CREATE INDEX IF NOT EXISTS idx_bronze_raw_videos_batch ON bronze.raw_videos(source_batch_id);

-- =====================================================================
-- SILVER LAYER - Cleaned & Validated Data
-- =====================================================================
-- Data after cleaning, validation, and normalization

-- Create silver tables by migrating existing public tables
-- This preserves existing data while establishing the silver layer
DO $$
BEGIN
    -- Check if we need to migrate tables to silver schema
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables 
                   WHERE table_schema = 'silver' AND table_name = 'videos') THEN
        
        -- Create silver.videos as a copy of structure
        CREATE TABLE silver.videos (LIKE public.videos INCLUDING ALL);
        
        -- Copy existing data if any
        INSERT INTO silver.videos SELECT * FROM public.videos ON CONFLICT DO NOTHING;
        
        -- Create other silver tables
        CREATE TABLE silver.transcriptions (LIKE public.transcriptions INCLUDING ALL);
        INSERT INTO silver.transcriptions SELECT * FROM public.transcriptions ON CONFLICT DO NOTHING;
        
        CREATE TABLE silver.comments (LIKE public.comments INCLUDING ALL);
        INSERT INTO silver.comments SELECT * FROM public.comments ON CONFLICT DO NOTHING;
        
        CREATE TABLE silver.hashtags (LIKE public.hashtags INCLUDING ALL);
        INSERT INTO silver.hashtags SELECT * FROM public.hashtags ON CONFLICT DO NOTHING;
        
        CREATE TABLE silver.video_hashtags (LIKE public.video_hashtags INCLUDING ALL);
        INSERT INTO silver.video_hashtags SELECT * FROM public.video_hashtags ON CONFLICT DO NOTHING;
        
    END IF;
END $$;

-- Add validation columns to silver tables if they don't exist
ALTER TABLE silver.videos ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20) DEFAULT 'validated';
ALTER TABLE silver.videos ADD COLUMN IF NOT EXISTS validation_timestamp TIMESTAMP WITH TIME ZONE;
ALTER TABLE silver.videos ADD COLUMN IF NOT EXISTS data_quality_score DECIMAL(3,2); -- 0.00 to 1.00

-- =====================================================================
-- GOLD LAYER - ML-Ready Features
-- =====================================================================
-- Pre-computed features and aggregations for ML training

-- ML feature store table
CREATE TABLE IF NOT EXISTS gold.ml_features (
    feature_id SERIAL PRIMARY KEY,
    video_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Basic metrics
    view_count BIGINT,
    like_count BIGINT,
    comment_count BIGINT,
    share_count BIGINT,
    
    -- Engagement features
    engagement_rate DECIMAL(10,6),  -- like_count / view_count
    comment_rate DECIMAL(10,6),     -- comment_count / view_count
    share_rate DECIMAL(10,6),       -- share_count / view_count
    
    -- Text features
    transcript_length INTEGER,
    transcript_word_count INTEGER,
    avg_word_length DECIMAL(5,2),
    sentence_count INTEGER,
    
    -- Sentiment features
    sentiment_score DECIMAL(5,4),   -- -1 to 1
    sentiment_magnitude DECIMAL(5,4),
    positive_word_ratio DECIMAL(5,4),
    negative_word_ratio DECIMAL(5,4),
    
    -- Temporal features
    upload_hour INTEGER,
    upload_day_of_week INTEGER,
    days_since_upload INTEGER,
    
    -- Content features
    has_hashtags BOOLEAN,
    hashtag_count INTEGER,
    has_transcript BOOLEAN,
    video_duration_seconds INTEGER,
    
    -- Performance categories
    performance_tier VARCHAR(20),  -- 'viral', 'popular', 'moderate', 'low'
    virality_score DECIMAL(10,6),  -- Composite score
    
    -- ML metadata
    feature_version VARCHAR(20) DEFAULT '1.0',
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for ML queries
CREATE INDEX IF NOT EXISTS idx_gold_ml_features_video_id ON gold.ml_features(video_id);
CREATE INDEX IF NOT EXISTS idx_gold_ml_features_performance ON gold.ml_features(performance_tier);
CREATE INDEX IF NOT EXISTS idx_gold_ml_features_computed ON gold.ml_features(computed_at);

-- Aggregated statistics for model training
CREATE TABLE IF NOT EXISTS gold.training_datasets (
    dataset_id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(100) UNIQUE NOT NULL,
    dataset_type VARCHAR(20),  -- 'train', 'validation', 'test'
    video_ids TEXT[],  -- Array of video IDs in this dataset
    feature_columns TEXT[],  -- Features used
    target_column VARCHAR(50),  -- Target variable
    row_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_version VARCHAR(50),
    notes TEXT
);

-- Model performance tracking
CREATE TABLE IF NOT EXISTS gold.model_metrics (
    metric_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    dataset_id INTEGER REFERENCES gold.training_datasets(dataset_id),
    accuracy DECIMAL(5,4),
    precision_score DECIMAL(5,4),
    recall_score DECIMAL(5,4),
    f1_score DECIMAL(5,4),
    rmse DECIMAL(10,4),
    mae DECIMAL(10,4),
    r2_score DECIMAL(5,4),
    training_duration_seconds INTEGER,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================================
-- ETL FUNCTIONS - Data Movement Between Layers
-- =====================================================================

-- Function to move data from Bronze to Silver with validation
CREATE OR REPLACE FUNCTION etl_bronze_to_silver(batch_id VARCHAR DEFAULT NULL)
RETURNS INTEGER AS $$
DECLARE
    processed_count INTEGER := 0;
BEGIN
    -- Insert validated records from bronze to silver
    INSERT INTO silver.videos (
        video_id, url, title, description, duration,
        uploader, uploader_id, uploader_url,
        view_count, like_count, comment_count,
        upload_date, timestamp, downloaded_at,
        validation_status, validation_timestamp
    )
    SELECT 
        raw_metadata->>'id',
        video_url,
        raw_metadata->>'title',
        raw_metadata->>'description',
        (raw_metadata->>'duration')::INTEGER,
        raw_metadata->>'uploader',
        raw_metadata->>'uploader_id',
        raw_metadata->>'uploader_url',
        (raw_metadata->>'view_count')::BIGINT,
        (raw_metadata->>'like_count')::BIGINT,
        (raw_metadata->>'comment_count')::BIGINT,
        to_date(raw_metadata->>'upload_date', 'YYYYMMDD'),
        (raw_metadata->>'timestamp')::BIGINT,
        ingestion_timestamp,
        'validated',
        NOW()
    FROM bronze.raw_videos
    WHERE 
        (batch_id IS NULL OR source_batch_id = batch_id)
        AND error_message IS NULL
        AND raw_metadata IS NOT NULL
        AND raw_metadata->>'id' IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM silver.videos sv 
            WHERE sv.video_id = raw_metadata->>'id'
        );
    
    GET DIAGNOSTICS processed_count = ROW_COUNT;
    RETURN processed_count;
END;
$$ LANGUAGE plpgsql;

-- Function to compute ML features from Silver to Gold
CREATE OR REPLACE FUNCTION etl_silver_to_gold()
RETURNS INTEGER AS $$
DECLARE
    processed_count INTEGER := 0;
BEGIN
    -- Insert or update ML features
    INSERT INTO gold.ml_features (
        video_id,
        view_count, like_count, comment_count, share_count,
        engagement_rate, comment_rate, share_rate,
        transcript_length, transcript_word_count,
        upload_hour, upload_day_of_week,
        has_hashtags, hashtag_count, has_transcript,
        video_duration_seconds,
        performance_tier,
        virality_score
    )
    SELECT 
        v.video_id,
        v.view_count, v.like_count, v.comment_count, v.share_count,
        -- Engagement rates
        CASE WHEN v.view_count > 0 
            THEN v.like_count::DECIMAL / v.view_count 
            ELSE 0 END,
        CASE WHEN v.view_count > 0 
            THEN v.comment_count::DECIMAL / v.view_count 
            ELSE 0 END,
        CASE WHEN v.view_count > 0 
            THEN v.share_count::DECIMAL / v.view_count 
            ELSE 0 END,
        -- Text features
        LENGTH(t.whisper_transcription),
        array_length(string_to_array(t.whisper_transcription, ' '), 1),
        -- Temporal features (upload_date is DATE only, so use default hour)
        0,  -- Default hour since we only have date not timestamp
        EXTRACT(dow FROM v.upload_date),
        -- Content features
        EXISTS(SELECT 1 FROM silver.video_hashtags vh WHERE vh.video_id = v.id),
        (SELECT COUNT(*) FROM silver.video_hashtags vh WHERE vh.video_id = v.id),
        t.whisper_transcription IS NOT NULL,
        v.duration,
        -- Performance tier
        CASE 
            WHEN v.view_count > 1000000 THEN 'viral'
            WHEN v.view_count > 100000 THEN 'popular'
            WHEN v.view_count > 10000 THEN 'moderate'
            ELSE 'low'
        END,
        -- Virality score (composite metric)
        CASE WHEN v.view_count > 0 
            THEN (v.like_count::DECIMAL / v.view_count * 0.4 + 
                  v.comment_count::DECIMAL / v.view_count * 0.3 +
                  v.share_count::DECIMAL / v.view_count * 0.3) * 100
            ELSE 0 END
    FROM silver.videos v
    LEFT JOIN silver.transcriptions t ON t.video_id = v.id
    WHERE NOT EXISTS (
        SELECT 1 FROM gold.ml_features mf 
        WHERE mf.video_id = v.video_id
    )
    ON CONFLICT (video_id) DO UPDATE SET
        view_count = EXCLUDED.view_count,
        like_count = EXCLUDED.like_count,
        engagement_rate = EXCLUDED.engagement_rate,
        updated_at = NOW();
    
    GET DIAGNOSTICS processed_count = ROW_COUNT;
    RETURN processed_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- MATERIALIZED VIEWS FOR ML TRAINING
-- =====================================================================

-- Create materialized view for efficient ML training queries
CREATE MATERIALIZED VIEW IF NOT EXISTS gold.ml_training_view AS
SELECT 
    f.*,
    v.title,
    v.description,
    v.uploader,
    t.whisper_transcription,
    -- Add computed lag features
    LAG(f.view_count, 1) OVER (PARTITION BY v.uploader ORDER BY v.upload_date) as prev_video_views,
    AVG(f.view_count) OVER (PARTITION BY v.uploader) as avg_uploader_views
FROM gold.ml_features f
JOIN silver.videos v ON v.video_id = f.video_id
LEFT JOIN silver.transcriptions t ON t.video_id = v.id
WHERE f.has_transcript = true;

-- Create unique index on materialized view for concurrent refresh
DROP INDEX IF EXISTS gold.idx_ml_training_view_video_id;
CREATE UNIQUE INDEX idx_ml_training_view_video_id ON gold.ml_training_view(video_id);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_ml_training_view()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY gold.ml_training_view;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- MIGRATION HELPERS
-- =====================================================================

-- Function to safely migrate existing data to medallion architecture
CREATE OR REPLACE FUNCTION migrate_to_medallion()
RETURNS TABLE(status TEXT, records_migrated INTEGER) AS $$
DECLARE
    silver_count INTEGER;
    gold_count INTEGER;
BEGIN
    -- Ensure silver layer has all data from public schema
    PERFORM etl_bronze_to_silver();
    
    -- Compute features in gold layer
    gold_count := etl_silver_to_gold();
    
    -- Refresh ML training view
    PERFORM refresh_ml_training_view();
    
    RETURN QUERY 
    SELECT 'Migration completed successfully'::TEXT, gold_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- SCHEDULED ETL JOB (Optional - requires pg_cron extension)
-- =====================================================================
-- Uncomment if pg_cron is installed
-- SELECT cron.schedule('etl-bronze-to-silver', '0 * * * *', 'SELECT etl_bronze_to_silver();');
-- SELECT cron.schedule('etl-silver-to-gold', '15 * * * *', 'SELECT etl_silver_to_gold();');
-- SELECT cron.schedule('refresh-ml-view', '30 * * * *', 'SELECT refresh_ml_training_view();');