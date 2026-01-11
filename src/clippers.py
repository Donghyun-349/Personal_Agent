# -*- coding: utf-8 -*-
import re
import os
import html
import hashlib
from typing import Optional, Dict, Tuple, List
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import trafilatura
import youtube_transcript_api
import yt_dlp

from .config import USER_AGENT, REQUEST_TIMEOUT, NAVER_COOKIES
from .utils import sanitize_filename, ImageProcessor

# Forward declaration for type hinting
# from .generators import HTMLGenerator (Circular import avoidance: use TYPE_CHECKING or just 'HTMLGenerator')

class WebClipper:
    """일반 웹페이지 클리퍼"""
    
    def __init__(self, image_processor: ImageProcessor, html_generator = None):
        self.image_processor = image_processor
        self.html_generator = html_generator
    
    def _normalize_naver_url(self, url: str) -> str:
        """
        네이버 URL 정규화
        - 블로그: 모바일 → PC 변환
        """
        # 블로그: 모바일 → PC
        if "m.blog.naver.com" in url:
            url = url.replace("m.blog.naver.com", "blog.naver.com")
        
        return url
    
    def extract_naver_iframe_url(self, url: str) -> Optional[str]:
        """네이버 블로그의 iframe 내부 실제 URL 추출"""
        try:
            # 이미 정규화된 URL이 들어오므로 여기서는 변환하지 않음
            
            # 이미 PostView URL이면 그대로 반환
            if "PostView" in url:
                return url
            
            # iframe URL 추출
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 블로그용 프레임 (mainFrame)
            iframe = soup.find('iframe', {'id': 'mainFrame'})
            
            if iframe and iframe.get('src'):
                iframe_src = iframe.get('src')
                # 상대 경로인 경우 절대 경로로 변환
                if iframe_src.startswith('/'):
                    return "https://blog.naver.com" + iframe_src
                elif iframe_src.startswith('http'):
                    return iframe_src
                else:
                    return urljoin(url, iframe_src)
            
            return None
        except Exception as e:
            print(f"네이버 iframe URL 추출 실패: {e}")
            return None
    
    def _extract_naver_blog(self, url: str) -> Dict:
        """네이버 블로그 전용 추출 함수 - 네이버 에디터 구조 직접 파싱"""
        try:
            # 이미 정규화된 URL이 들어오므로 여기서는 변환하지 않음
            original_url = url
            
            # iframe URL 추출
            iframe_url = self.extract_naver_iframe_url(url)
            if not iframe_url:
                # iframe URL 추출 실패 시 원본 URL 사용 시도
                if "PostView" in url:
                    iframe_url = url
                else:
                    # 다시 한 번 시도
                    iframe_url = self.extract_naver_iframe_url(original_url)
                    if not iframe_url:
                        raise Exception("네이버 iframe URL 추출 실패")
            
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(iframe_url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 2. 제목 추출 (카페/블로그 공통 대응)
            title = "Untitled"
            title_elem = soup.select_one('.se-ff-nanumgothic.se-fs-32, .se-title-text, #title_1 span, .title_text, .article_header .title_text, h2.tit')
            if title_elem:
                title = title_elem.get_text(strip=True)
            else:
                title_tag = soup.find('div', class_='se-title-text') or soup.find('h3', class_='se-title-text')
                if not title_tag:
                    title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)
            title = re.sub(r'\s*:\s*네이버.*$', '', title).strip()
            
            # 3. 본문 컨테이너 찾기 (블로그 전용)
            main_container = soup.select_one('.se-main-container')  # 스마트에디터
            if not main_container:
                # 구형 에디터 대응
                main_container = soup.select_one('#postViewArea')
            if not main_container:
                raise Exception("본문 영역을 찾을 수 없습니다 (비공개 글이거나 접근 권한이 없을 수 있습니다)")
            
            # 4. 모듈 단위 파싱 (Component-Based Parsing)
            content_parts = []
            image_counter = 0
            
            components = main_container.select('.se-component')
            
            for comp in components:
                classes = comp.get('class', [])
                class_str = ' '.join(classes)
                
                # A. 텍스트 컴포넌트 (se-text)
                if 'se-text' in class_str:
                    paragraphs = comp.select('.se-text-paragraph')
                    for p in paragraphs:
                        text = p.get_text(separator=" ", strip=True)
                        if not text:
                            continue
                        
                        if p.find_parent(class_='se-section-text'):
                            content_parts.append(f"\n### {text}\n\n")
                        else:
                            if p.select('b, strong'):
                                bold_text = p.find(['b', 'strong'])
                                if bold_text and bold_text.get_text(strip=True) == text:
                                    content_parts.append(f"**{text}**\n\n")
                                else:
                                    content_parts.append(f"{text}\n\n")
                            else:
                                content_parts.append(f"{text}\n\n")
                    if paragraphs:
                        content_parts.append("")
                
                # B. 이미지 컴포넌트 (se-image)
                elif 'se-image' in class_str:
                    imgs = comp.select('img.se-image-resource')
                    for img in imgs:
                        img_src = img.get('src') or img.get('data-lazy-src') or img.get('data-src') or img.get('data-original')
                        if img_src:
                            if img_src.startswith('//'):
                                img_src = 'https:' + img_src
                            elif img_src.startswith('/'):
                                parsed = urlparse(iframe_url)
                                img_src = f"{parsed.scheme}://{parsed.netloc}{img_src}"
                            elif not img_src.startswith('http'):
                                img_src = urljoin(iframe_url, img_src)
                            
                            if img_src.startswith('http') and (
                                'blogfiles.naver.net' in img_src or 
                                'postfiles.naver.net' in img_src or
                                'blogpfthumb.pstatic.net' in img_src or
                                'ssl.pstatic.net' in img_src or
                                'postfiles.pstatic.net' in img_src
                            ):
                                image_counter += 1
                                local_path = self.image_processor.download_and_resize(
                                    img_src,
                                    base_filename=f"{sanitize_filename(title)}_img_{image_counter}"
                                )
                                if local_path:
                                    content_parts.append(f"\n![Image {image_counter}]({local_path})\n\n")
                                else:
                                    content_parts.append(f"\n![Image {image_counter}]({img_src})\n\n")
                
                # C. 표 (Table)
                elif 'se-table' in class_str:
                    table = comp.find('table')
                    if table:
                        content_parts.append(f"\n{str(table)}\n\n")
                
                # D. 인용구
                elif 'se-quote' in class_str:
                    quote_container = comp.select_one('.se-quote-container, .se-quote-module')
                    if quote_container:
                        for script in quote_container(["script", "style"]):
                            script.extract()
                        content_parts.append(f"\n{str(quote_container)}\n\n")
                    else:
                        text = comp.get_text(separator=" ", strip=True)
                        if text:
                            content_parts.append(f"\n> {text}\n\n")
                
                # E. 구분선
                elif 'se-horizontalLine' in class_str:
                    content_parts.append("\n---\n\n")
                
                # F. 외부 링크 (oglink)
                elif 'se-oglink' in class_str:
                    oglink_html = self._process_oglink(comp, title, iframe_url)
                    if oglink_html:
                        content_parts.append(f"\n{oglink_html}\n\n")
                
                # G. 기타
                else:
                    for script in comp(["script", "style"]):
                        script.extract()
                    comp_html = str(comp)
                    if comp_html and len(comp_html.strip()) > 10:
                        content_parts.append(f"\n{comp_html}\n\n")
            
            markdown_content = '\n'.join(content_parts)
            
            # HTML 컨테이너 준비
            main_container_html = self._prepare_html_container(main_container, title, iframe_url)
            
            # 후처리
            markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
            markdown_content = self._clean_naver_messages(markdown_content)
            
            return {
                "title": title,
                "content": markdown_content,
                "url": url,
                "type": "article",
                "html_content": main_container_html
            }
            
        except Exception as e:
            print(f"네이버 블로그 추출 실패: {e}")
            try:
                return self._fallback_extract(url)
            except Exception as e2:
                print(f"폴백 추출도 실패: {e2}")
                return {
                    "title": "Untitled",
                    "content": f"추출 실패: {str(e)}",
                    "url": url,
                    "type": "article",
                    "html_content": ""
                }
    
    def _process_oglink(self, oglink_comp, base_title: str, base_url: str) -> str:
        """외부 링크(oglink) 처리"""
        try:
            link_elem = oglink_comp.find('a', class_='se-oglink-info') or oglink_comp.find('a')
            if not link_elem:
                return ""
            
            link_url = link_elem.get('href', '')
            if not link_url:
                return ""
            
            title_elem = oglink_comp.find(class_='se-oglink-title') or oglink_comp.find('strong', class_='se-oglink-title')
            link_title = title_elem.get_text(strip=True) if title_elem else ""
            
            desc_elem = oglink_comp.find(class_='se-oglink-summary') or oglink_comp.find(class_='se-oglink-desc')
            link_desc = desc_elem.get_text(strip=True) if desc_elem else ""
            
            url_elem = oglink_comp.find(class_='se-oglink-url')
            link_domain = url_elem.get_text(strip=True) if url_elem else ""
            if not link_domain and link_url:
                try:
                    parsed = urlparse(link_url)
                    link_domain = parsed.netloc
                except:
                    link_domain = link_url
            
            # 썸네일
            thumbnail_elem = oglink_comp.find('img', class_='se-oglink-thumbnail-resource') or oglink_comp.find('img', class_='se-oglink-thumbnail')
            thumbnail_local_path = None
            
            if thumbnail_elem:
                thumbnail_url = (thumbnail_elem.get('src') or 
                                thumbnail_elem.get('data-src') or 
                                thumbnail_elem.get('data-lazy-src'))
                
                if thumbnail_url:
                    if thumbnail_url.startswith('//'):
                        thumbnail_url = 'https:' + thumbnail_url
                    elif thumbnail_url.startswith('/'):
                        parsed = urlparse(base_url)
                        thumbnail_url = f"{parsed.scheme}://{parsed.netloc}{thumbnail_url}"
                    elif not thumbnail_url.startswith('http'):
                        thumbnail_url = urljoin(base_url, thumbnail_url)
                    
                    if thumbnail_url.startswith('http') and self.html_generator:
                        thumbnail_local_path = self.html_generator.download_image_for_html(
                            thumbnail_url,
                            base_filename=f"{sanitize_filename(base_title)}_oglink"
                        )
            
            # HTML 생성
            if thumbnail_local_path:
                oglink_html = f"""<div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin: 20px 0; background-color: #fafafa; display: flex; gap: 16px; text-decoration: none; color: inherit;">
    <div style="flex: 0 0 120px;">
        <img src="{thumbnail_local_path}" alt="{link_title}" style="width: 120px; height: 120px; object-fit: cover; border-radius: 4px; display: block;" />
    </div>
    <div style="flex: 1; min-width: 0;">
        <div style="font-weight: bold; font-size: 16px; margin-bottom: 8px; color: #333;">
            <a href="{link_url}" target="_blank" style="color: #333; text-decoration: none;">{link_title or '링크'}</a>
        </div>
        {f'<div style="font-size: 14px; color: #666; margin-bottom: 8px; line-height: 1.5;">{link_desc}</div>' if link_desc else ''}
        <div style="font-size: 12px; color: #999;">
            <a href="{link_url}" target="_blank" style="color: #999; text-decoration: none;">{link_domain}</a>
        </div>
    </div>
</div>"""
            else:
                oglink_html = f"""<div style="border-left: 4px solid #4a90e2; padding: 12px 16px; margin: 20px 0; background-color: #f5f8ff;">
    <div style="font-weight: bold; font-size: 16px; margin-bottom: 8px;">
        <a href="{link_url}" target="_blank" style="color: #4a90e2; text-decoration: none;">{link_title or '링크'}</a>
    </div>
    {f'<div style="font-size: 14px; color: #666; margin-bottom: 8px;">{link_desc}</div>' if link_desc else ''}
    <div style="font-size: 12px; color: #999;">
        <a href="{link_url}" target="_blank" style="color: #999; text-decoration: none;">{link_domain}</a>
    </div>
</div>"""
            return oglink_html
        
        except Exception as e:
            print(f"oglink 처리 실패: {e}")
            for script in oglink_comp(["script", "style"]):
                script.extract()
            return str(oglink_comp)

    def _prepare_html_container(self, main_container, title: str, base_url: str) -> str:
        """HTML 저장을 위한 컨테이너 준비"""
        try:
            container_copy = BeautifulSoup(str(main_container), 'html.parser')
            
            for tag in container_copy.select('script, style, button, .se-documentTitle, .article_writer, .CommentBox, .ccl'):
                tag.decompose()
            
            oglink_components = container_copy.select('.se-component.se-oglink')
            for oglink_comp in oglink_components:
                oglink_html = self._process_oglink(oglink_comp, title, base_url)
                if oglink_html:
                    oglink_comp.replace_with(BeautifulSoup(oglink_html, 'html.parser'))
            
            imgs = container_copy.select('img')
            for img in imgs:
                candidates = [
                    img.get('data-lazy-src'),
                    img.get('src'),
                    img.get('data-src'),
                    img.get('data-original')
                ]
                real_src = None
                for src in candidates:
                    if src and src.startswith(('http://', 'https://')):
                        real_src = src
                        break
                
                if real_src:
                    if real_src.startswith('//'):
                        real_src = 'https:' + real_src
                    elif real_src.startswith('/'):
                        parsed = urlparse(base_url)
                        real_src = f"{parsed.scheme}://{parsed.netloc}{real_src}"
                    elif not real_src.startswith(('http://', 'https://')):
                        real_src = urljoin(base_url, real_src)
                    
                    if real_src.startswith(('http://', 'https://')):
                        if self.html_generator:
                            local_path = self.html_generator.download_image_for_html(
                                real_src,
                                base_filename=sanitize_filename(title)
                            )
                            if local_path:
                                img['src'] = local_path
                                if img.has_attr('data-lazy-src'): del img['data-lazy-src']
                                if img.has_attr('data-src'): del img['data-src']
                                if img.has_attr('data-original'): del img['data-original']
                                img['style'] = "max-width: 100%; height: auto;"
                else:
                    img['style'] = "display: none;"
            
            for iframe in container_copy.select('iframe'):
                iframe_src = iframe.get('src')
                if iframe_src and not iframe_src.startswith(('http://', 'https://')):
                    if iframe_src.startswith('//'):
                        iframe['src'] = 'https:' + iframe_src
                    elif iframe_src.startswith('/'):
                        parsed = urlparse(base_url)
                        iframe['src'] = f"{parsed.scheme}://{parsed.netloc}{iframe_src}"
                    else:
                        iframe['src'] = urljoin(base_url, iframe_src)
            
            for video in container_copy.select('video'):
                video_src = video.get('src')
                if video_src and not video_src.startswith(('http://', 'https://')):
                    if video_src.startswith('//'):
                        video['src'] = 'https:' + video_src
                    elif video_src.startswith('/'):
                        parsed = urlparse(base_url)
                        video['src'] = f"{parsed.scheme}://{parsed.netloc}{video_src}"
                    else:
                        video['src'] = urljoin(base_url, video_src)
            
            return str(container_copy)
        except Exception as e:
            print(f"HTML 컨테이너 준비 실패: {e}")
            return str(main_container)

    def extract_content(self, url: str) -> Dict:
        """웹페이지 콘텐츠 추출"""
        parsed_url = urlparse(url)
        is_naver_blog = (parsed_url.netloc in ['blog.naver.com', 'm.blog.naver.com'] or 
                        'blog.naver.com' in parsed_url.netloc)
        
        if is_naver_blog:
            url = self._normalize_naver_url(url)
            result = self._extract_naver_blog(url)
            return result
        
        try:
            headers = {"User-Agent": USER_AGENT}
            downloaded = trafilatura.fetch_url(url, no_ssl=False)
            
            if not downloaded:
                raise Exception("페이지 다운로드 실패")
            
            article = trafilatura.extract(
                downloaded,
                include_images=True,
                include_links=False,
                output_format='markdown',
                favor_recall=True,
                include_comments=False,
                include_tables=True
            )
            
            if not article or len(article) < 100:
                raise Exception("콘텐츠 추출 실패 또는 내용이 너무 짧음")
            
            metadata = trafilatura.extract_metadata(downloaded)
            title = metadata.title if metadata and metadata.title else "Untitled"
            
            markdown_content = self._process_images(article, title, base_url=url)
            
            html_content = ""
            try:
                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                main_container = soup.find('article') or soup.find('main')
                if not main_container:
                    main_container = soup.find('div', class_=re.compile(r'content|article|post|entry|view|body', re.I))
                if not main_container:
                    main_container = soup.find('body')
                
                if main_container:
                    html_content = self._prepare_html_container(main_container, title, url)
            except Exception as e:
                print(f"HTML 추출 실패 (Markdown만 사용): {e}")
            
            return {
                "title": title,
                "content": markdown_content,
                "url": url,
                "type": "article",
                "html_content": html_content
            }
            
        except Exception as e:
            print(f"trafilatura 추출 실패: {e}")
            return self._fallback_extract(url)

    def _process_images(self, markdown_content: str, base_title: str, base_url: str = None, target_dir = None) -> str:
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        
        def replace_image(match):
            alt_text = match.group(1)
            image_url = match.group(2)
            
            if not image_url.startswith(('http://', 'https://')):
                return match.group(0)
            
            if base_url and not image_url.startswith(('http://', 'https://')):
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                elif image_url.startswith('/'):
                    parsed = urlparse(base_url)
                    image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"
                else:
                    image_url = urljoin(base_url, image_url)
            
            if image_url.startswith(('http://', 'https://')):
                local_path = self.image_processor.download_and_resize(
                    image_url,
                    base_filename=sanitize_filename(base_title),
                    target_dir=target_dir
                )
                if local_path:
                    return f"![{alt_text}]({local_path})"
            
            return match.group(0)
        
        return re.sub(pattern, replace_image, markdown_content)

    def _clean_naver_messages(self, content: str) -> str:
        lines = content.split('\n')
        cleaned_lines = []
        seen_lines = set()
        
        remove_patterns = [
            r'저작권 침해가 우려되는', r'글보내기 기능을 제한합니다', r'네이버는 블로그를 통해',
            r'저작물이 무단으로 공유되는 것을 막기 위해', r'저작권을 침해하는 컨텐츠가 포함되어 있는',
            r'상세한 안내를 받고 싶으신 경우', r'네이버 고객센터로 문의주시면',
            r'건강한 인터넷 환경을 만들어 나갈 수 있도록', r'고객님의 많은 관심과 협조를 부탁드립니다',
            r'메뉴 바로가기', r'본문 바로가기', r'작성하신.*이용자들의 신고가 많은 표현이 포함',
            r'다른 표현을 사용해주시기 바랍니다', r'건전한 인터넷 문화 조성을 위해',
            r'회원님의 적극적인 협조를 부탁드립니다', r'더 궁금하신 사항은 고객센터로 문의하시면',
            r'^## 블로그$', r'^댓글\d+$', r'^\s*\|+\s*$', r'blog\.naver\.com.*\.\.\.',
            r'안녕하세요\. 오랜만입니다\. 향후 이 시리즈로',
        ]
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                if cleaned_lines and cleaned_lines[-1].strip() == '':
                    continue
                cleaned_lines.append('')
                continue
            
            line_hash = hashlib.md5(line_stripped.encode('utf-8')).hexdigest()
            if line_hash in seen_lines:
                continue
            seen_lines.add(line_hash)
            
            should_remove = False
            for pattern in remove_patterns:
                if re.search(pattern, line_stripped, re.IGNORECASE):
                    should_remove = True
                    break
            
            if line_stripped.startswith('|') and len(line_stripped) < 50:
                if '|' in line_stripped[1:] and line_stripped.count('|') >= 2:
                    should_remove = True
            
            if 'blog.naver.com' in line_stripped and len(line_stripped) < 100:
                if '...' in line_stripped or line_stripped.endswith('blog.naver.com'):
                    should_remove = True
            
            if not should_remove:
                cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = result.strip()
        result = re.sub(r'작성하신\s*\*+.*?댓글\d+', '', result, flags=re.DOTALL)
        
        lines_final = result.split('\n')
        deduplicated = []
        prev_line = None
        prev_prev_line = None
        
        for line in lines_final:
            line_stripped = line.strip()
            if line_stripped and line_stripped == prev_line: continue
            if line_stripped and line_stripped == prev_prev_line and prev_line == '': continue
            prev_prev_line = prev_line
            prev_line = line_stripped
            deduplicated.append(line)
        
        result = '\n'.join(deduplicated)
        
        lines = result.split('\n')
        final_lines = []
        for i, line in enumerate(lines):
            if not line.strip():
                final_lines.append(line)
                continue
            
            is_duplicate = False
            for prev_line in final_lines[-5:]:
                if prev_line.strip() and len(prev_line.strip()) > 20:
                    similarity = len(set(line.strip()) & set(prev_line.strip())) / max(len(set(line.strip())), len(set(prev_line.strip())), 1)
                    if similarity > 0.9:
                        is_duplicate = True
                        break
            if not is_duplicate:
                final_lines.append(line)
        
        return '\n'.join(final_lines)

    def _fallback_extract(self, url: str) -> Dict:
        try:
            iframe_url = self.extract_naver_iframe_url(url)
            if iframe_url and iframe_url != url:
                url = iframe_url
            
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('title')
            title = title_tag.text.strip() if title_tag else "Untitled"
            title = re.sub(r'\s*:\s*네이버.*$', '', title)
            
            main_container = soup.select_one('.se-main-container')
            if not main_container: main_container = soup.select_one('#postViewArea')
            
            html_content = ""
            if main_container:
                html_content = self._prepare_html_container(main_container, title, url)
            else:
                content_tags = soup.find_all(['article', 'main', 'div'], class_=re.compile(r'content|article|post|entry|view', re.I))
                if not content_tags: content_tags = [soup.find('body')]
                if content_tags and content_tags[0]:
                    html_content = self._prepare_html_container(content_tags[0], title, url)
            
            if main_container:
                content_tags = [main_container]
            else:
                content_tags = soup.find_all(['article', 'main', 'div'], class_=re.compile(r'content|article|post|entry|view', re.I))
                if not content_tags: content_tags = [soup.find('body')]
            
            content_parts = []
            image_urls = []
            
            for tag in content_tags:
                if tag:
                    for script in tag(["script", "style", "nav", "header", "footer", "aside", "advertisement"]):
                        script.decompose()
                    
                    images = tag.find_all('img')
                    for img in images:
                        img_src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                        if img_src:
                            if img_src.startswith('//'): img_src = 'https:' + img_src
                            elif img_src.startswith('/'):
                                parsed = urlparse(url)
                                img_src = f"{parsed.scheme}://{parsed.netloc}{img_src}"
                            elif not img_src.startswith('http'): img_src = urljoin(url, img_src)
                            
                            if img_src.startswith('http') and img_src not in image_urls:
                                image_urls.append(img_src)
                    
                    paragraphs = tag.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre'])
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 3:
                            if p.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                level = int(p.name[1])
                                content_parts.append(f"{'#' * level} {text}\n\n")
                            else:
                                content_parts.append(f"{text}\n\n")
            
            content_text = ''.join(content_parts)
            for img_url in image_urls:
                local_path = self.image_processor.download_and_resize(
                    img_url, base_filename=sanitize_filename(title)
                )
                if local_path: content_text += f"![Image]({local_path})\n\n"
                else: content_text += f"![Image]({img_url})\n\n"
            
            content_text = self._clean_naver_messages(content_text)
            
            return {
                "title": title,
                "content": content_text,
                "url": url,
                "type": "article",
                "html_content": html_content
            }
        except Exception as e:
            raise Exception(f"폴백 추출도 실패: {e}")

