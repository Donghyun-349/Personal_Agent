# -*- coding: utf-8 -*-
"""
OAuth 사용자 계정 확인 스크립트
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from uploader import GDriveUploader

def check_oauth_user():
    print("=" * 60)
    print("OAuth 사용자 계정 확인")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    try:
        uploader = GDriveUploader()
        
        if uploader.service:
            # Get user info
            about = uploader.service.about().get(fields="user").execute()
            user = about.get('user', {})
            
            print(f"\n✅ 인증된 Google 계정:")
            print(f"   이메일: {user.get('emailAddress', 'N/A')}")
            print(f"   이름: {user.get('displayName', 'N/A')}")
            
            print(f"\n💡 이 이메일 주소에 Google Drive 폴더 편집자 권한을 부여하세요!")
            print(f"   폴더 ID: {os.getenv('GOOGLE_DRIVE_FOLDER_ID')}")
            
        else:
            print("❌ 인증 실패")
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_oauth_user()
