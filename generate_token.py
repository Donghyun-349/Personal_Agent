# -*- coding: utf-8 -*-
"""
Google Drive OAuth 토큰 생성 스크립트
"""
import os
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# OAuth scope - full Drive access
SCOPES = ['https://www.googleapis.com/auth/drive']

def generate_token():
    print("=" * 60)
    print("Google Drive OAuth 토큰 생성")
    print("=" * 60)
    
    creds = None
    token_file = Path('credentials/token.json')
    client_secret_file = Path('credentials/client_secret.json')
    
    # Check if client_secret.json exists
    if not client_secret_file.exists():
        print(f"\n❌ {client_secret_file} 파일을 찾을 수 없습니다!")
        print("   Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하고")
        print("   client_secret.json 파일을 credentials/ 폴더에 저장하세요.")
        return
    
    # Check if token already exists
    if token_file.exists():
        print(f"\n⚠️  기존 토큰 파일이 발견되었습니다: {token_file}")
        response = input("   기존 토큰을 삭제하고 새로 생성하시겠습니까? (y/N): ")
        if response.lower() != 'y':
            print("   취소되었습니다.")
            return
        token_file.unlink()
        print("   기존 토큰 삭제 완료")
    
    print(f"\n1️⃣ OAuth 인증 시작...")
    print(f"   Scope: {SCOPES[0]}")
    print(f"   브라우저가 자동으로 열립니다...")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_file), SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Save the credentials
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        
        print(f"\n✅ 토큰 생성 성공!")
        print(f"   저장 위치: {token_file}")
        print(f"   파일 크기: {token_file.stat().st_size} bytes")
        
        # Verify the token
        from googleapiclient.discovery import build
        service = build('drive', 'v3', credentials=creds)
        about = service.about().get(fields="user").execute()
        user = about.get('user', {})
        
        print(f"\n2️⃣ 인증된 계정:")
        print(f"   이메일: {user.get('emailAddress')}")
        print(f"   이름: {user.get('displayName')}")
        
        print(f"\n3️⃣ 다음 단계:")
        print(f"   1. .env 파일에 다음 설정 확인:")
        print(f"      GOOGLE_TOKEN_JSON=credentials/token.json")
        print(f"   2. 테스트 실행:")
        print(f"      python test_folder_list.py")
        
    except Exception as e:
        print(f"\n❌ 토큰 생성 실패: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    generate_token()
