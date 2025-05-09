#!/usr/bin/env python3
import os
import sqlite3
import tempfile
import json
import base64
import logging
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, g

# Import Vuforia client from your paste
from cloud_target_webapi_client import VuforiaVwsClient, CloudTargetWebAPIClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask application
app = Flask(__name__)

# Configuration
# VUFORIA_ACCESS_KEY = os.environ.get('VUFORIA_ACCESS_KEY', '')
VUFORIA_ACCESS_KEY = 'dc1a37f25bfd3c7ed5ebdeed20cee19c62a8b415'
# VUFORIA_SECRET_KEY = os.environ.get('VUFORIA_SECRET_KEY', '')
VUFORIA_SECRET_KEY = '8980423c33e37777b8dc9360a6c4e57417388eda'
DATABASE_PATH = os.environ.get('DATABASE_PATH', 'vuforia.db')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')

# Make sure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database setup
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            width REAL NOT NULL,
            image_path TEXT NOT NULL,
            metadata TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        db.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_id TEXT UNIQUE NOT NULL,
            summary TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        db.commit()

# Initialize the database
init_db()

# Get Vuforia client
def get_vuforia_client():
    vws_client = VuforiaVwsClient(
        "https://vws.vuforia.com",
        VUFORIA_ACCESS_KEY,
        VUFORIA_SECRET_KEY
    )
    return CloudTargetWebAPIClient(vws_client)

# API Routes
@app.route('/targets', methods=['POST'])
def create_target():
    if 'image' not in request.files:
        return jsonify({'error': 'No image file'}), 400
    
    file = request.files['image']
    name = request.form.get('name')
    width = request.form.get('width')
    
    if not name or not width:
        return jsonify({'error': 'Name and width are required'}), 400
    
    # Save image to disk
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    # Process optional parameters
    metadata = request.form.get('metadata')
    metadata_base64 = None
    if metadata:
        metadata_base64 = base64.b64encode(metadata.encode()).decode()
    
    active = request.form.get('active')
    active_flag = None
    if active:
        active_flag = active.lower() in ['true', '1', 'yes']
    
    try:
        # Create target in Vuforia
        client = get_vuforia_client()
        response = client.create_target(
            image=Path(filepath),
            name=name,
            width=float(width),
            metadata_base64=metadata_base64,
            active=active_flag
        )
        
        # Extract target ID
        response_data = response.json()
        target_id = response_data.get('target_id')
        
        # Store in database
        db = get_db()
        db.execute(
            "INSERT INTO targets (target_id, name, width, image_path, metadata, active) VALUES (?, ?, ?, ?, ?, ?)",
            (target_id, name, width, filepath, metadata, 1 if active_flag else 0)
        )
        db.commit()
        
        return jsonify({
            'success': True,
            'target_id': target_id,
            'status': response_data
        })
        
    except Exception as e:
        logger.error(f"Error creating target: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/targets', methods=['GET'])
def get_targets():
    try:
        # Get target list from Vuforia
        client = get_vuforia_client()
        response = client.list_targets()
        vuforia_targets = response.json()

        # Get local database info to enrich the response
        db = get_db()
        targets = db.execute("SELECT * FROM targets").fetchall()
        local_targets = {t['target_id']: dict(t) for t in targets}

        # Combine Vuforia data with local data
        result = []
        for target_id in vuforia_targets.get('results', []):
            target_data = local_targets.get(target_id, {'target_id': target_id})
            result.append(target_data)

        return jsonify({'targets': result})
    except Exception as e:
        logger.error(f"Error listing targets: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/targets/<target_id>', methods=['GET'])
def get_target(target_id):
    try:
        db = get_db()
        target = db.execute("SELECT * FROM targets WHERE target_id = ?", (target_id,)).fetchone()
        
        if not target:
            return jsonify({'error': 'Target not found'}), 404
        
        # Get details from Vuforia
        client = get_vuforia_client()
        response = client.get_target(target_id)
        
        result = dict(target)
        result['vuforia_data'] = response.json()
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error getting target: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/targets/<target_id>/summary', methods=['GET'])
def get_target_summary(target_id):
    try:
        db = get_db()
        target = db.execute("SELECT * FROM targets WHERE target_id = ?", (target_id,)).fetchone()
        
        if not target:
            return jsonify({'error': 'Target not found'}), 404
        
        # Check if we already have a summary in the database
        summary = db.execute("SELECT * FROM summaries WHERE target_id = ?", (target_id,)).fetchone()
        
        # Get fresh summary from Vuforia
        client = get_vuforia_client()
        response = client.get_target_report(target_id)
        summary_data = response.json()
        
        # Store in database
        if summary:
            db.execute(
                "UPDATE summaries SET summary = ?, created_at = ? WHERE target_id = ?",
                (json.dumps(summary_data), datetime.now(), target_id)
            )
        else:
            db.execute(
                "INSERT INTO summaries (target_id, summary) VALUES (?, ?)",
                (target_id, json.dumps(summary_data))
            )
        db.commit()
        
        return jsonify(summary_data)
    except Exception as e:
        logger.error(f"Error getting target summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/targets/<target_id>', methods=['DELETE'])
def delete_target(target_id):
    try:
        db = get_db()
        target = db.execute("SELECT * FROM targets WHERE target_id = ?", (target_id,)).fetchone()
        
        if not target:
            return jsonify({'error': 'Target not found'}), 404
        
        # Delete from Vuforia
        client = get_vuforia_client()
        response = client.delete_target(target_id)
        
        # Delete from database
        db.execute("DELETE FROM targets WHERE target_id = ?", (target_id,))
        db.execute("DELETE FROM summaries WHERE target_id = ?", (target_id,))
        db.commit()
        
        # Optionally delete the image file
        try:
            if target['image_path'] and os.path.exists(target['image_path']):
                os.remove(target['image_path'])
        except:
            logger.warning(f"Could not delete image file for target {target_id}")
        
        return jsonify({
            'success': True,
            'status': response.json()
        })
    except Exception as e:
        logger.error(f"Error deleting target: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/database/summary', methods=['GET'])
def get_database_summary():
    try:
        client = get_vuforia_client()
        response = client.get_database_report()
        return jsonify(response.json())
    except Exception as e:
        logger.error(f"Error getting database summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting Vuforia SQLite Server with database at {DATABASE_PATH}")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    
    if not VUFORIA_ACCESS_KEY or not VUFORIA_SECRET_KEY:
        logger.warning("VUFORIA_ACCESS_KEY and/or VUFORIA_SECRET_KEY environment variables not set!")
    
    app.run(host='0.0.0.0', port=8000, debug=True)