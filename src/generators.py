# -*- coding: utf-8 -*-
import os
import re
import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import requests
from bs4 import BeautifulSoup

# Use absolute imports
from config import MAX_IMAGE_SIZE, NAVER_COOKIES, USER_AGENT, REQUEST_TIMEOUT
from utils import sanitize_filename, generate_filename, ImageProcessor

class MarkdownGenerator:
    """Markdown 파일 생성 클래스"""
    
    def __init__(self, markdown_dir: Path):
        self.markdown_dir = markdown_dir
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_filename(self, title: str, url: str, extension: str = '.md') -> str:
        """파일명 생성"""
        return generate_filename(title, self.markdown_dir, extension)
    
    def create_markdown(self, data: Dict) -> str:
        """Markdown 파일 생성"""
        # Frontmatter 생성
        created_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if data['content'].strip().startswith('---'):
            # 이미 Frontmatter가 포함된 경우 (예: Gemini 요약본)
            return data['content']
            
        frontmatter = f"""---
created: {created_time}
source: {data['url']}
tags: #clippings
type: {data['type']}
"""
        
        if data['type'] == 'youtube' and 'channel' in data:
            frontmatter += f"channel: {data['channel']}\n"
        
        frontmatter += "---\n\n"
        
        # 본문 생성
        content = f"# {data['title']}\n\n"
        content += data['content']
        
        return frontmatter + content
    
    def save(self, data: Dict, image_processor: ImageProcessor = None) -> Path:
        """
        Markdown 파일 저장
        image_processor: 이미지 다운로드를 위한 ImageProcessor (선택)
        """
        filename = self.generate_filename(data['title'], data['url'], '.md')
        filepath = self.markdown_dir / filename
        
        markdown_content = self.create_markdown(data)
        
        # 이미지 경로 처리 (이미지 URL을 찾아서 img 폴더에 다운로드)
        # YouTube의 경우 썸네일은 다운로드하지 않으므로 img 폴더 생성 불필요
        if image_processor:
            markdown_content = self._process_image_paths(markdown_content, filepath.parent, image_processor, data.get('type') == 'youtube')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return filepath
    
    def _process_image_paths(self, markdown_content: str, target_dir: Path, image_processor: ImageProcessor, is_youtube: bool = False) -> str:
        """
        Markdown 내 이미지 URL을 찾아서 img 폴더에 다운로드하고 경로 변경
        is_youtube: YouTube 파일인 경우 썸네일은 다운로드하지 않고 링크만 유지
        """
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        
        # YouTube가 아닌 경우에만 img 폴더 생성
        if not is_youtube:
            img_dir = target_dir / "img"
            img_dir.mkdir(parents=True, exist_ok=True)
        
        def replace_image(match):
            alt_text = match.group(1)
            image_url = match.group(2)
            
            # 이미 로컬 경로인 경우 (img/로 시작) 그대로 유지
            if image_url.startswith('img/'):
                return match.group(0)
            
            # YouTube 썸네일인 경우 다운로드하지 않고 링크만 유지
            if is_youtube and ('youtube.com' in image_url or 'img.youtube.com' in image_url):
                return match.group(0)
            
            # 이미지 URL인 경우 다운로드
            if image_url.startswith(('http://', 'https://')):
                # img 폴더가 없으면 생성
                img_dir = target_dir / "img"
                img_dir.mkdir(parents=True, exist_ok=True)
                
                local_path = image_processor.download_and_resize(
                    image_url,
                    base_filename=sanitize_filename(alt_text or "image", max_length=100),
                    target_dir=target_dir
                )
                if local_path:
                    return f"![{alt_text}]({local_path})"
            
            # 실패하거나 이미 로컬 경로인 경우 원본 유지
            return match.group(0)
        
        return re.sub(pattern, replace_image, markdown_content)


