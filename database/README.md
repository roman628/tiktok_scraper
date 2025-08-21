# PostgreSQL Database Setup for TikTok Scraper

## Overview

This guide explains how to migrate from the JSON-based storage (`master2.json`) to PostgreSQL for improved performance, scalability, and concurrent access.

## Prerequisites

- PostgreSQL 12+ installed
- Python packages: `psycopg2-binary` (or `psycopg2`)
- Existing `master2.json` file (optional, for migration)

## Quick Start

### 1. Install PostgreSQL

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download and install from https://www.postgresql.org/download/windows/

### 2. Install Python Dependencies

```bash
pip install psycopg2-binary tqdm
```

### 3. Create Database

```bash
# Connect to PostgreSQL as superuser
psql -U postgres

# Create database
CREATE DATABASE tiktok_scraper;

# Create user (optional)
CREATE USER tiktok_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tiktok_scraper TO tiktok_user;

# Exit
\q
```

### 4. Initialize Schema

```bash
# Run the schema creation script
psql -U postgres -d tiktok_scraper -f database/schema.sql
```

### 5. Configure Application

Edit `config.toml`:

```toml
[database]
enabled = true         # Enable PostgreSQL
host = "localhost"
port = 5432
database = "tiktok_scraper"
user = "postgres"      # Or your created user
password = ""          # Set DB_PASSWORD env var instead
```

For security, use environment variable:
```bash
export DB_PASSWORD="your_password"
```

### 6. Migrate Existing Data (Optional)

If you have existing data in `master2.json`:

```bash
# Dry run to validate data
python database/migrate_json_to_postgres.py data/master2.json --dry-run

# Perform actual migration
python database/migrate_json_to_postgres.py data/master2.json \
    --user postgres \
    --database tiktok_scraper \
    --batch-size 100
```

## Database Structure

### Main Tables

- **videos**: Core video metadata
- **hashtags**: Unique hashtags (normalized)
- **video_hashtags**: Many-to-many relationship
- **transcriptions**: Whisper AI transcriptions
- **comments**: Video comments with replies
- **processing_status**: Track processing state

### Key Features

- **Normalized design**: Efficient storage and queries
- **Indexes**: Fast lookups on URLs, video IDs, timestamps
- **Views**: Pre-built queries for ML training
- **Triggers**: Automatic timestamp updates
- **ACID compliance**: Data integrity guaranteed

## Usage Modes

### 1. Database-Only Mode

Set in `config.toml`:
```toml
[database]
enabled = true

[output]
json_output = ""  # Can be empty when using database
```

### 2. Dual-Write Mode (Migration Period)

The system can write to both database and JSON:
```toml
[database]
enabled = true

[output]
json_output = "data/master2.json"
```

### 3. JSON-Only Mode (Legacy)

```toml
[database]
enabled = false

[output]
json_output = "data/master2.json"
```

## Performance Benefits

| Feature | JSON File | PostgreSQL |
|---------|-----------|------------|
| Concurrent writes | ❌ File locking | ✅ ACID transactions |
| Query speed | O(n) full scan | O(1) indexed lookups |
| Duplicate detection | In-memory set | Indexed query |
| Partial updates | Rewrite entire file | Update specific fields |
| Data size limit | Memory constrained | Terabytes |
| ML data access | Load entire file | Query specific subsets |

## Common Operations

### Check Database Statistics

```sql
-- Connect to database
psql -U postgres -d tiktok_scraper

-- View statistics
SELECT * FROM database_statistics;

-- Count videos by uploader
SELECT uploader, COUNT(*) as video_count 
FROM videos 
GROUP BY uploader 
ORDER BY video_count DESC 
LIMIT 10;

-- Recent transcriptions
SELECT v.title, t.whisper_transcription 
FROM videos v 
JOIN transcriptions t ON t.video_id = v.id 
ORDER BY t.transcription_timestamp DESC 
LIMIT 5;
```

### Export Database to JSON

```python
from src.database_manager import DatabaseManager

db = DatabaseManager(database="tiktok_scraper")
db.export_to_json("export.json")
```

### Backup Database

```bash
# Full backup
pg_dump -U postgres tiktok_scraper > backup_$(date +%Y%m%d).sql

# Compressed backup
pg_dump -U postgres -Fc tiktok_scraper > backup_$(date +%Y%m%d).dump
```

### Restore Database

```bash
# From SQL file
psql -U postgres tiktok_scraper < backup.sql

# From compressed dump
pg_restore -U postgres -d tiktok_scraper backup.dump
```

## Troubleshooting

### Connection Issues

```bash
# Check PostgreSQL is running
pg_isready

# Check connection
psql -U postgres -d tiktok_scraper -c "SELECT 1"

# View PostgreSQL logs
tail -f /usr/local/var/log/postgresql@14.log  # macOS
sudo tail -f /var/log/postgresql/postgresql-*.log  # Linux
```

### Permission Errors

```sql
-- Grant all permissions to user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO tiktok_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO tiktok_user;
```

### Performance Tuning

```sql
-- Analyze tables for query planner
ANALYZE;

-- View table sizes
SELECT 
    schemaname AS table_schema,
    tablename AS table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Migration Rollback

If you need to switch back to JSON:

1. Export current database:
```bash
python -c "
from src.database_manager import DatabaseManager
db = DatabaseManager()
db.export_to_json('data/master2_restored.json')
"
```

2. Update config:
```toml
[database]
enabled = false

[output]
json_output = "data/master2_restored.json"
```

## Next Steps

1. **Monitor Performance**: Use `pg_stat_statements` for query analysis
2. **Set up Replication**: For high availability
3. **Configure Backups**: Automated daily backups
4. **Optimize Queries**: Add indexes based on usage patterns
5. **Set up Monitoring**: Use tools like pgAdmin or Grafana

## Support

For issues or questions:
- Check PostgreSQL logs
- Review error messages in application logs
- Ensure database service is running
- Verify connection parameters
- Check disk space and permissions