# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os
import sys
import re
import threading
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except:
        pass

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from clippers import YouTubeClipper, WebClipper
from generators import MarkdownGenerator, PDFGenerator
from utils import ImageProcessor
from summarizer import GeminiSummarizer
from uploader import GDriveUploader

# Load environment variables
load_dotenv()

class ClipperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Web Clipper & Summarizer")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Initialize components
        self.setup_directories()
        self.setup_components()
        
        # Processing control
        self.is_processing = False
        self.current_thread = None
        
        # Create GUI
        self.create_widgets()
        
    def setup_directories(self):
        """디렉토리 설정"""
        base_dir = Path(__file__).parent
        self.assets_dir = base_dir / 'assets'
        self.clippings_dir = base_dir / 'clippings'
        self.assets_dir.mkdir(exist_ok=True)
        self.clippings_dir.mkdir(exist_ok=True)
        
    def setup_components(self):
        """컴포넌트 초기화"""
        self.image_processor = ImageProcessor(self.assets_dir)
        self.md_gen = MarkdownGenerator(self.clippings_dir)
        self.pdf_gen = PDFGenerator(self.clippings_dir, self.assets_dir)
        
        # API 키 및 토큰 설정
        api_key = os.getenv('GOOGLE_API_KEY')
        token_json = os.getenv('GOOGLE_TOKEN_JSON')
        self.folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        
        self.summarizer = GeminiSummarizer(api_key) if api_key else None
        self.uploader = None
        
        if token_json:
            self.uploader = GDriveUploader()
            self.uploader.authenticate(token_json)
    
    def create_widgets(self):
        """GUI 위젯 생성"""
        # 상단 프레임
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        # 제목
        title_label = ttk.Label(top_frame, text="📋 Web Clipper & Summarizer", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # URL 입력
        url_frame = ttk.Frame(top_frame)
        url_frame.pack(fill=tk.X, pady=5)
        
        
        ttk.Label(url_frame, text="URL:", font=('Arial', 10)).pack(side=tk.LEFT, padx=(0, 5))
        self.url_entry = ttk.Entry(url_frame, font=('Arial', 10))
        self.url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # 시작 버튼 (URL 옆)
        self.start_button = ttk.Button(url_frame, text="🚀 시작", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT)
        
        # 진행 상태 표시
        progress_frame = ttk.Frame(top_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # 중지 버튼 (프로그레스 바 옆)
        self.stop_button = ttk.Button(progress_frame, text="⏹ 중지", command=self.stop_processing, state='disabled')
        self.stop_button.pack(side=tk.LEFT)
        
        # 상태 표시 라벨 (중지 버튼 옆)
        self.status_label = ttk.Label(progress_frame, text="대기 중...", font=('Arial', 9))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # 로그 출력 영역
        log_frame = ttk.LabelFrame(self.root, text="처리 로그", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, 
                                                  font=('Consolas', 9), 
                                                  height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def log(self, message, level='INFO'):
        """로그 메시지 출력"""
        colors = {
            'INFO': 'black',
            'SUCCESS': 'green',
            'WARNING': 'orange',
            'ERROR': 'red'
        }
        
        self.log_text.insert(tk.END, f"{message}\n")
        # 마지막 줄 색상 변경
        last_line = self.log_text.index('end-1c linestart')
        self.log_text.tag_add(level, last_line, 'end-1c')
        self.log_text.tag_config(level, foreground=colors.get(level, 'black'))
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def update_status(self, message):
        """상태 표시 업데이트"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def start_processing(self):
        """처리 시작"""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("오류", "URL을 입력해주세요!")
            return
        
        # 버튼 상태 변경
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.is_processing = True
        
        # 로그에 구분선 추가 (누적 모드)
        if self.log_text.get(1.0, tk.END).strip():
            self.log("\n" + "="*60 + "\n", 'INFO')
        
        self.progress_bar.start()
        
        # 별도 스레드에서 처리
        self.current_thread = threading.Thread(target=self.process_url, args=(url,), daemon=True)
        self.current_thread.start()
        
    def stop_processing(self):
        """처리 중지"""
        if self.is_processing:
            self.is_processing = False
            self.log("\n⏹ 사용자가 작업을 중지했습니다.", 'WARNING')
            self.update_status("중지됨")
    
    def process_url(self, url):
        """URL 처리 (별도 스레드)"""
        try:
            self.log(f"🔗 URL: {url}", 'INFO')
            
            # 중지 확인
            if not self.is_processing:
                return
            
            # API 키 확인
            if not self.summarizer:
                self.log("⚠️ GOOGLE_API_KEY가 설정되지 않았습니다. 요약 기능을 건너뜁니다.", 'WARNING')
            
            if not self.uploader:
                self.log("⚠️ Google Drive 인증 정보가 없습니다. 업로드를 건너뜁니다.", 'WARNING')
            
            # 콘텐츠 타입 판별
            is_youtube = 'youtube.com' in url or 'youtu.be' in url
            
            # 콘텐츠 추출
            self.update_status("콘텐츠 추출 중...")
            if is_youtube:
                self.log("🎥 YouTube 영상 처리 중...", 'INFO')
                clipper = YouTubeClipper(self.image_processor)
            else:
                self.log("🌐 웹 페이지 처리 중...", 'INFO')
                clipper = WebClipper(self.image_processor)
            
            data = clipper.extract_content(url)
            self.log(f"✅ 추출 완료: {data['title']}", 'SUCCESS')
            
            # 중지 확인
            if not self.is_processing:
                return
            
            # YouTube 처리
            if is_youtube:
                # 요약 생성
                if self.summarizer:
                    self.update_status("AI 요약 생성 중...")
                    self.log("🤖 AI 요약 생성 중...", 'INFO')
                    
                    metadata = {}
                    if data.get('use_gemini_url'):
                        metadata['use_gemini_url'] = True
                        metadata['youtube_url'] = data['url']
                        metadata['video_title'] = data.get('title', '제목 없음')
                    
                    summary = self.summarizer.summarize_text(
                        data['content'],
                        content_type='youtube',
                        metadata=metadata
                    )
                    
                    if summary:
                        if data.get('use_gemini_url'):
                            title_match = re.search(r'^#\s+(.+)$', summary, re.MULTILINE)
                            if title_match:
                                data['title'] = title_match.group(1).strip()
                        
                        data['content'] = f"{summary}\n\n---\n\n{data['content']}"
                        self.log("✅ 요약 완료", 'SUCCESS')
                
                # Markdown 저장
                self.update_status("파일 저장 중...")
                self.log("💾 파일 저장 중...", 'INFO')
                md_path = self.md_gen.save(data, image_processor=self.image_processor)
                
                self.log(f"✅ 저장 완료: {md_path.name}", 'SUCCESS')
                
                # Drive 업로드
                if self.folder_id and self.uploader:
                    self.update_status("Google Drive 업로드 중...")
                    self.log("☁️ Google Drive 업로드 중...", 'INFO')
                    file_id = self.uploader.upload_file(str(md_path), self.folder_id)
                    self.log(f"✅ 업로드 완료! ID: {file_id}", 'SUCCESS')
            
            else:
                # 웹 페이지 처리
                # PDF 생성
                self.update_status("PDF 생성 중...")
                self.log("📄 PDF 생성 중...", 'INFO')
                html_content = data.get('html_content')
                pdf_path = self.pdf_gen.save(data, html_content, source_html_path=None)
                self.log(f"✅ PDF 저장 완료: {pdf_path.name}", 'SUCCESS')
                
                # 요약 생성
                if self.summarizer:
                    self.update_status("AI 요약 생성 중...")
                    self.log("🤖 AI 요약 생성 중...", 'INFO')
                    
                    from urllib.parse import urlparse
                    parsed_url = urlparse(data['url'])
                    clean_url = parsed_url._replace(query=None).geturl()
                    
                    metadata = {'Source Link': url}
                    summary = self.summarizer.summarize_text(
                        data['content'],
                        content_type='article',
                        metadata=metadata
                    )
                    
                    if summary:
                        summary_data = {
                            'title': f"{data['title']} - Summary",
                            'content': summary,
                            'url': data['url'],
                            'type': data['type']
                        }
                        summary_path = self.md_gen.save(summary_data, image_processor=None)
                        self.log(f"✅ 요약 저장 완료: {summary_path.name}", 'SUCCESS')
                
                # Drive 업로드
                if self.folder_id and self.uploader:
                    self.update_status("Google Drive 업로드 중...")
                    self.log("☁️ Google Drive 업로드 중...", 'INFO')
                    pdf_id = self.uploader.upload_file(str(pdf_path), self.folder_id)
                    if summary:
                        summary_id = self.uploader.upload_file(str(summary_path), self.folder_id)
                    self.log("✅ 업로드 완료!", 'SUCCESS')
            
            
            self.update_status("완료!")
            self.log("\n🎉 모든 작업이 완료되었습니다!", 'SUCCESS')
            
        except Exception as e:
            self.log(f"\n❌ 오류 발생: {str(e)}", 'ERROR')
            self.update_status("오류 발생")
            
        finally:
            # test_output 폴더 정리
            try:
                import shutil
                test_output = Path(__file__).parent / 'test_output'
                if test_output.exists():
                    shutil.rmtree(test_output)
                    self.log("🧹 test_output 폴더 정리 완료", 'INFO')
            except Exception as cleanup_error:
                self.log(f"⚠️ test_output 정리 실패: {cleanup_error}", 'WARNING')
            
            self.is_processing = False
            self.progress_bar.stop()
            self.start_button.config(state='normal')
            self.stop_button.config(state='disabled')

def main():
    root = tk.Tk()
    app = ClipperGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
