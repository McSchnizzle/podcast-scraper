#!/usr/bin/env python3
"""
Setup Local YouTube Processing Automation
Creates launchd plist for macOS or crontab entry for Linux
"""

import os
import platform
import subprocess
import sys
from pathlib import Path


def create_macos_launchd():
    """Create macOS launchd plist for YouTube processing"""
    project_dir = Path(__file__).parent.absolute()

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.podcast-scraper.youtube</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{project_dir}/youtube_processor.py</string>
        <string>--process-new</string>
        <string>--hours-back</string>
        <string>6</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{project_dir}</string>

    <key>StandardOutPath</key>
    <string>{project_dir}/logs/youtube_processor.log</string>

    <key>StandardErrorPath</key>
    <string>{project_dir}/logs/youtube_processor_error.log</string>

    <key>StartInterval</key>
    <integer>21600</integer>

    <key>RunAtLoad</key>
    <false/>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
        <key>PYTHONPATH</key>
        <string>{project_dir}</string>
    </dict>

    <key>KeepAlive</key>
    <false/>

    <key>Disabled</key>
    <false/>
</dict>
</plist>"""

    # Ensure logs directory exists
    (project_dir / "logs").mkdir(exist_ok=True)

    # Write plist file
    home_dir = Path.home()
    launchagents_dir = home_dir / "Library" / "LaunchAgents"
    launchagents_dir.mkdir(exist_ok=True)

    plist_path = launchagents_dir / "com.podcast-scraper.youtube.plist"

    with open(plist_path, "w") as f:
        f.write(plist_content)

    print(f"✅ Created launchd plist: {plist_path}")

    # Load the plist
    try:
        subprocess.run(["launchctl", "load", str(plist_path)], check=True)
        print("✅ Loaded YouTube processing service")

        # Start immediately for testing
        subprocess.run(
            ["launchctl", "start", "com.podcast-scraper.youtube"], check=True
        )
        print("✅ Started YouTube processing service")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error loading service: {e}")
        print("You can manually load it with:")
        print(f"  launchctl load {plist_path}")

    return plist_path


def create_linux_crontab():
    """Create Linux crontab entry for YouTube processing"""
    project_dir = Path(__file__).parent.absolute()

    cron_command = f"0 */6 * * * cd {project_dir} && /usr/bin/python3 youtube_processor.py --process-new --hours-back 6 >> logs/youtube_processor.log 2>&1"

    # Ensure logs directory exists
    (project_dir / "logs").mkdir(exist_ok=True)

    print("📋 Add this line to your crontab (run 'crontab -e'):")
    print(f"  {cron_command}")
    print("\nThis will run YouTube processing every 6 hours.")

    # Try to add automatically
    try:
        # Get current crontab
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current_crontab = result.stdout if result.returncode == 0 else ""

        # Check if entry already exists
        if "youtube_processor.py" not in current_crontab:
            new_crontab = current_crontab + "\n" + cron_command + "\n"

            # Write new crontab
            process = subprocess.Popen(
                ["crontab", "-"], stdin=subprocess.PIPE, text=True
            )
            process.communicate(new_crontab)

            if process.returncode == 0:
                print("✅ Added to crontab automatically")
            else:
                print("❌ Failed to add to crontab automatically")
        else:
            print("✅ YouTube processing already in crontab")

    except Exception as e:
        print(f"❌ Could not modify crontab automatically: {e}")


def create_git_automation():
    """Create git automation script for committing YouTube updates"""
    project_dir = Path(__file__).parent.absolute()

    git_script_content = f"""#!/bin/bash
# LOCAL ONLY: YouTube Transcript Processing
# Uses YouTube Transcript API, pushes transcripts to GitHub repo

cd "{project_dir}"

echo "🎬 LOCAL: Starting YouTube transcript processing..."

# Use YouTube Transcript API to get transcripts (no video download)
python3 youtube_processor.py --process-new --hours-back 6

# Check if there are NEW transcripts to commit
if [[ -n $(git status --porcelain) ]]; then
    echo "📝 LOCAL: Committing new YouTube transcripts..."

    # Add only YouTube database and transcripts
    git add youtube_transcripts.db
    git add transcripts/
    git add transcripts/digested/

    # Simple commit message
    commit_msg="LOCAL: YouTube transcripts - $(date '+%Y-%m-%d %H:%M')

New YouTube episodes transcribed and ready for GitHub Actions digest processing"

    git commit -m "$commit_msg"

    # Push to GitHub for GitHub Actions to pick up
    echo "🚀 LOCAL: Pushing transcripts to GitHub..."
    git push origin main

    echo "✅ LOCAL: YouTube transcripts pushed"
    echo "🤖 NEXT: GitHub Actions will generate digest from all 'transcribed' episodes"
else
    echo "ℹ️  LOCAL: No new YouTube transcripts to commit"
fi
"""

    git_script_path = project_dir / "youtube_git_automation.sh"

    with open(git_script_path, "w") as f:
        f.write(git_script_content)

    # Make executable
    os.chmod(git_script_path, 0o755)

    print(f"✅ Created git automation script: {git_script_path}")
    return git_script_path


def main():
    """Setup local YouTube processing automation"""
    print("🤖 Setting up Local YouTube Processing Automation")
    print("=" * 50)

    system = platform.system()

    if system == "Darwin":  # macOS
        print("🍎 Detected macOS - setting up launchd service")
        plist_path = create_macos_launchd()

        print(f"\n📋 LaunchAgent created:")
        print(f"  Service: com.podcast-scraper.youtube")
        print(f"  Interval: Every 6 hours")
        print(f"  Logs: logs/youtube_processor.log")

        print(f"\n⚙️  Management commands:")
        print(f"  Start:   launchctl start com.podcast-scraper.youtube")
        print(f"  Stop:    launchctl stop com.podcast-scraper.youtube")
        print(f"  Unload:  launchctl unload {plist_path}")

    elif system == "Linux":
        print("🐧 Detected Linux - setting up crontab entry")
        create_linux_crontab()

    else:
        print(f"❓ Unsupported system: {system}")
        print("Please set up YouTube processing manually")
        return

    # Create git automation script for both systems
    git_script = create_git_automation()

    print(f"\n🔄 Git Automation:")
    print(f"  Script: {git_script}")
    print(f"  Usage: ./youtube_git_automation.sh")

    print(f"\n✅ Local YouTube automation setup complete!")
    print(f"🚀 GitHub Actions will continue handling RSS feeds")
    print(f"🎬 Local system will handle YouTube processing every 6 hours")


if __name__ == "__main__":
    main()