class YouTubeClipper:
    """YouTube 동영상 클리퍼"""
    
    def __init__(self, image_processor: ImageProcessor, log_callback=None):
        self.image_processor = image_processor
        self.log = log_callback if log_callback else print
    
    def extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match: return match.group(1)
        return None
    
    def get_thumbnail_url(self, video_id: str) -> str:
        url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        response = requests.head(url, timeout=5)
        if response.status_code == 200: return url
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    
    def _get_cookie_file(self) -> Optional[str]:
        # Check for cookies (Priority: Env Var Path > Local 'cookies.txt')
        cookie_file = os.getenv("YOUTUBE_COOKIES_PATH")
        if not cookie_file and os.path.exists("cookies.txt"):
            cookie_file = "cookies.txt"
        return cookie_file

    def extract_transcript(self, video_id: str) -> Tuple[Optional[str], bool]:
        self.log(f"🎬 자막 추출 시도: {video_id}")
        
        cookie_file = self._get_cookie_file()
        if cookie_file:
            self.log(f"🍪 쿠키 파일 발견: {cookie_file}")
        
        # 1. Try youtube-transcript-api first
        try:
            self.log("1단계: youtube-transcript-api 시도 중...")
            import sys
            # DEBUG Info
            self.log(f"DEBUG: youtube_transcript_api file: {getattr(youtube_transcript_api, '__file__', 'No __file__')}")
            
            # The class might be shadowed or behave differently in some environments
            YTApi = youtube_transcript_api.YouTubeTranscriptApi
            
            # Attempt list_transcripts (modern) or get_transcript (legacy)
            if hasattr(YTApi, 'list_transcripts'):
                if cookie_file:
                    transcript_list_obj = YTApi.list_transcripts(video_id, cookies=cookie_file)
                else:
                    transcript_list_obj = YTApi.list_transcripts(video_id)
                transcript = transcript_list_obj.find_transcript(['ko', 'en'])
                transcript_data = transcript.fetch()
                language = transcript.language
            elif hasattr(YTApi, 'get_transcript'):
                if cookie_file:
                    transcript_data = YTApi.get_transcript(video_id, languages=['ko', 'en'], cookies=cookie_file)
                else:
                    transcript_data = YTApi.get_transcript(video_id, languages=['ko', 'en'])
                language = "unknown"
            else:
                raise AttributeError(f"YouTubeTranscriptApi has neither list_transcripts nor get_transcript. Dir: {dir(YTApi)}")
            
            # Format transcript
            formatter = []
            for item in transcript_data:
                start = item['start']
                text = item['text']
                minutes = int(start // 60)
                seconds = int(start % 60)
                time_str = f"{minutes:02d}:{seconds:02d}"
                formatter.append(f"[{time_str}] {text}")
            
            full_text = "\n".join(formatter)
            self.log(f"✅ youtube-transcript-api 자막 추출 성공 ({language}, {len(full_text)}자)")
            return full_text, True
            
        except Exception as e:
            self.log(f"⚠️ 1단계 실패 ({e}). 2단계(yt-dlp)로 전환합니다.")

        # 2. Try yt-dlp as fallback
        try:
            self.log("2단계: yt-dlp로 자막 정보 조회 중...")
            ydl_opts = {
                'writesubtitles': True, 'writeautomaticsub': True,
                'subtitleslangs': ['ko', 'en'], 'skip_download': True, 'quiet': True,
            }
            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                subtitles = info.get('requested_subtitles')
                if not subtitles: subtitles = info.get('automatic_captions')

                if subtitles:
                    self.log(f"  → 자막 발견: {list(subtitles.keys())}")
                    for lang in ['ko', 'en']:
                        if lang in subtitles:
                            self.log(f"  → {lang} 자막 다운로드 시도 중...")
                            subs_data = subtitles[lang]
                            target_url = None
                            
                            if isinstance(subs_data, list):
                                for item in subs_data:
                                    if isinstance(item, dict) and item.get('url'):
                                        target_url = item['url']
                                        break
                            elif isinstance(subs_data, dict):
                                if subs_data.get('url'): target_url = subs_data['url']
                            
                            if target_url:
                                res = requests.get(target_url, timeout=REQUEST_TIMEOUT)
                                if res.status_code == 200:
                                    text = self._parse_webvtt(res.text)
                                    self.log(f"✅ yt-dlp로 자막 추출 성공 ({lang}, {len(text)}자)")
                                    return text, True
                            else:
                                self.log(f"  → {lang} 자막에서 URL을 찾을 수 없음")
                else:
                    self.log("  → 자막 정보를 찾을 수 없음")
                    
        except Exception as e:
            self.log(f"❌ yt-dlp 자막 추출 실패: {e}")

        self.log("❌ 모든 자막 추출 방법 실패")
        return None, False
    
    def _time_to_seconds(self, time_str: str) -> int:
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s
    
    def _parse_webvtt(self, webvtt_text: str) -> str:
        lines = webvtt_text.split('\n')
        final_output = []       
        current_chunk = []      
        chunk_start_seconds = 0
        current_seconds = 0
        chunk_start_time_str = "00:00:00"
        
        time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2})')
        seen_lines = set()
        is_body_started = False 

        MIN_DURATION = 20
        MAX_DURATION = 40

        for line in lines:
            line = line.strip()
            time_match = time_pattern.search(line)
            if time_match:
                time_str = time_match.group(1)
                current_seconds = self._time_to_seconds(time_str)
                is_body_started = True 
                if not current_chunk:
                    chunk_start_time_str = time_str
                    chunk_start_seconds = current_seconds

            if not line or line.startswith('WEBVTT') or '-->' in line or line.isdigit() or not is_body_started:
                continue

            line = html.unescape(line)
            clean_text = re.sub(r'<[^>]+>', '', line).strip()
            clean_text = re.sub(r'^[>\s\-]+', '', clean_text).strip()
            
            if clean_text and clean_text not in seen_lines:
                current_chunk.append(clean_text)
                seen_lines.add(clean_text)
                
                duration = current_seconds - chunk_start_seconds
                if duration >= MIN_DURATION:
                    if clean_text[-1] in ['.', '?', '!'] or duration >= MAX_DURATION:
                        full_paragraph = " ".join(current_chunk)
                        final_output.append(f"[{chunk_start_time_str}] {full_paragraph}")
                        current_chunk = []
                        chunk_start_seconds = current_seconds

        if current_chunk:
            full_paragraph = " ".join(current_chunk)
            final_output.append(f"[{chunk_start_time_str}] {full_paragraph}")

        return '\n\n'.join(final_output)
    
    def extract_metadata(self, video_id: str) -> Dict:
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            cookie_file = self._get_cookie_file()
            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return {
                    "title": info.get('title', 'Untitled'),
                    "channel": info.get('uploader', 'Unknown'),
                    "upload_date": info.get('upload_date', ''),
                    "description": info.get('description', '')[:500]
                }
        except Exception as e:
            self.log(f"메타데이터 추출 실패: {e}")
            return {"title": "Untitled", "channel": "Unknown", "upload_date": "", "description": ""}
    
    def _extract_via_browser(self, url: str) -> Dict:
        """Playwright를 이용해 브라우저 상에서 직접 정보와 자막 추출 (쿠키 불필요)"""
        from playwright.sync_api import sync_playwright
        import time
        import traceback

        self.log(f"🌐 브라우저 기반 추출 시작: {url}")
        
        result = {
            "title": "Untitled",
            "channel": "Unknown",
            "upload_date": "",
            "description": "",
            "transcript": None,
            "success": False
        }

        try:
            with sync_playwright() as p:
                self.log("  → Playwright 초기화 완료")
                browser = p.chromium.launch(headless=True)
                self.log("  → 브라우저 실행 완료")
                
                # 실제 브라우저처럼 보이도록 User-Agent 및 언어 설정
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    locale="ko-KR"
                )
                page = context.new_page()
                self.log("  → 페이지 생성 완료")
                
                # 타임아웃 설정 및 페이지 이동
                self.log(f"  → 페이지 로딩 중: {url}")
                page.goto(url, wait_until="networkidle", timeout=60000)
                self.log("  → 페이지 로딩 완료")
                time.sleep(3) # 추가 렌더링 대기

                # 1. 메타데이터 추출
                try:
                    result["title"] = page.title().replace(" - YouTube", "")
                    self.log(f"  → 제목 추출: {result['title']}")
                    # 채널명 추출 (다양한 셀렉터 시도)
                    channel_elem = page.query_selector("#upload-info #channel-name a, #owner #channel-name a")
                    if channel_elem:
                        result["channel"] = channel_elem.inner_text()
                        self.log(f"  → 채널명 추출: {result['channel']}")
                except Exception as me:
                    self.log(f"⚠️ 브라우저 메타데이터 추출 중 경고: {me}")
                    self.log(f"   상세: {traceback.format_exc()}")

                # 2. 자막 창 열기 시도
                try:
                    self.log("  → 자막 버튼 찾는 중...")
                    # '더보기' 버튼 클릭하여 설명란 확장
                    more_button = page.query_selector("#description-inner #expand, .ytd-video-secondary-info-renderer #more")
                    if more_button:
                        more_button.click()
                        time.sleep(1)
                    
                    # '스크립트 표시' 버튼 찾기 및 클릭
                    # 한국어/영어 버튼 텍스트 대응
                    transcript_button = page.get_by_role("button", name=re.compile(r"스크립트 표시|Show transcript", re.I))
                    if transcript_button.count() > 0:
                        self.log("  → 자막 버튼 발견, 클릭 중...")
                        transcript_button.first.click()
                        time.sleep(2)
                        
                        # 자막 텍스트 수집
                        segments = page.query_selector_all("ytd-transcript-segment-renderer")
                        self.log(f"  → 자막 세그먼트 {len(segments)}개 발견")
                        if segments:
                            formatter = []
                            for seg in segments:
                                time_elem = seg.query_selector(".segment-timestamp")
                                text_elem = seg.query_selector(".segment-text")
                                if time_elem and text_elem:
                                    t_str = time_elem.inner_text().strip()
                                    txt = text_elem.inner_text().strip()
                                    formatter.append(f"[{t_str}] {txt}")
                            
                            result["transcript"] = "\n".join(formatter)
                            self.log(f"✅ 브라우저로 자막 추출 성공 ({len(result['transcript'])}자)")
                            result["success"] = True
                        else:
                            self.log("  → 자막 세그먼트를 찾을 수 없음")
                    else:
                        self.log("  → 자막 버튼을 찾을 수 없음")
                except Exception as te:
                    self.log(f"⚠️ 브라우저 자막 추출 중 실패: {te}")
                    self.log(f"   상세: {traceback.format_exc()}")

                browser.close()
                return result

        except Exception as e:
            self.log(f"❌ 브라우저 기반 추출 전체 실패: {e}")
            self.log(f"   상세: {traceback.format_exc()}")
            return result

    def extract_content(self, url: str) -> Dict:
        video_id = self.extract_video_id(url)
        if not video_id: raise Exception("YouTube 영상 ID를 추출할 수 없습니다.")
        
        # 1순위: 브라우저 기반 추출 시도 (쿠키 없이 가장 강력함)
        browser_data = self._extract_via_browser(url)
        
        # 결과 결합
        if browser_data["success"]:
            metadata = browser_data
            transcript = browser_data["transcript"]
            has_transcript = True
        else:
            # 2순위: 기존 방식들로 시도 (백업)
            self.log("🔄 브라우저 추출 실패. 기존 API/라이브러리 방식으로 전환합니다.")
            metadata = self.extract_metadata(video_id)
            transcript, has_transcript = self.extract_transcript(video_id)
            
        thumbnail_url = self.get_thumbnail_url(video_id)
        
        content_parts = []
        if thumbnail_url: content_parts.append(f"![Thumbnail]({thumbnail_url})\n")
        
        if transcript:
            content_parts.append("## 자막\n\n")
            content_parts.append(transcript)
        else:
            content_parts.append("## 안내\n\n")
            content_parts.append("자막을 추출할 수 없습니다. 향후 요약을 위해서는 자막이 필요합니다.\n\n")
            if metadata.get("description"):
                content_parts.append("### 동영상 설명\n\n")
                content_parts.append(metadata["description"])
        
        return {
            "title": metadata["title"],
            "channel": metadata.get("channel", "Unknown"),
            "content": "".join(content_parts),
            "video_id": video_id,
            "url": url,
            "type": "youtube",
            "has_transcript": has_transcript
        }
