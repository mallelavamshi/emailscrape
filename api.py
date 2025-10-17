# api.py
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional
import os
import pandas as pd
from datetime import datetime
from jobs import JobManager, JobStatus, JobControl
import json
import asyncio
from pathlib import Path

app = FastAPI(
    title="Email Scraper API",
    description="API for email scraping with real-time job management",
    version="1.0.0"
)

# CORS Configuration - Updated with Lovable domain and server IP
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://preview--emailscrape.lovable.app",
    "https://emailscrape.lovable.app",
    "http://178.16.141.15",
    "http://178.16.141.15:3000",
    "http://178.16.141.15:5173",
    # Add your custom domain when you connect it
    # "https://yourdomain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_manager = JobManager()

# WebSocket Connection Manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# ==================== FILE UPLOAD ENDPOINTS ====================

@app.post("/api/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload multiple Excel files"""
    uploaded = []
    
    for file in files:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(400, detail=f"Invalid file type: {file.filename}")
        
        filepath = os.path.join(job_manager.uploads_dir, file.filename)
        
        # Save file
        with open(filepath, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        file_info = {
            'filename': file.filename,
            'size': os.path.getsize(filepath),
            'uploaded_at': datetime.now().isoformat()
        }
        uploaded.append(file_info)
        
        # Broadcast update
        await manager.broadcast({
            'type': 'file_uploaded',
            'data': file_info
        })
    
    return {
        "message": f"Uploaded {len(uploaded)} file(s)",
        "files": uploaded
    }

@app.get("/api/files/uploaded")
async def get_uploaded_files():
    """Get list of all uploaded files"""
    files = job_manager.get_uploaded_files()
    return {"files": files}

@app.get("/api/files/uploaded/{filename}")
async def download_uploaded_file(filename: str):
    """Download a specific uploaded file"""
    filepath = os.path.join(job_manager.uploads_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(404, detail="File not found")
    
    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )

@app.delete("/api/files/uploaded/{filename}")
async def delete_uploaded_file(filename: str):
    """Delete an uploaded file"""
    success = job_manager.delete_uploaded_file(filename)
    
    if not success:
        raise HTTPException(404, detail="File not found")
    
    await manager.broadcast({
        'type': 'file_deleted',
        'data': {'filename': filename}
    })
    
    return {"message": "File deleted successfully"}

@app.get("/api/files/uploaded/{filename}/sheets")
async def get_file_sheets(filename: str):
    """Get sheet names from an uploaded Excel file"""
    filepath = os.path.join(job_manager.uploads_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(404, detail="File not found")
    
    try:
        excel_file = pd.ExcelFile(filepath)
        sheets = excel_file.sheet_names
        return {"filename": filename, "sheets": sheets}
    except Exception as e:
        raise HTTPException(400, detail=f"Error reading file: {str(e)}")

# ==================== OUTPUT FILES ENDPOINTS ====================

@app.get("/api/files/output")
async def get_output_files():
    """Get list of all output files"""
    files = job_manager.get_output_files()
    return {"files": files}

@app.get("/api/files/output/{filename}")
async def download_output_file(filename: str):
    """Download a specific output file"""
    filepath = os.path.join(job_manager.outputs_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(404, detail="File not found")
    
    return FileResponse(
        path=filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )

@app.delete("/api/files/output/{filename}")
async def delete_output_file(filename: str):
    """Delete an output file"""
    success = job_manager.delete_output_file(filename)
    
    if not success:
        raise HTTPException(404, detail="File not found")
    
    await manager.broadcast({
        'type': 'output_deleted',
        'data': {'filename': filename}
    })
    
    return {"message": "File deleted successfully"}

# ==================== JOB MANAGEMENT ENDPOINTS ====================

@app.post("/api/jobs/create")
async def create_job(filename: str, selected_sheets: List[int]):
    """Create a new scraping job"""
    filepath = os.path.join(job_manager.uploads_dir, filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(404, detail="File not found")
    
    job_id = job_manager.create_job(filename, selected_sheets)
    job = job_manager.get_job(job_id)
    
    await manager.broadcast({
        'type': 'job_created',
        'data': job
    })
    
    return {
        "message": "Job created successfully",
        "job_id": job_id,
        "job": job
    }

@app.get("/api/jobs")
async def get_all_jobs():
    """Get all jobs"""
    jobs = job_manager.get_all_jobs()
    return {"jobs": jobs}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get specific job details"""
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(404, detail="Job not found")
    
    return {"job": job}

@app.put("/api/jobs/{job_id}/control")
async def control_job(job_id: str, action: str):
    """Control job execution (run/pause/stop)"""
    if action not in ['run', 'pause', 'stop']:
        raise HTTPException(400, detail="Invalid action")
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, detail="Job not found")
    
    control = JobControl[action.upper()]
    job_manager.set_job_control(job_id, control)
    
    updated_job = job_manager.get_job(job_id)
    
    await manager.broadcast({
        'type': 'job_control',
        'data': updated_job
    })
    
    return {
        "message": f"Job {action} command sent",
        "job": updated_job
    }

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job"""
    success = job_manager.delete_job(job_id)
    
    if not success:
        raise HTTPException(404, detail="Job not found")
    
    await manager.broadcast({
        'type': 'job_deleted',
        'data': {'job_id': job_id}
    })
    
    return {"message": "Job deleted successfully"}

# ==================== STATISTICS ENDPOINT ====================

@app.get("/api/stats")
async def get_stats():
    """Get dashboard statistics"""
    uploaded_count = len(job_manager.get_uploaded_files())
    output_count = len(job_manager.get_output_files())
    all_jobs = job_manager.get_all_jobs()
    
    active_jobs = len([j for j in all_jobs if j['status'] in ['processing', 'pending']])
    completed_jobs = len([j for j in all_jobs if j['status'] == 'completed'])
    failed_jobs = len([j for j in all_jobs if j['status'] == 'failed'])
    
    return {
        "uploaded_files": uploaded_count,
        "output_files": output_count,
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "total_jobs": len(all_jobs)
    }

# ==================== WEBSOCKET FOR REAL-TIME UPDATES ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and send periodic updates
            await asyncio.sleep(2)
            
            # Send job updates
            jobs = job_manager.get_all_jobs()
            active_jobs = [j for j in jobs if j['status'] in ['processing', 'pending', 'paused']]
            
            if active_jobs:
                await websocket.send_json({
                    'type': 'job_update',
                    'data': active_jobs
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ==================== HEALTH CHECK ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Email Scraper API",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "directories": {
            "uploads": os.path.exists(job_manager.uploads_dir),
            "outputs": os.path.exists(job_manager.outputs_dir),
            "jobs": os.path.exists(job_manager.jobs_dir)
        }
    }
