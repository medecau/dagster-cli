#!/usr/bin/env python3
"""
Example: Submit a job and monitor its completion using dgc CLI.

This example demonstrates how to use the dgc CLI programmatically
from Python using subprocess.
"""

import subprocess
import json
import time
import sys


def run_dgc_command(args):
    """Run a dgc command and return the output."""
    cmd = ["dgc"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    
    return result.stdout


def main():
    # Check if authenticated
    print("Checking authentication status...")
    run_dgc_command(["auth", "status"])
    
    # List available jobs
    print("\nListing available jobs...")
    output = run_dgc_command(["job", "list", "--json"])
    jobs = json.loads(output)
    
    if not jobs:
        print("No jobs found!")
        return
    
    # Display jobs
    print(f"Found {len(jobs)} jobs:")
    for job in jobs[:5]:  # Show first 5
        print(f"  - {job['name']}")
    
    # Example: Submit a job (commented out to avoid accidental runs)
    # job_name = jobs[0]['name']
    # print(f"\nSubmitting job: {job_name}")
    # output = run_dgc_command(["job", "run", job_name, "--yes", "--json"])
    # run_data = json.loads(output)
    # run_id = run_data['run_id']
    # 
    # print(f"Job submitted with run ID: {run_id}")
    # 
    # # Monitor the run
    # print("\nMonitoring run status...")
    # while True:
    #     output = run_dgc_command(["run", "view", run_id, "--json"])
    #     run = json.loads(output)
    #     status = run['status']
    #     
    #     print(f"Status: {status}")
    #     
    #     if status in ['SUCCESS', 'FAILURE', 'CANCELED']:
    #         break
    #     
    #     time.sleep(5)  # Check every 5 seconds
    # 
    # print(f"\nRun completed with status: {status}")


if __name__ == "__main__":
    main()