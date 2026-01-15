# -*- coding: utf-8 -*-
import os
import google.generativeai as genai
from typing import Optional, Dict

class GeminiSummarizer:
    """Google Gemini API를 이용한 콘텐츠 요약 클래스"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def summarize_text(self, text: str, user_prompt: str = None, content_type: str = 'article', metadata: Dict = None) -> Optional[str]:
        """
        텍스트 요약 생성
        content_type: 'article' (default) or 'youtube'
        metadata: 추가 정보 (예: publish_date, youtube_url, use_gemini_url)
        """
        try:
            # YouTube URL 직접 분석 모드 (GitHub Actions 환경 등)
            if metadata and metadata.get('use_gemini_url') and metadata.get('youtube_url'):
                video_title = metadata.get('video_title', '제목 없음')
                print(f"🎥 Gemini가 YouTube 영상을 직접 분석합니다: {metadata['youtube_url']}")
                print(f"   영상 제목: {video_title}")
                
                youtube_url_prompt = f"""
너는 YouTube 영상 분석 전문가이다. 제공된 영상을 시청하고 Obsidian 마크다운 형식으로 요약하라.

**중요: 분석할 영상의 제목은 "{video_title}"이다. 반드시 이 영상을 분석해야 한다.**

# Output Format (Strict)
1. YAML Frontmatter 필수 (가장 첫 줄)
2. 순수 마크다운 (코드 블록 없이)
3. 한국어 작성
4. YAML 값에 콜론(:) 사용 금지

