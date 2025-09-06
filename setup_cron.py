#!/usr/bin/env python3
"""
Cron Job Setup for YouTube Transcript Processing
Sets up automated YouTube transcript processing every 6 hours
"""

import os
import subprocess
import sys
from pathlib import Path


def get_project_directory():
    """Get the absolute path to the podcast scraper project directory"""
    return Path(__file__).parent.absolute()


def get_python_executable():
    """Get the Python executable currently in use"""
    return sys.executable


def create_cron_script():
    """Create the actual script that will be run by cron"""
    project_dir = get_project_directory()
    python_exe = get_python_executable()

    script_content = f"""#!/bin/bash
# YouTube Transcript Processing Cron Job
# Runs every 6 hours to process YouTube episodes from last 7 days

# Change to project directory
cd "{project_dir}"

# Set up logging
LOG_FILE="{project_dir}/logs/youtube_cron_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "{project_dir}/logs"

# Run YouTube processor with comprehensive logging
echo "=== YouTube Cron Job Started: $(date) ===" >> "$LOG_FILE"
echo "Project Directory: {project_dir}" >> "$LOG_FILE"
echo "Python Executable: {python_exe}" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Process YouTube episodes from last 7 days (168 hours)
{python_exe} youtube_processor.py --process-new --hours-back 168 >> "$LOG_FILE" 2>&1

# Log completion
echo "" >> "$LOG_FILE"
echo "=== YouTube Cron Job Completed: $(date) ===" >> "$LOG_FILE"
echo "Exit Code: $?" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Keep only last 10 log files to prevent disk space issues
find "{project_dir}/logs" -name "youtube_cron_*.log" -type f | sort | head -n -10 | xargs -r rm

# Optional: Send notification on failure (uncomment if needed)
# if [ $? -ne 0 ]; then
#     echo "YouTube transcript processing failed at $(date)" | mail -s "Podcast Scraper Alert" your-email@domain.com
# fi
"""

    script_path = project_dir / "youtube_cron_job.sh"
    with open(script_path, "w") as f:
        f.write(script_content)

    # Make script executable
    os.chmod(script_path, 0o755)

    print(f"✅ Created cron script: {script_path}")
    return script_path


def get_cron_schedule():
    """Generate cron schedule - every 6 hours"""
    return "0 */6 * * *"


def install_cron_job():
    """Install the cron job"""
    try:
        script_path = create_cron_script()
        cron_schedule = get_cron_schedule()

        # Create cron entry
        cron_line = f"{cron_schedule} {script_path}\n"

        print("\n📋 Cron Job Configuration:")
        print(f"Schedule: Every 6 hours (at minute 0 of hours 0, 6, 12, 18)")
        print(f"Times: 12:00 AM, 6:00 AM, 12:00 PM, 6:00 PM daily")
        print(f"Command: {script_path}")
        print(f"Lookback: 7 days (168 hours) to catch any missed episodes")

        # Get current cron jobs
        try:
            current_cron = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True, timeout=10
            )
            existing_jobs = current_cron.stdout if current_cron.returncode == 0 else ""
        except:
            existing_jobs = ""

        # Check if our job already exists
        if str(script_path) in existing_jobs:
            print("\n⚠️ YouTube cron job already exists!")
            print("Run with --remove first to remove existing job, then --install")
            return False

        # Add our job to existing jobs
        new_cron = existing_jobs.rstrip() + "\n" if existing_jobs.strip() else ""
        new_cron += f"# YouTube Transcript Processing - Every 6 hours\n"
        new_cron += cron_line

        # Install new crontab
        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(new_cron)

        if process.returncode == 0:
            print("\n✅ Successfully installed YouTube cron job!")
            print(f"Next runs: Every 6 hours starting from next hour boundary")
            print(f"Logs will be saved to: {get_project_directory()}/logs/")
            return True
        else:
            print("\n❌ Failed to install cron job")
            return False

    except Exception as e:
        print(f"\n❌ Error installing cron job: {e}")
        return False


