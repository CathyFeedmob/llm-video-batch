# SQLite Web Viewer Instructions

## Overview
A web-based SQLite database viewer using `sqlite-web` is now running for the `llm_video_batch.db` database.

## Access Information
- **URL**: http://localhost:8081
- **Database**: `data/llm_video_batch.db`
- **Server Status**: Running on port 8081

## Available Tables
The database contains the following tables:
- **images**: Image upload and processing information
- **prompts**: AI-generated prompts for video creation
- **videos**: Video generation metadata and status
- **sqlite_sequence**: SQLite internal sequence table

## Features Available

### 1. Table Browsing
- Navigate to any table to view its structure and data
- Paginated results for large datasets
- Column sorting and filtering

### 2. SQL Query Interface
- Execute custom SQL queries
- Syntax highlighting for SQL
- Export query results

### 3. Data Export
- Export table data or query results
- Multiple format support (CSV, JSON, etc.)

### 4. Schema Information
- View table schemas and relationships
- Index information
- Foreign key constraints

## Starting the Server

To start the sqlite-web server:

```bash
python3 -m sqlite_web data/llm_video_batch.db --host 0.0.0.0 --port 8081
```

## Common Queries

Here are some useful queries for this database:

### Image Statistics
```sql
SELECT status, COUNT(*) as count 
FROM images 
GROUP BY status;
```

### Video Generation Services
```sql
SELECT generation_service, COUNT(*) as count 
FROM videos 
GROUP BY generation_service;
```

### Recent Activity
```sql
SELECT * FROM images 
ORDER BY created_at DESC 
LIMIT 10;
```

### Join Images with Prompts
```sql
SELECT i.original_filename, p.video_prompt 
FROM images i 
LEFT JOIN prompts p ON i.id = p.image_id 
LIMIT 10;
```

## Security Notes
- The server is configured to accept connections from any host (0.0.0.0)
- This is suitable for development/internal use
- For production use, consider restricting access and using authentication

## Stopping the Server
Press `Ctrl+C` in the terminal where the server is running to stop it.

## Alternative Access
If you need to access the database programmatically, you can also use the MCP SQLite server that's already configured in this environment.
