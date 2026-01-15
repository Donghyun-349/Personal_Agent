# -*- coding: utf-8 -*-
import os
import re
import json
import hashlib
import io
import requests
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from PIL import Image
from urllib.parse import urlparse, urlunparse

# Use absolute imports
from config import (
    CONFIG_FILE, DEFAULT_CLIPPINGS_DIR, DEFAULT_ASSETS_DIR,
    MAX_IMAGE_SIZE, REQUEST_TIMEOUT, NAVER_COOKIES, USER_AGENT
)

def sanitize_filename(title: str, max_length: int = 150) -> str:
    """파일명에서 특수문자 제거 및 정리"""
    invalid_chars = r'<>:"/\|?*'
    # Remove metadata like [Title] or [NOTICE] from filename
    title = re.sub(r'\[.*?\]', '', title).strip()
    
    for char in invalid_chars:
        title = title.replace(char, '_')
    title = title.replace(' ', '_')
    if len(title) > max_length:
        title = title[:max_length]
    return title

def generate_filename(title: str, save_dir: Path, extension: str = '.md') -> str:
    """파일명 생성 (중복 처리 포함)"""
    sanitized = sanitize_filename(title)
    
    if not sanitized or sanitized == "Untitled":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Untitled_{timestamp}{extension}"
    else:
        filename = f"{sanitized}{extension}"
    
    # 중복 파일명 처리
    filepath = save_dir / filename
    counter = 1
    original_filepath = filepath
    while filepath.exists():
        stem = original_filepath.stem
        filepath = save_dir / f"{stem}_{counter}{extension}"
        counter += 1
    
    return filepath.name

class ConfigManager:
    """설정 파일 관리 클래스"""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = Path(config_file)
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """설정 파일 로드"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"설정 파일 로드 오류: {e}")
                return self.get_default_config()
        return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """기본 설정 반환"""
        # 스크립트 실행 위치 기준이 아니라 home 또는 현재 working dir 기준으로 변경 고려
        # 일단은 현재 working directory 기준으로 설정
        cwd = Path.cwd()
        return {
            "markdown_dir": str(cwd / DEFAULT_CLIPPINGS_DIR),
            "assets_dir": str(cwd / DEFAULT_ASSETS_DIR)
        }
    
    def save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"설정 파일 저장 오류: {e}")
    
    def get_markdown_dir(self) -> Path:
        """Markdown 파일 저장 디렉토리 반환"""
        return Path(self.config.get("markdown_dir", self.get_default_config()["markdown_dir"]))
    
    def get_assets_dir(self) -> Path:
        """이미지 저장 디렉토리 반환"""
        return Path(self.config.get("assets_dir", self.get_default_config()["assets_dir"]))


class ImageProcessor:
    """이미지 다운로드 및 리사이징 처리 클래스"""
    
    def __init__(self, assets_dir: Path, max_size: int = MAX_IMAGE_SIZE):
        self.assets_dir = assets_dir
        self.max_size = max_size
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

    def download_and_resize(self, image_url: str, base_filename: str = None, target_dir: Path = None) -> Optional[str]:
        """이미지 다운로드 및 리사이징 후 로컬 경로 반환"""
        try:
            # http/https 체크
            if not image_url or not image_url.startswith(('http://', 'https://')):
                return None
            
            # 네이버 이미지 URL에서 썸네일 파라미터를 더 큰 사이즈로 교체
            # 예: ?type=w80_blur -> ?type=w966 (더 큰 사이즈)
            if 'pstatic.net' in image_url or 'naver.com' in image_url:
                parsed = urlparse(image_url)
                # 쿼리 파라미터를 더 큰 사이즈로 교체
                if '?type=' in image_url:
                    # 원본 크기에 가까운 큰 사이즈 요청
                    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', 'type=w966', ''))
                    print(f"원본 URL 변환: {image_url} -> {clean_url}")
                    image_url = clean_url
                else:
                    # type 파라미터가 없으면 추가
                    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', 'type=w966', ''))
                    print(f"원본 URL 변환: {image_url} -> {clean_url}")
                    image_url = clean_url
            
            # 대상 디렉토리 설정
            if target_dir is None:
                target_dir = self.assets_dir
            
            # 이미지 다운로드
            headers = {"User-Agent": USER_AGENT}
            cookies = NAVER_COOKIES if any(domain in image_url for domain in ['naver.com', 'pstatic.net', 'blogfiles.naver.net', 'postfiles.naver.net']) else None
            response = requests.get(image_url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()
            
            # 이미지 데이터 로드
            image_data = response.content
            img = Image.open(io.BytesIO(image_data))
            
            print(f"다운로드된 이미지 크기: {img.width}x{img.height}px")
            
            # 원본 형식 저장
            original_format = img.format or "PNG"
            
            # 리사이징 (MAX_IMAGE_SIZE보다 큰 경우만)
            if img.width > self.max_size or img.height > self.max_size:
                ratio = min(self.max_size / img.width, self.max_size / img.height)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"리사이징: {new_width}x{new_height}px")
            
            # 파일명 생성
            if base_filename:
                ext = Path(urlparse(image_url).path).suffix or f".{original_format.lower()}"
                filename = f"{base_filename}{ext}"
            else:
                url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
                ext = f".{original_format.lower()}"
                filename = f"{url_hash}{ext}"
            
            # img 폴더 생성
            img_dir = target_dir / "img"
            img_dir.mkdir(parents=True, exist_ok=True)
            
            # 파일 저장
            filepath = img_dir / filename
            
            # 중복 파일명 처리
            counter = 1
            original_filepath = filepath
            while filepath.exists():
                stem = original_filepath.stem
                suffix = original_filepath.suffix
                filepath = img_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            # Track file
            self.created_files.append(filepath)
            
            # 이미지 저장
            if original_format in ["JPEG", "JPG"]:
                img.save(filepath, "JPEG", quality=95, optimize=True)  # 품질 향상: 85 -> 95
            elif original_format == "PNG":
                img.save(filepath, "PNG", optimize=True)
            else:
                img.save(filepath, original_format)
            
            # 상대 경로 반환 (img/filename.ext)
            return f"img/{filepath.name}"
            
        except Exception as e:
            print(f"이미지 다운로드/리사이징 실패 ({image_url}): {e}")
            return None
    
    def _resize_image(self, img: Image.Image) -> Image.Image:
        """이미지 리사이징 (비율 유지)"""
        width, height = img.size
        
        if width <= self.max_size and height <= self.max_size:
            return img
        
        # 비율 계산
        ratio = min(self.max_size / width, self.max_size / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        
        # 리사이징
        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)
