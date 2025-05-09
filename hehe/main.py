#!/usr/bin/env python3
import os
import logging
import sqlite3
from pathlib import Path

# Import the Flask application
from vuforia_client.vuforia_server import app, Config, init_db

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_db_schema():
    # Check if schema.sql exists
    schema_path = Path('schema.sql')
    if not schema_path.exists():
        logger.error("schema.sql not found. Please create the schema file.")
        return False
    
    try:
        # Create database if it doesn't exist
        db_path = Path(Config.DATABASE_PATH)
        
        # Check if database already exists
        if db_path.exists():
            logger.info(f"Database already exists at {db_path}")
        else:
            logger.info(f"Creating new database at {db_path}")
            conn = sqlite3.connect(db_path)
            
            # Read and execute schema.sql
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
                conn.executescript(schema_sql)
            
            conn.commit()
            conn.close()
            logger.info("Database schema created successfully")
        
        return True
    except Exception as e:
        logger.error(f"Error creating database schema: {str(e)}")
        return False

def check_environment():
    # Check if required environment variables are set
    required_vars = ['VUFORIA_ACCESS_KEY', 'VUFORIA_SECRET_KEY']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables before starting the server.")
        return False
    
    # Create upload directory if it doesn't exist
    upload_dir = Path(Config.UPLOAD_FOLDER)
    if not upload_dir.exists():
        logger.info(f"Creating upload directory at {upload_dir}")
        upload_dir.mkdir(parents=True)
    
    return True

if __name__ == '__main__':
    logger.info("Starting Vuforia SQLite Server...")
    
    # Check environment
    if not check_environment():
        logger.error("Environment check failed. Exiting.")
        exit(1)
    
    # Create database schema
    if not create_db_schema():
        logger.error("Database initialization failed. Exiting.")
        exit(1)
    
    # Start the Flask server
    logger.info("Starting Flask server...")
    app.run(host='0.0.0.0', port=5000)