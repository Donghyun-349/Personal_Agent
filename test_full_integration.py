# -*- coding: utf-8 -*-
"""
전체 기능 통합 테스트 (스크랩 + 요약 + Google Drive 업로드)
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

from clippers import WebClipper
from generators import PDFGenerator, MarkdownGenerator
from utils import ImageProcessor
from summarizer import GeminiSummarizer
from uploader import GDriveUploader

def full_test():
    print("=" * 60)
    print("🧪 전체 기능 통합 테스트")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Test URL
    url = "https://blog.naver.com/tri99er/224140816612"
    print(f"\n📌 Target URL: {url}\n")
    
    # Setup directories
    base_dir = Path(__file__).parent
    test_output = base_dir / "test_output"
    test_output.mkdir(exist_ok=True)
    
    assets_dir = test_output / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    print(f"📁 Output Directory: {test_output}\n")
    
    # Initialize components
    print("⚙️  Initializing components...")
    image_processor = ImageProcessor(assets_dir)
    pdf_gen = PDFGenerator(test_output, assets_dir)
    md_gen = MarkdownGenerator(test_output)
    clipper = WebClipper(image_processor)
    
    # Initialize Gemini & Drive
    api_key = os.getenv('GOOGLE_API_KEY')
    token_json = os.getenv('GOOGLE_TOKEN_JSON')
    folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    
    summarizer = GeminiSummarizer(api_key) if api_key else None
    uploader = None
    
    if token_json:
        uploader = GDriveUploader()
        uploader.authenticate(token_json)
    
    print("✅ Components ready\n")
    
    try:
        # 1. Extract content
        print("1️⃣ 📥 Extracting content...")
        data = clipper.extract_content(url)
        print(f"   ✅ Title: {data['title']}")
        print(f"   ✅ Content length: {len(data['content'])} chars\n")
        
        # 2. Generate PDF
        print("2️⃣ 📄 Generating PDF...")
        html_content = data.get('html_content')
        pdf_path = pdf_gen.save(data, html_content, source_html_path=None)
        print(f"   ✅ PDF saved: {pdf_path.name}")
        print(f"   ✅ File size: {pdf_path.stat().st_size / 1024:.1f} KB\n")
        
        # 3. Generate Summary (if available)
        summary_path = None
        if summarizer:
            print("3️⃣ 🤖 Generating AI Summary...")
            from urllib.parse import urlparse
            parsed_url = urlparse(data['url'])
            clean_url = parsed_url._replace(query=None).geturl()
            
            metadata = {'Source Link': url}
            summary = summarizer.summarize_text(
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
                summary_path = md_gen.save(summary_data, image_processor=None)
                print(f"   ✅ Summary saved: {summary_path.name}\n")
        else:
            print("3️⃣ ⚠️  Gemini API Key not found, skipping summary\n")
        
        # 4. Upload to Google Drive
        if folder_id and uploader and uploader.service:
            print("4️⃣ ☁️  Uploading to Google Drive...")
            print(f"   Target Folder: {folder_id}")
            
            # Upload PDF
            pdf_id = uploader.upload_file(str(pdf_path), folder_id)
            if pdf_id:
                print(f"   ✅ PDF uploaded! ID: {pdf_id}")
                print(f"      https://drive.google.com/file/d/{pdf_id}/view")
            
            # Upload Summary
            if summary_path:
                summary_id = uploader.upload_file(str(summary_path), folder_id)
                if summary_id:
                    print(f"   ✅ Summary uploaded! ID: {summary_id}")
                    print(f"      https://drive.google.com/file/d/{summary_id}/view")
            
            print()
        else:
            print("4️⃣ ⚠️  Google Drive not configured, skipping upload\n")
        
        # Summary
        print("=" * 60)
        print("🎉 테스트 완료!")
        print("=" * 60)
        print(f"\n✅ PDF 생성: {pdf_path.name}")
        if summary_path:
            print(f"✅ 요약 생성: {summary_path.name}")
        if folder_id and uploader and uploader.service:
            print(f"✅ Google Drive 업로드: 성공")
        print()
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    full_test()