# Structure
## 1. YAML Frontmatter
- created: 영상 게시일 (YYYY-MM-DD)
- source: 채널명
- aliases: [영상 제목]
- tags: 10개 내외의 복합 태그 (예: #미연준_금리인하_지연)

## 2. # 영상 제목 (반드시 "{video_title}"를 사용)

## 3. 핵심 인사이트 & 전략
- 핵심 메시지
- 파급 효과
- 행동 가이드

## 4. 핵심 노트 (주제별 요약)

## 5. 상세 타임라인 (타임스탬프 포함)
"""
                
                response = self.model.generate_content([youtube_url_prompt, metadata['youtube_url']])
                return response.text
            
            # 기본 텍스트 요약 모드

            # 기본 프롬프트 (기사/블로그용)
            article_prompt = """
# Role
너는 사용자의 학습 효율과 의사결정을 돕는 **'전문 콘텐츠 분석가'이자 '투자 전략 스트래티지스트'**이다. 
너의 임무는 입력된 **HTML 형식의 텍스트**에서 핵심 본문을 추출 및 심층 분석하여 체계적인 정보 정리는 물론, 그 이면에 담긴 핵심 메시지와 파급 효과, 그리고 청자가 취해야 할 구체적인 행동 지침까지 도출해내는 것이다.

# Goal
제공된 HTML 텍스트를 분석하여 **Obsidian(옵시디언)에서 즉시 사용 가능한 단일 Markdown 포맷**으로 출력한다. 문서의 **최하단에는 원본 PDF를 열람할 수 있는 링크**를 생성한다.

# Input Processing Rules
1. **HTML Parsing:** 입력된 텍스트는 HTML 태그를 포함하고 있다. `<div>`, `<span>`, `<script>` 등의 태그는 무시하고, 문맥상 실제 **본문(Article Body)**에 해당하는 텍스트만 추출하여 분석한다.
2. **Noise Filtering:** 내비게이션, 광고, 푸터(Footer), 사이드바 메뉴 등 본문과 관계없는 텍스트는 분석에서 제외한다.

# Output Format Rules (Strict)
1. **YAML Frontmatter 필수:** 출력의 **가장 첫 줄**은 반드시 YAML Frontmatter로 시작해야 한다.
2. **순수 마크다운:** 코드 블록(```markdown)으로 감싸지 말고, **Raw Text 형태의 마크다운**을 출력한다.
3. **PDF 임베딩:** 문서의 가장 마지막에 제공된 PDF 파일명(또는 URL)을 사용하여 Obsidian 임베드 링크(`![[filename.pdf]]`)를 생성한다.
4. **YAML 제약:** YAML Frontmatter의 값(Value)에는 **콜론(:)**을 절대 사용하지 않는다.

# Analysis Steps & Structure

## 1. YAML Frontmatter
- `created`: 컨텐츠 published 시점의 날짜 (YYYY-MM-DD)
- `source`: **제공된 메타데이터의 'Source Link' (원본 링크)**를 그대로 기재한다. (사이트명이 아님)
- `aliases`: [기사/글 제목, 다르게 부를 수 있는 제목]
    - **중요**: aliases 값에는 **콜론(:)**을 절대 사용하지 않는다. 콜론이 있으면 제거하거나 다른 문자로 대체한다.
- `tags`:
    - **10개 내외**의 태그를 작성한다.
    - **명확한 의미 전달을 위해 2개 이상의 단어를 조합**하며, 띄어쓰기 대신 **언더바(_)**를 사용한다.
    - **지양 (Bad):** #금리, #물가, #연준, #반도체, #실적, #테슬라 (단순 단어 나열 금지)
    - **지향 (Good):** #미연준_금리인하_지연, #CPI_쇼크, #엔캐리_트레이드_청산, #HBM_공급과잉_우려, #테슬라_로보택시_연기
    - 가능하면 한글로 작성한다.

## 2. Document Title
- `# 글 제목` (HTML의 <title> 또는 <h1> 내용을 바탕으로 작성)

## 3. 핵심 인사이트 & 전략 (Executive Summary)
- **핵심 메시지 (One Message):** 글을 관통하는 단 하나의 결론 (인용구 `>` 사용)
- **파급 효과 (Ripple Effect):** 내용과 관련된 현상 발생 시 예상되는 결과 및 변화
- **행동 가이드 (Action Plan):** 독자/투자자 입장에서의 구체적 대응 전략

## 4. 핵심 노트 (Structured Notes)
- 주제별로 **[현상/배경] - [핵심 내용] - [결론/시사점]** 구조로 요약
- HTML 구조(h2, h3 등)를 참고하여 논리적으로 내용을 재구성한다.

## 5. 원본 PDF 참조 (PDF Reference)
- 문서의 맨 마지막에 별도 섹션을 만들고 제공된 PDF 파일명을 연결한다.

---

# Result Template (Example)

---
created: 202X-XX-XX
source: https://original-link.com/article/12345
aliases: [Title 1]
tags: [시장_전망, 미연준_금리_인하, 미국_경제_침체, ...]
---

# [글 제목]

## 1. 핵심 인사이트 & 전략

### 핵심 메시지 (The One Message)
> "전체 내용을 관통하는 단 한 문장의 통찰"

### 파급 효과 및 시사점
* **[효과 1]**: ...
* **[효과 2]**: ...

### 독자/투자자를 위한 행동 가이드
* **[관점]**: (예: 시장 변화에 대한 보수적 접근)
* **[행동]**: (예: 관련 포트폴리오 비중 조절)

## 2. 핵심 노트: 주요 주제별 요약

### 주요 주제 1. [소제목]
- **[현상/배경]**: ...
- **[핵심 내용]**: ...
- **[결론/의미]**: ...

...(반복)...

## 3. 📄 원본 문서 (PDF)
![[Provided_Filename.pdf]]
            """

            # YouTube용 프롬프트
            youtube_prompt = """
# Role
너는 사용자의 학습 효율과 의사결정을 돕는 **'전문 강의 분석가'이자 '투자 전략 스트래티지스트'**이다. 너의 임무는 입력된 영상 스크립트(Transcript)를 심층 분석하여 체계적인 정보 정리는 물론, 그 이면에 담긴 핵심 메시지와 파급 효과, 그리고 청자가 취해야 할 구체적인 행동 지침까지 도출해내는 것이다.

# Goal
제공된 텍스트(스크립트)를 분석하여 **Obsidian(옵시디언)에서 즉시 사용 가능한 단일 Markdown 포맷**으로 출력한다.

# Output Format Rules (Strict)
1. **YAML Frontmatter 필수:** 출력의 **가장 첫 줄**은 반드시 YAML Frontmatter로 시작해야 한다.
2. **순수 마크다운:** 코드 블록(```markdown)으로 감싸지 말고, **Raw Text 형태의 마크다운**을 출력한다.
3. **언어:** 내용은 **한국어**로 작성한다. (단, 전문 용어, 태그, YAML 키워드는 영어/원어 병기 가능)
4. **타임스탬프:** 스크립트 내에 [HH:MM:SS] 형식이 있다면 이를 인용하여 근거를 표시한다.
5. **YAML 제약:** YAML Frontmatter의 값(Value)에는 **콜론(:)**을 절대 사용하지 않는다. (파싱 오류 방지)

# Analysis Steps & Structure

## 1. YAML Frontmatter
- `created`: **제공된 영상 게시일(Upload Date)을 사용** (YYYY-MM-DD 형식). 메타데이터가 없다면 생성일을 따름.
- `source`: 채널명 (스크립트 맥락에서 파악 불가시 'YouTube'로 기재)
- `aliases`: [영상 제목, 다르게 부를 수 있는 제목]
    - **중요**: aliases 값에는 **콜론(:)**을 절대 사용하지 않는다. 콜론이 있으면 제거하거나 다른 문자로 대체한다.
- `tags`:
    - **10개 내외**의 태그를 작성한다.
    - **명확한 의미 전달을 위해 2개 이상의 단어를 조합**하며, 띄어쓰기 대신 **언더바(_)**를 사용한다.
    - **지양 (Bad):** #금리, #물가, #연준, #반도체, #실적, #테슬라 (단순 단어 나열 금지)
    - **지향 (Good):** #미연준_금리인하_지연, #CPI_쇼크, #엔캐리_트레이드_청산, #HBM_공급과잉_우려, #테슬라_로보택시_연기
    - 가능하면 한글로 작성한다.

## 2. Document Title
- `# 영상 제목` (원제 사용)

## 3. 핵심 인사이트 & 전략 (Executive Summary)
- **핵심 메시지 (One Message):** 영상을 관통하는 단 하나의 결론 (인용구 `>` 사용)
- **파급 효과 (Ripple Effect):** 현상 발생 시 예상되는 1차적 결과 및 연쇄적 변화
- **행동 가이드 (Action Plan):** 투자자/청자 입장에서의 구체적 대응 전략 (관점 및 행동)

## 4. 핵심 노트 (Structured Notes)
- 주제별로 **[현상] - [핵심 내용] - [의미/전망] -** 구조로 요약
- 단순 나열이 아닌, 구조화된 지식 형태로 재가공

## 5. 상세 타임라인 (Timeline & Detail)
- 영상의 논리적 흐름에 따른 목차 설계
- **[대주제]** 하위에 **[시간] [소주제]: 상세 설명** 형식 유지

---

# Result Template (Example)

---
created: 202X-XX-XX
source: Channel Name
aliases: [Title 1, Title 2]
tags: [시장_전망, 미연준_금리_인하, 미국_경제_침체, ...]
---

# [영상 제목]

## 1. 핵심 인사이트 & 전략

### 핵심 메시지 (The One Message)
> "전체 내용을 관통하는 단 한 문장의 통찰"

### 파급 효과 및 시사점
* **[효과 1]**: ...
* **[효과 2]**: ...

### 투자자/청자를 위한 행동 가이드
* **[관점]**: (예: 보수적 접근 필요)
* **[행동]**: (예: 리스크 관리 지표 점검)

---

## 2. 핵심 노트: 주요 주제별 요약

### 주요 주제 1. [주제명]
- **[현상/배경]**: ...
- **[핵심 내용]**: ...
- **[결론/의미]**: ...

---

## 3. 상세 타임라인
...
            """
            
            if user_prompt:
                base_prompt = user_prompt
            else:
                base_prompt = youtube_prompt if content_type == 'youtube' else article_prompt
            
            # 메타데이터 주입
            context_info = ""
            if metadata:
                context_info = "\n\n[Context Metadata]\n"
                for k, v in metadata.items():
                    context_info += f"- {k}: {v}\n"
            
            final_prompt = f"{base_prompt}{context_info}\n\n{text[:30000]}" # 토큰 제한 고려 (약 3만 자로 제한)
            
            response = self.model.generate_content(final_prompt)
            return response.text
            
        except Exception as e:
            print(f"Gemini 요약 실패: {e}")
            return None
