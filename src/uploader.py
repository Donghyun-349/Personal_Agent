# -*- coding: utf-8 -*-
import os
import logging
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GDriveUploader:
    def __init__(self, token_json: str = None):
        """
        token_json: JSON string of the token or path to token file (optional if env var set)
        """
        self.creds = None
        self.service = None
        # Updated scope to allow access to existing folders
        # 'drive.file' only allows access to files created by this app
        # 'drive' allows access to all files and folders
        self.scopes = ['https://www.googleapis.com/auth/drive']
        
        # Initialize credentials
        self.authenticate(token_json)

    def authenticate(self, token_json: str = None):
        """Authenticate with Google Drive API"""
        try:
            # 1. Try passed token_json
            token_data = token_json
            
            # 2. Fallback to Env Var
            if not token_data:
                token_data = os.getenv("GOOGLE_TOKEN_JSON")
            
            if not token_data:
                logger.warning("No token provided for Google Drive authentication.")
                return

            # Check if it's a file path or direct JSON string
            if os.path.isfile(token_data):
                self.creds = Credentials.from_authorized_user_file(token_data, self.scopes)
            else:
                try:
                    info = json.loads(token_data)
                    self.creds = Credentials.from_authorized_user_info(info, self.scopes)
                except json.JSONDecodeError:
                    # If it's not JSON, maybe it's a path that doesn't exist?
                    logger.error("Invalid token JSON string.")
                    return
            
            self.service = build('drive', 'v3', credentials=self.creds)
            logger.info("✅ Google Drive Authenticated")
            
        except Exception as e:
            logger.error(f"❌ Google Drive Authentication Failed: {e}")
            self.service = None

    def upload_file(self, file_path: str, folder_id: str, mime_type: str = None) -> str:
        """Upload a file to a specific Google Drive folder"""
        if not self.service:
            # Try re-auth if service is missing (though init should have handled it)
            logger.error("Google Drive service not initialized. Cannot upload.")
            return None

        filename = os.path.basename(file_path)
        
        if not mime_type:
            if filename.endswith('.pdf'):
                mime_type = 'application/pdf'
            elif filename.endswith('.md'):
                mime_type = 'text/markdown'
            elif filename.endswith('.html'):
                mime_type = 'text/html'
            else:
                mime_type = 'application/octet-stream'

        metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaFileUpload(file_path, mimetype=mime_type)

        try:
            file = self.service.files().create(
                body=metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"📤 Uploaded to Drive: {filename} (ID: {file_id})")
            return file_id
        except Exception as e:
            logger.error(f"❌ Failed to upload {filename}: {e}")
            return None
