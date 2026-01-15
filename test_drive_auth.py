# -*- coding: utf-8 -*-
"""
Google Drive 인증 테스트 스크립트
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

def test_drive_auth():
    print("=" * 60)
    print("Google Drive 인증 테스트")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Check environment variables
    print("\n1️⃣ 환경 변수 확인:")
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    if token_json:
        if os.path.isfile(token_json):
            print(f"   ✅ GOOGLE_TOKEN_JSON: 파일 경로 ({token_json})")
            if Path(token_json).exists():
                print(f"      파일 존재: ✅")
                print(f"      파일 크기: {Path(token_json).stat().st_size} bytes")
            else:
                print(f"      파일 존재: ❌ (파일을 찾을 수 없음)")
        else:
            print(f"   ✅ GOOGLE_TOKEN_JSON: JSON 문자열 (길이: {len(token_json)} chars)")
    else:
        print("   ❌ GOOGLE_TOKEN_JSON: 설정되지 않음")
        
        # Check for local token file
        local_token = Path("credentials/token.json")
        if local_token.exists():
            print(f"\n   💡 로컬 토큰 파일 발견: {local_token}")
            print(f"      .env 파일에 다음과 같이 설정하세요:")
            print(f"      GOOGLE_TOKEN_JSON=credentials/token.json")
    
    if folder_id:
        print(f"   ✅ GOOGLE_DRIVE_FOLDER_ID: {folder_id}")
    else:
        print("   ❌ GOOGLE_DRIVE_FOLDER_ID: 설정되지 않음")
    
    # Test authentication
    print("\n2️⃣ 인증 테스트:")
    try:
        uploader = GDriveUploader()
        
        if uploader.service:
            print("   ✅ Google Drive 인증 성공!")
            
            # Test folder access
            if folder_id:
                print(f"\n3️⃣ 폴더 접근 테스트 (ID: {folder_id}):")
                try:
                    folder = uploader.service.files().get(
                        fileId=folder_id,
                        fields='id, name, mimeType'
                    ).execute()
                    print(f"   ✅ 폴더 접근 성공!")
                    print(f"      폴더 이름: {folder.get('name')}")
                    print(f"      폴더 ID: {folder.get('id')}")
                except Exception as e:
                    print(f"   ❌ 폴더 접근 실패: {e}")
                    print(f"      폴더 ID가 올바른지 확인하세요.")
        else:
            print("   ❌ Google Drive 인증 실패")
            print("\n   문제 해결 방법:")
            print("   1. .env 파일에 GOOGLE_TOKEN_JSON 설정 확인")
            print("   2. credentials/token.json 파일 존재 확인")
            print("   3. token.json 파일이 유효한지 확인 (만료되었을 수 있음)")
            
    except Exception as e:
        print(f"   ❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    test_drive_auth()
