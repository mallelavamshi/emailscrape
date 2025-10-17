# worker.py
import asyncio
import time
import pandas as pd
from jobs import JobManager, JobStatus, JobControl
from scraper_async import scrape_multiple_websites
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_job_async(job_id: str):
    """Process a single job with pause/stop support"""
    job_manager = JobManager()
    job = job_manager.get_job(job_id)
    
    if not job:
        logger.error(f"Job {job_id} not found")
        return
    
    logger.info(f"🚀 Starting job {job_id} - {job['filename']}")
    
    try:
        # Update to processing
        job_manager.update_job(job_id, {
            'status': JobStatus.PROCESSING.value,
            'started_at': pd.Timestamp.now().isoformat()
        })
        
        # Read the uploaded file
        filepath = os.path.join(job_manager.uploads_dir, job['filename'])
        excel_file = pd.ExcelFile(filepath)
        
        all_results = []
        total_sheets = len(job['selected_sheets'])
        
        for sheet_num, sheet_idx in enumerate(job['selected_sheets']):
            sheet_name = excel_file.sheet_names[sheet_idx]
            logger.info(f"📄 Processing sheet: {sheet_name}")
            
            # Check control signal
            control = job_manager.get_job_control(job_id)
            
            if control == JobControl.STOP.value:
                logger.warning(f"⏹️ Job {job_id} stopped by user")
                # Save partial results
                if all_results:
                    await save_partial_results(job_id, all_results, job_manager)
                job_manager.update_job(job_id, {
                    'status': JobStatus.STOPPED.value,
                    'completed_at': pd.Timestamp.now().isoformat()
                })
                return
            
            elif control == JobControl.PAUSE.value:
                logger.info(f"⏸️ Job {job_id} paused")
                job_manager.update_job(job_id, {'status': JobStatus.PAUSED.value})
                
                # Wait until resumed or stopped
                while True:
                    await asyncio.sleep(2)
                    control = job_manager.get_job_control(job_id)
                    
                    if control == JobControl.RUN.value:
                        logger.info(f"▶️ Job {job_id} resumed")
                        job_manager.update_job(job_id, {'status': JobStatus.PROCESSING.value})
                        break
                    elif control == JobControl.STOP.value:
                        logger.warning(f"⏹️ Job {job_id} stopped while paused")
                        if all_results:
                            await save_partial_results(job_id, all_results, job_manager)
                        job_manager.update_job(job_id, {
                            'status': JobStatus.STOPPED.value,
                            'completed_at': pd.Timestamp.now().isoformat()
                        })
                        return
            
            # Update progress
            job_manager.update_job(job_id, {
                'current_sheet': sheet_name,
                'progress': (sheet_num / total_sheets) * 100
            })
            
            df = excel_file.parse(sheet_name)
            
            if 'Website' not in df.columns or 'Title' not in df.columns:
                logger.warning(f"Sheet {sheet_name} missing required columns")
                continue
            
            # Prepare data for batch processing
            websites_data = []
            for _, row in df.iterrows():
                websites_data.append({
                    'company': row['Title'],
                    'website': row['Website'],
                    'phone': row.get('Phone Number', ''),
                    'city': sheet_name
                })
            
            job_manager.update_job(job_id, {'total_rows': len(websites_data)})
            
            # Process in smaller batches to check control signals frequently
            batch_size = 50  # Process 50 websites at a time
            for batch_start in range(0, len(websites_data), batch_size):
                # Check control again
                control = job_manager.get_job_control(job_id)
                if control in [JobControl.STOP.value, JobControl.PAUSE.value]:
                    break
                
                batch_end = min(batch_start + batch_size, len(websites_data))
                batch_data = websites_data[batch_start:batch_end]
                
                logger.info(f"⚡ Scraping batch {batch_start}-{batch_end} of {len(websites_data)}")
                
                batch_results = await scrape_multiple_websites(batch_data, max_concurrent=1000)
                all_results.extend(batch_results)
                
                # Update progress
                progress = ((sheet_num + (batch_end / len(websites_data))) / total_sheets) * 100
                job_manager.update_job(job_id, {
                    'progress': progress,
                    'current_row': batch_end
                })
            
            logger.info(f"✅ Sheet {sheet_name} complete: {len(all_results)} total results")
        
        # Save final results
        if all_results:
            results_df = pd.DataFrame(all_results)
            output_filename = f"scraped_{job['filename']}"
            output_path = os.path.join(job_manager.outputs_dir, output_filename)
            results_df.to_excel(output_path, index=False)
            
            total_emails = len([r for r in all_results 
                              if not r['Email'].startswith(('No', 'Error', 'Blocked'))])
            
            job_manager.update_job(job_id, {
                'status': JobStatus.COMPLETED.value,
                'completed_at': pd.Timestamp.now().isoformat(),
                'progress': 100,
                'total_emails': total_emails,
                'total_rows': len(results_df),
                'output_file': output_filename
            })
            
            logger.info(f"🎉 Job {job_id} completed! Found {total_emails} emails in {len(results_df)} rows")
        else:
            job_manager.update_job(job_id, {
                'status': JobStatus.FAILED.value,
                'completed_at': pd.Timestamp.now().isoformat(),
                'error': 'No results found'
            })
            
    except Exception as e:
        logger.error(f"❌ Job {job_id} failed: {str(e)}")
        job_manager.update_job(job_id, {
            'status': JobStatus.FAILED.value,
            'completed_at': pd.Timestamp.now().isoformat(),
            'error': str(e)
        })


async def save_partial_results(job_id: str, results: list, job_manager: JobManager):
    """Save partial results when job is stopped"""
    if not results:
        return
    
    job = job_manager.get_job(job_id)
    results_df = pd.DataFrame(results)
    output_filename = f"partial_{job['filename']}"
    output_path = os.path.join(job_manager.outputs_dir, output_filename)
    results_df.to_excel(output_path, index=False)
    
    total_emails = len([r for r in results 
                      if not r['Email'].startswith(('No', 'Error', 'Blocked'))])
    
    job_manager.update_job(job_id, {
        'total_emails': total_emails,
        'total_rows': len(results_df),
        'output_file': output_filename
    })
    
    logger.info(f"💾 Saved partial results: {len(results)} rows, {total_emails} emails")


def worker_loop():
    """Main worker loop"""
    job_manager = JobManager()
    logger.info("🚀 Async worker started - waiting for jobs...")
    
    while True:
        try:
            pending_jobs = job_manager.get_pending_jobs()
            
            if pending_jobs:
                job = pending_jobs[0]
                logger.info(f"📝 Found pending job: {job['job_id']} - {job['filename']}")
                asyncio.run(process_job_async(job['job_id']))
            else:
                time.sleep(5)
                
        except Exception as e:
            logger.error(f"❌ Worker error: {str(e)}")
            time.sleep(10)


if __name__ == "__main__":
    worker_loop()