class HTMLGenerator:
    """HTML 파일 생성 클래스 (옵시디언 호환)"""
    
    def __init__(self, html_dir: Path, assets_dir: Path):
        self.html_dir = html_dir
        self.assets_dir = assets_dir  # Markdown용 (사용 안 함)
        self.html_dir.mkdir(parents=True, exist_ok=True)
        # HTML 이미지 저장 폴더 (HTML 파일과 같은 위치의 img 폴더)
        self.html_img_dir = self.html_dir / "img"
        self.html_img_dir.mkdir(parents=True, exist_ok=True)
        self.created_files = [] # Track generated files

    def cleanup(self):
        """생성된 이미지 파일 삭제"""
        for filepath in self.created_files:
            try:
                if filepath.exists():
                    filepath.unlink()
            except Exception as e:
                print(f"이미지 삭제 실패: {e}")
        self.created_files = []
        
        # img 폴더 비어있으면 삭제 시도
        try:
            if self.html_img_dir.exists() and not any(self.html_img_dir.iterdir()):
                self.html_img_dir.rmdir()
        except:
            pass

    def generate_filename(self, title: str, url: str) -> str:
        """파일명 생성"""
        return generate_filename(title, self.html_dir, '.html')
    
    def download_image_for_html(self, image_url: str, base_filename: str = None) -> Optional[str]:
        """HTML용 이미지 다운로드 및 리사이징 (img 폴더에 저장)"""
        try:
            # http/https 체크
            if not image_url or not image_url.startswith(('http://', 'https://')):
                return None
            
            # 네이버 이미지 URL에서 썸네일 파라미터를 더 큰 사이즈로 교체
            # 예: ?type=w80_blur -> ?type=w966 (더 큰 사이즈)
            from urllib.parse import urlparse, urlunparse
            if 'pstatic.net' in image_url or 'naver.com' in image_url:
                parsed = urlparse(image_url)
                # 쿼리 파라미터를 더 큰 사이즈로 교체
                if '?type=' in image_url:
                    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', 'type=w966', ''))
                    image_url = clean_url
                else:
                    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', 'type=w966', ''))
                    image_url = clean_url
            
            # html_img_dir이 html_dir에 상대적으로 올바르게 설정되어 있는지 확인
            expected_html_img_dir = self.html_dir / "img"
            if self.html_img_dir != expected_html_img_dir:
                self.html_img_dir = expected_html_img_dir
                self.html_img_dir.mkdir(parents=True, exist_ok=True)
            
            # 이미지 다운로드
            headers = {"User-Agent": USER_AGENT}
            cookies = NAVER_COOKIES if any(domain in image_url for domain in ['naver.com', 'pstatic.net', 'blogfiles.naver.net', 'postfiles.naver.net']) else None
            response = requests.get(image_url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()
            
            # 이미지 데이터 로드
            from PIL import Image
            import io
            import hashlib
            
            image_data = response.content
            img = Image.open(io.BytesIO(image_data))
            
            # 원본 형식 저장
            original_format = img.format or "PNG"
            
            # 리사이징 (MAX_IMAGE_SIZE보다 큰 경우만)
            if img.width > MAX_IMAGE_SIZE or img.height > MAX_IMAGE_SIZE:
                ratio = min(MAX_IMAGE_SIZE / img.width, MAX_IMAGE_SIZE / img.height)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 파일명 생성
            if base_filename:
                parsed_url = urlparse(image_url)
                ext = Path(parsed_url.path).suffix or f".{original_format.lower()}"
                filename = f"{base_filename}{ext}"
            else:
                url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
                ext = f".{original_format.lower()}"
                filename = f"{url_hash}{ext}"
            
            # 파일 저장
            filepath = self.html_img_dir / filename
            
            # 중복 파임명 처리
            counter = 1
            original_filepath = filepath
            while filepath.exists():
                stem = original_filepath.stem
                suffix = original_filepath.suffix
                filepath = self.html_img_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # Track file
            self.created_files.append(filepath)

            # 이미지 저장
            if original_format in ["JPEG", "JPG"]:
                img.save(filepath, "JPEG", quality=85, optimize=True)
            elif original_format == "PNG":
                img.save(filepath, "PNG", optimize=True)
            else:
                img.save(filepath, original_format)
            
            # HTML 파일 기준 상대 경로 반환
            return f"./img/{filepath.name}"
            
        except Exception as e:
            print(f"HTML 이미지 다운로드/리사이징 실패 ({image_url}): {e}")
            return None
    
    def create_html(self, data: Dict, main_container_html: str = None) -> str:
        """HTML 파일 생성"""
        created_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # main_container_html이 제공되면 사용, 아니면 content를 HTML로 변환
        if main_container_html:
            body_content = main_container_html
        else:
            # 마크다운을 HTML로 변환 (간단한 변환)
            body_content = f"<div class='markdown-content'>{data['content']}</div>"
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{data['title']}</title>
    <style>
        body {{
            font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #f9f9f9;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }}
        .metadata {{
            color: gray;
            font-size: 0.9em;
            margin-bottom: 20px;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        blockquote {{
            background: #f9f9f9;
            border-left: 5px solid #ccc;
            margin: 1.5em 10px;
            padding: 0.5em 10px;
        }}
        /* 네이버 블로그 원본 스타일 일부 유지 */
        .se-component {{
            margin-bottom: 20px;
        }}
        .se-text-paragraph {{
            margin-bottom: 10px;
        }}
        .markdown-content {{
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1><a href="{data['url']}" target="_blank" style="text-decoration:none; color:black;">{data['title']}</a></h1>
        <div class="metadata">
            <p>Source: <a href="{data['url']}" target="_blank">{data['url']}</a></p>
            <p>Scraped: {created_time}</p>
            <p>Type: {data['type']}</p>
        </div>
        <hr>
        {body_content}
    </div>
</body>
</html>"""
        
        return html_content
    
    def save(self, data: Dict, main_container_html: str = None) -> Path:
        """HTML 파일 저장"""
        filename = self.generate_filename(data['title'], data['url'])
        filepath = self.html_dir / filename
        
        # HTML 파일이 저장될 위치에 img 폴더 생성
        img_dir = filepath.parent / "img"
        img_dir.mkdir(parents=True, exist_ok=True)
        # html_img_dir도 img로 변경
        self.html_img_dir = img_dir
        
        html_content = self.create_html(data, main_container_html)
        
        # HTML 내 이미지 URL 처리 (이미지 URL을 찾아서 img 폴더에 다운로드)
        html_content = self._process_html_images(html_content, filepath.parent)
        
        # HTML 내 이미지 경로 처리 (html_img -> img로 변경)
        html_content = html_content.replace('./html_img/', './img/')
        html_content = html_content.replace('html_img/', 'img/')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath
    
    def _process_html_images(self, html_content: str, target_dir: Path) -> str:
        """HTML 내 이미지 URL을 찾아서 img 폴더에 다운로드하고 경로 변경"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 모든 img 태그 찾기
        for img in soup.find_all('img'):
            img_src = img.get('src')
            if img_src and img_src.startswith(('http://', 'https://')):
                # 이미지 다운로드
                local_path = self.download_image_for_html(img_src, base_filename=None)
                if local_path:
                    img['src'] = local_path
        
        return str(soup)


class PDFGenerator:
    """PDF 파일 생성 클래스"""
    
    def __init__(self, pdf_dir: Path, assets_dir: Path):
        self.pdf_dir = pdf_dir
        self.assets_dir = assets_dir
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_filename(self, title: str, url: str) -> str:
        """PDF 파일명 생성: 원문제목_attach.pdf (특수기호 제거)"""
        import re
        
        # 특수문자 및 공백을 모두 제거하고 언더바로 대체
        # 한글, 영문, 숫자만 남기고 나머지는 언더바로 변환
        clean_title = re.sub(r'[^\w가-힣]', '_', title)
        # 연속된 언더바를 하나로 축소
        clean_title = re.sub(r'_+', '_', clean_title)
        # 앞뒤 언더바 제거
        clean_title = clean_title.strip('_')
        
        # 길이 제한 (Windows 파일명 제한 고려)
        if len(clean_title) > 100:
            clean_title = clean_title[:100]
        
        # _attach 접미사 추가
        filename = f"{clean_title}_attach.pdf"
        
        return filename
    
    async def _generate_pdf_async(self, html_filepath: Path, pdf_filepath: Path) -> None:
        """Async method to generate PDF using Playwright"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("playwright가 설치되지 않았습니다. 'pip install playwright' 후 'playwright install chromium'을 실행해주세요.")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            # HTML 파일 경로를 file:// URL로 변환
            html_url = html_filepath.as_uri()
            await page.goto(html_url, wait_until='networkidle')
            # PDF 생성 (A4 크기, 여백 설정)
            await page.pdf(
                path=str(pdf_filepath),
                format='A4',
                margin={'top': '20mm', 'right': '20mm', 'bottom': '20mm', 'left': '20mm'},
                print_background=True
            )
            await browser.close()
    
    def save(self, data: Dict, main_container_html: str = None, source_html_path: Path = None) -> Path:
        """PDF 파일 저장 (HTML 파일을 생성한 후 PDF로 변환)
        source_html_path: 이미 생성된 HTML 파일이 있다면 그 경로를 사용하여 재생성 방지
        """
        filename = self.generate_filename(data['title'], data['url'])
        filepath = self.pdf_dir / filename
        
        temp_html_created = False
        html_filepath = None

        # 기존 HTML 파일 사용 시도
        if source_html_path and source_html_path.exists():
            html_filepath = source_html_path
        else:
            # HTML 파일 생성 (이미지 다운로드 포함)
            html_generator = HTMLGenerator(self.pdf_dir, self.assets_dir)
            html_filepath = html_generator.save(data, main_container_html)
            temp_html_created = True
        
        # HTML 파일을 PDF로 변환 (isolated event loop)
        # Windows에서 subprocess 문제 해결을 위한 event loop policy 설정
        if sys.platform == 'win32':
            # Set the policy before creating the loop
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Create a new event loop for this operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._generate_pdf_async(html_filepath, filepath))
        finally:
            loop.close()
            # Reset to default policy if needed
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(None)
        
        # 임시 HTML 파일 삭제 (우리가 생성했을 때만)
        if temp_html_created:
            try:
                html_filepath.unlink()
            except Exception as e:
                pass
        
        return filepath
