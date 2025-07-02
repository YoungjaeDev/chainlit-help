# Chainlit 헬프 앱 설치 가이드

## 설치 단계

### 1. 가상환경 설정
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

### 2. 의존성 설치
```bash
uv pip install -r app\requirements.txt
```

### 3. 환경 변수 설정
`.env` 파일을 프로젝트 루트에 생성하고 필요한 API 키를 설정하세요:
```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
LITERAL_API_KEY=your_literal_api_key_here
```

### 4. 앱 실행
```bash
chainlit run app/app.py
```

## 문제 해결

### Unicode 인코딩 에러 (UnicodeDecodeError)

**문제**: 
```
UnicodeDecodeError: 'cp949' codec can't decode byte 0xe2 in position 22: illegal multibyte sequence
```

**원인**: 
- Windows 한국어 환경에서 기본 인코딩인 cp949 사용
- 읽으려는 파일이 UTF-8 인코딩으로 되어 있음

**해결됨**: 
모든 파일 열기 부분에 `encoding="utf-8"` 매개변수가 추가되었습니다.