def remove_cron_job():
    """Remove the YouTube cron job"""
    try:
        script_path = get_project_directory() / "youtube_cron_job.sh"

        # Get current cron jobs
        current_cron = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=10
        )

        if current_cron.returncode != 0:
            print("No cron jobs found")
            return True

        # Remove our job lines
        lines = current_cron.stdout.split("\n")
        new_lines = []
        skip_next = False

        for line in lines:
            if skip_next and str(script_path) in line:
                skip_next = False
                continue
            elif "YouTube Transcript Processing" in line:
                skip_next = True
                continue
            else:
                new_lines.append(line)

        # Install cleaned crontab
        new_cron = "\n".join(new_lines).strip()
        if new_cron:
            new_cron += "\n"

        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(new_cron)

        if process.returncode == 0:
            print("✅ Successfully removed YouTube cron job")

            # Also remove the script file
            if script_path.exists():
                script_path.unlink()
                print(f"🗑️ Removed script file: {script_path}")

            return True
        else:
            print("❌ Failed to remove cron job")
            return False

    except Exception as e:
        print(f"❌ Error removing cron job: {e}")
        return False


def show_cron_status():
    """Show current cron job status"""
    try:
        script_path = get_project_directory() / "youtube_cron_job.sh"

        # Check if script exists
        print(f"Script file: {'✅ Exists' if script_path.exists() else '❌ Missing'}")

        # Check current cron jobs
        current_cron = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=10
        )

        if current_cron.returncode == 0:
            if str(script_path) in current_cron.stdout:
                print("Cron job: ✅ Installed")

                # Show relevant lines
                for line in current_cron.stdout.split("\n"):
                    if "YouTube" in line or str(script_path) in line:
                        print(f"  {line}")
            else:
                print("Cron job: ❌ Not installed")
        else:
            print("Cron job: ❌ Cannot check (crontab not accessible)")

        # Show recent logs
        logs_dir = get_project_directory() / "logs"
        if logs_dir.exists():
            log_files = sorted(logs_dir.glob("youtube_cron_*.log"))
            if log_files:
                print(f"\nRecent logs ({len(log_files)} files):")
                for log_file in log_files[-3:]:  # Show last 3
                    print(f"  {log_file.name}")
            else:
                print("\nNo log files found")
        else:
            print("\nLogs directory not created yet")

    except Exception as e:
        print(f"❌ Error checking cron status: {e}")


def test_youtube_processor():
    """Test the YouTube processor to make sure it works"""
    try:
        project_dir = get_project_directory()
        python_exe = get_python_executable()

        print("🧪 Testing YouTube processor...")

        # Change to project directory
        os.chdir(project_dir)

        # Test with stats command (quick test)
        result = subprocess.run(
            [python_exe, "youtube_processor.py", "--stats"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("✅ YouTube processor test successful")
            print("Output:")
            print(result.stdout)
            return True
        else:
            print("❌ YouTube processor test failed")
            print("Error:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"❌ Error testing YouTube processor: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("YouTube Cron Job Manager")
        print("=======================")
        print()
        print("Usage:")
        print("  python3 setup_cron.py --install   # Install cron job (every 6 hours)")
        print("  python3 setup_cron.py --remove    # Remove cron job")
        print("  python3 setup_cron.py --status    # Show current status")
        print("  python3 setup_cron.py --test      # Test YouTube processor")
        print()
        print("The cron job will:")
        print("  - Run every 6 hours (12AM, 6AM, 12PM, 6PM)")
        print("  - Check for YouTube episodes from last 7 days")
        print("  - Download transcripts using YouTube API")
        print("  - Commit and push transcripts to GitHub")
        print("  - Log all activity to logs/ directory")
        return

    action = sys.argv[1]

    if action == "--install":
        if install_cron_job():
            print(
                "\n🎉 Setup complete! YouTube transcripts will be processed automatically."
            )
            print("💡 Tip: Use 'python3 setup_cron.py --status' to check status")

    elif action == "--remove":
        remove_cron_job()

    elif action == "--status":
        show_cron_status()

    elif action == "--test":
        test_youtube_processor()

    else:
        print(f"Unknown action: {action}")
        print("Use --install, --remove, --status, or --test")


if __name__ == "__main__":
    main()
