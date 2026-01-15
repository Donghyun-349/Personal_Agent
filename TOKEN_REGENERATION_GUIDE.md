# Google Drive OAuth 토큰 재생성 가이드

## 문제

현재 `token.json`의 OAuth scope가 `drive.file`로 제한되어 있어, **앱이 생성한 파일만** 접근할 수 있습니다.  
기존 폴더에 업로드하려면 `drive` scope가 필요합니다.

## 해결 방법

### 1. 기존 token.json 삭제

```powershell
Remove-Item credentials\token.json
```

### 2. OAuth 토큰 재생성

새로운 scope로 토큰을 재생성해야 합니다. 다음 스크립트를 실행하세요:

```powershell
python generate_token.py
```

이 스크립트는:

1. 브라우저를 열어 Google 로그인 요청
2. `seodh349@gmail.com` 계정으로 로그인
3. "Google Drive에 대한 전체 액세스 권한" 승인
4. 새로운 `credentials/token.json` 생성

### 3. 재테스트

```powershell
python test_folder_list.py
```

이제 폴더 목록이 표시되고, 기존 폴더에 접근할 수 있어야 합니다.

## 참고

- **이전 scope**: `https://www.googleapis.com/auth/drive.file` (앱이 생성한 파일만)
- **새 scope**: `https://www.googleapis.com/auth/drive` (모든 파일/폴더)

scope를 변경했으므로 반드시 토큰을 재생성해야 합니다!
