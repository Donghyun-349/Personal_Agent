# -*- coding: utf-8 -*-
"""
Google Drive 폴더 목록 및 접근 테스트
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

def test_folder_access():
    print("=" * 60)
    print("Google Drive 폴더 접근 테스트")
    print("=" * 60)
    
    load_dotenv()
    folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    try:
        uploader = GDriveUploader()
        
        if not uploader.service:
            print("❌ 인증 실패")
            return
        
        print(f"\n1️⃣ 설정된 폴더 ID: {folder_id}")
        
        # Try to access the folder
        print(f"\n2️⃣ 폴더 접근 시도...")
        try:
            folder = uploader.service.files().get(
                fileId=folder_id,
                fields='id, name, mimeType, trashed, capabilities'
            ).execute()
            
            print(f"   ✅ 폴더 접근 성공!")
            print(f"      이름: {folder.get('name')}")
            print(f"      ID: {folder.get('id')}")
            print(f"      휴지통: {folder.get('trashed', False)}")
            print(f"      업로드 가능: {folder.get('capabilities', {}).get('canAddChildren', False)}")
            
        except Exception as e:
            print(f"   ❌ 폴더 접근 실패: {e}")
            
            # List user's folders
            print(f"\n3️⃣ 사용 가능한 폴더 목록 (최근 10개):")
            try:
                results = uploader.service.files().list(
                    q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                    pageSize=10,
                    fields="files(id, name, parents)"
                ).execute()
                
                folders = results.get('files', [])
                if folders:
                    for folder in folders:
                        print(f"      📁 {folder['name']}")
                        print(f"         ID: {folder['id']}")
                        print()
                else:
                    print("      폴더를 찾을 수 없습니다.")
                    
                print(f"\n💡 위 목록에서 올바른 폴더 ID를 찾아 .env 파일을 업데이트하세요.")
                
            except Exception as e2:
                print(f"      폴더 목록 조회 실패: {e2}")
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_folder_access()
