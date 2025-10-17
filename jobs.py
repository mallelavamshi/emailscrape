# jobs.py
import json
import os
from datetime import datetime
from enum import Enum
import uuid

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"

class JobControl(Enum):
    RUN = "run"
    PAUSE = "pause"
    STOP = "stop"

class JobManager:
    def __init__(self, jobs_dir="jobs", outputs_dir="outputs", uploads_dir="uploaded_files", control_dir=".control"):
        self.jobs_dir = jobs_dir
        self.outputs_dir = outputs_dir
        self.uploads_dir = uploads_dir
        self.control_dir = control_dir
        
        # Create directories
        os.makedirs(jobs_dir, exist_ok=True)
        os.makedirs(outputs_dir, exist_ok=True)
        os.makedirs(uploads_dir, exist_ok=True)
        os.makedirs(control_dir, exist_ok=True)
    
    def create_job(self, filename, selected_sheets):
        """Create a new job"""
        job_id = str(uuid.uuid4())
        job = {
            'job_id': job_id,
            'filename': filename,
            'selected_sheets': selected_sheets,
            'status': JobStatus.PENDING.value,
            'control': JobControl.RUN.value,
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'progress': 0,
            'current_sheet': None,
            'current_row': 0,
            'total_rows': 0,
            'total_emails': 0,
            'error': None,
            'output_file': None,
            'partial_results': []  # Store partial results
        }
        
        job_file = os.path.join(self.jobs_dir, f"{job_id}.json")
        with open(job_file, 'w') as f:
            json.dump(job, f, indent=2)
        
        return job_id
    
    def get_job(self, job_id):
        """Get job details"""
        job_file = os.path.join(self.jobs_dir, f"{job_id}.json")
        if os.path.exists(job_file):
            with open(job_file, 'r') as f:
                return json.load(f)
        return None
    
    def update_job(self, job_id, updates):
        """Update job status"""
        job = self.get_job(job_id)
        if job:
            job.update(updates)
            job_file = os.path.join(self.jobs_dir, f"{job_id}.json")
            with open(job_file, 'w') as f:
                json.dump(job, f, indent=2)
    
    def set_job_control(self, job_id, control: JobControl):
        """Set job control signal (pause/stop/run)"""
        self.update_job(job_id, {'control': control.value})
    
    def get_job_control(self, job_id) -> str:
        """Get current control signal"""
        job = self.get_job(job_id)
        return job.get('control', JobControl.RUN.value) if job else JobControl.RUN.value
    
    def delete_job(self, job_id):
        """Delete a job"""
        job_file = os.path.join(self.jobs_dir, f"{job_id}.json")
        if os.path.exists(job_file):
            os.remove(job_file)
            return True
        return False
    
    def get_all_jobs(self):
        """Get all jobs"""
        jobs = []
        for filename in os.listdir(self.jobs_dir):
            if filename.endswith('.json'):
                job_id = filename[:-5]
                job = self.get_job(job_id)
                if job:
                    jobs.append(job)
        
        jobs.sort(key=lambda x: x['created_at'], reverse=True)
        return jobs
    
    def get_pending_jobs(self):
        """Get all pending jobs"""
        return [j for j in self.get_all_jobs() if j['status'] == JobStatus.PENDING.value]
    
    def get_uploaded_files(self):
        """Get list of uploaded files"""
        files = []
        for filename in os.listdir(self.uploads_dir):
            if filename.endswith(('.xlsx', '.xls')):
                filepath = os.path.join(self.uploads_dir, filename)
                files.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': os.path.getsize(filepath),
                    'uploaded_at': datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
                })
        files.sort(key=lambda x: x['uploaded_at'], reverse=True)
        return files
    
    def delete_uploaded_file(self, filename):
        """Delete an uploaded file"""
        filepath = os.path.join(self.uploads_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    
    def get_output_files(self):
        """Get list of output files"""
        files = []
        for filename in os.listdir(self.outputs_dir):
            if filename.endswith(('.xlsx', '.xls')):
                filepath = os.path.join(self.outputs_dir, filename)
                files.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': os.path.getsize(filepath),
                    'created_at': datetime.fromtimestamp(os.path.getctime(filepath)).isoformat()
                })
        files.sort(key=lambda x: x['created_at'], reverse=True)
        return files
    
    def delete_output_file(self, filename):
        """Delete an output file"""
        filepath = os.path.join(self.outputs_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
