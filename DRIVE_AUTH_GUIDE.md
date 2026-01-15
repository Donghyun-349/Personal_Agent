# Google Drive 인증 설정 가이드

## 문제 진단 결과

❌ `.env` 파일에 `GOOGLE_TOKEN_JSON`이 설정되지 않음  
✅ `credentials/token.json` 파일은 존재함  
✅ `GOOGLE_DRIVE_FOLDER_ID`는 설정되어 있음

## 해결 방법

`.env` 파일을 열고 다음 줄을 추가하세요:

```
GOOGLE_TOKEN_JSON=credentials/token.json
```

또는 절대 경로로:

```
GOOGLE_TOKEN_JSON=d:/Dev/Scrapper/credentials/token.json
```

## 전체 .env 파일 예시

```env
# Google API Keys
GOOGLE_API_KEY=your_gemini_api_key_here

# Google Drive Settings
GOOGLE_TOKEN_JSON=credentials/token.json
GOOGLE_DRIVE_FOLDER_ID=18DINVl8r6T9Bxf6dBHa9PKiHbfnAj4vq
```

## 설정 후 테스트

```powershell
python test_drive_auth.py
```

성공 시 다음과 같은 메시지가 표시됩니다:

```
✅ Google Drive 인증 성공!
✅ 폴더 접근 성공!
```

## 참고사항

- `token.json` 파일이 만료되었을 경우, 다시 생성해야 할 수 있습니다
- 폴더 ID는 이미 올바르게 설정되어 있습니다: `18DINVl8r6T9Bxf6dBHa9PKiHbfnAj4vq`
