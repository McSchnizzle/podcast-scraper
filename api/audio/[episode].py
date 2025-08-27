"""
Vercel Function: Audio File Server
Serves podcast audio files directly from deployed files
"""

import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import unquote

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Serve audio files for podcast episodes"""
        try:
            # Extract episode filename from URL path
            path_parts = self.path.split('/')
            if len(path_parts) < 3:
                self.send_error(404, "Audio file not found")
                return
                
            episode_filename = unquote(path_parts[-1])
            
            # Look for audio file in deployed directory structure
            audio_path = f"daily_digests/{episode_filename}"
            
            if not os.path.exists(audio_path):
                self.send_error(404, f"Audio file not found: {episode_filename}")
                return
            
            # Get file size
            file_size = os.path.getsize(audio_path)
            
            # Set headers for audio streaming
            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg')
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'public, max-age=86400')  # Cache for 24 hours
            self.send_header('Content-Disposition', f'inline; filename="{episode_filename}"')
            self.end_headers()
            
            # Stream the file
            with open(audio_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                        
        except Exception as e:
            self.send_error(500, f"Error serving audio: {str(e)}")