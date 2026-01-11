import os
import sys
from pathlib import Path
import logging
import re
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.utils import ImageProcessor, ConfigManager
from src.generators import HTMLGenerator, PDFGenerator, MarkdownGenerator
from src.clippers import WebClipper
from src.summarizer import GeminiSummarizer
from src.uploader import GDriveUploader

# Setup logging
logging.basicConfig(level=logging.INFO)
sys.stdout.reconfigure(encoding='utf-8')

def test_scraper():
    print("🚀 Starting Local Scraper Test...")
    
    # Load environment variables
    load_dotenv()
    
    # Test URL
    target_url_env = os.getenv("TARGET_URL")
    if target_url_env:
        url = target_url_env
        print(f"🔗 Using URL from Environment Variable: {url}")
    else:
        # Default Test URLs
        # url = "https://www.python.org/blogs/"
        # url = "https://blog.naver.com/tri99er/224140816612"
        # url = "https://blog.naver.com/tri99er/224140816612?test_param=123&utm_source=test"
        url = "https://blog.naver.com/tri99er/224140816612?test_param=123&utm_source=test"
        # url = "https://www.youtube.com/watch?v=gDdPs7oGRXU"
    
    print(f"Target URL: {url}")

    # Setup directories
    cwd = Path.cwd()
    test_dir = cwd / "test_output"
    test_dir.mkdir(exist_ok=True)
    assets_dir = test_dir / "assets"
    
    # Initialize Components
    image_processor = ImageProcessor(assets_dir)
    html_gen = HTMLGenerator(test_dir, assets_dir)
    pdf_gen = PDFGenerator(test_dir, assets_dir)
    md_gen = MarkdownGenerator(test_dir)
    
    # Initialize Step 2 Components (Summarizer & Uploader)
    gemini_key = os.getenv("GOOGLE_API_KEY")
    drive_token = os.getenv("GOOGLE_TOKEN_JSON")
    drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

    # Fallback to local files if env vars are missing
    if not drive_token:
        possible_tokens = ["credentials/token.json", "token.json"]
        for t in possible_tokens:
            if (cwd / t).exists():
                drive_token = str(cwd / t)
                print(f"ℹ️  Found token file at: {drive_token}")
                break

    summarizer = None
    uploader = None

    if gemini_key:
        print("✅ Gemini API Key found. Initializing Summarizer...")
        summarizer = GeminiSummarizer(gemini_key)
    else:
        print("⚠️  No Gemini API Key found (GOOGLE_API_KEY). Summarization will be skipped.")

    if drive_token:
        print("✅ Google Drive Token found. Initializing Uploader...")
        uploader = GDriveUploader(drive_token)
    else:
        print("⚠️  No Drive Token found (GOOGLE_TOKEN_JSON). Upload will be skipped.")

    
    # Select Clipper
    if 'youtube.com' in url or 'youtu.be' in url:
        from src.clippers import YouTubeClipper
        clipper = YouTubeClipper(image_processor, log_callback=print)
        is_youtube = True
    else:
        from src.clippers import WebClipper
        clipper = WebClipper(image_processor, html_gen)
        is_youtube = False
    
    try:
        # 1. Extract
        print("\n1️⃣  Extracting content...")
        data = clipper.extract_content(url)
        print(f"✅ Extracted Title: {data['title']}")
        print(f"✅ Content Length: {len(data['content'])} chars")
        
        saved_files = []

        if is_youtube:
            # YouTube: Summary + Transcript Merge
            
            # Generate Summary First if available
            if summarizer:
                print("\n2️⃣  Generating Summary (Gemini - YouTube Mode)...")
                # Prepare metadata for summarizer
                metadata = {}
                if is_youtube and 'upload_date' in data:
                    # yt-dlp upload_date is usually YYYYMMDD
                    ud = data['upload_date']
                    if len(ud) == 8:
                        formatted_date = f"{ud[:4]}-{ud[4:6]}-{ud[6:]}"
                        metadata['publish_date'] = formatted_date
                
                # YouTube URL 분석 모드 전달
                if data.get('use_gemini_url'):
                    metadata['use_gemini_url'] = True
                    metadata['youtube_url'] = data['url']
                
                summary = summarizer.summarize_text(data['content'], content_type='youtube', metadata=metadata)
                if summary:
                    # [구조 변경] 1. 요약 (Frontmatter 포함) -> 2. 대본 (이미지/헤더 제거)
                    
                    # 대본 섹션 구성 (헤더 제거, 구분선만 추가)
                    # "자막 부분만 유지" -> data['content']
                    transcript_section = f"\n\n---\n\n{data['content']}"
                    
                    # 전체 내용 병합 (요약본이 이미 Frontmatter와 제목을 포함하고 있음)
                    data['content'] = f"{summary}{transcript_section}"
                    print("✅ Summary merged into transcript.")
                else:
                    print("❌ Summary generation failed.")
            
            # Save Combined MD
            print("\n3️⃣  Saving Transcript (with Summary)...")
            
            # 파일명 생성: 날짜 제거 (YouTube만)
            # MarkdownGenerator.generate_filename은 내부적으로 utils.generate_filename을 호출하는데
            # 날짜를 강제로 넣으므로, 여기서 filename을 오버라이드할 방법이 필요함.
            # 하지만 MarkdownGenerator.save는 내부적으로 generate_filename을 호출.
            # 임시 해결책: data['title']에 날짜가 안 들어가도록 하고, generator 측면에서 날짜 prefix 로직을 우회하거나
            # Generator가 제공하는 유연성이 부족하면 직접 저장 로직을 구현해야 할 수도 있음.
            # 현재 utils.generate_filename이 날짜를 박아버림. -> [2026-01-11] ...
            
            # generators.py를 수정하지 않고 파일명을 제어하기 어려움.
            # save 메서드를 호출하되, 결과 파일명을 변경하는 방식 사용
            md_path = md_gen.save(data, image_processor=image_processor)
            
            # 파일명 변경 (날짜 제거)
            if md_path.exists():
                new_filename = f"{data['title']}.md".replace(':', '').replace('/', '_').replace('\\', '_') # Sanitize title roughly
                new_path = md_path.parent / new_filename
                
                # 기존 utils.sanitize_filename 로직과 불일치할 수 있으므로
                # 생성된 파일에서 날짜 부분만 제거하는 식으로 처리
                # 예: [2026-01-11] 제목.md -> 제목.md
                
                clean_name = re.sub(r'^\[\d{4}-\d{2}-\d{2}\]\s*', '', md_path.name)
                new_path = md_path.parent / clean_name
                
                # 이미 존재하면 덮어쓰거나 번호 붙이기 (여기선 덮어쓰기 or 패스)
                if new_path.exists():
                     new_path.unlink() # 오버라이드
                
                md_path.rename(new_path)
                md_path = new_path

            saved_files.append(md_path)
            print(f"✅ Transcript Saved: {md_path}")
            
        else:
            # Web: PDF + Optional Summary (Separate)
            
            # Generate PDF
            print("\n2️⃣  Generating PDF (with auto-cleanup)...")
            try:
                html_content = data.get('html_content')
                pdf_path = pdf_gen.save(data, html_content, source_html_path=None)
                
                # PDF 파일명 변경 (날짜 제거)
                if pdf_path and pdf_path.exists():
                    clean_pdf_name = re.sub(r'^\[\d{4}-\d{2}-\d{2}\]\s*', '', pdf_path.name)
                    new_pdf_path = pdf_path.parent / clean_pdf_name
                    
                    if new_pdf_path.exists():
                        new_pdf_path.unlink() # 오버라이드
                    
                    pdf_path.rename(new_pdf_path)
                    pdf_path = new_pdf_path
                    print(f"✅ PDF Renamed: {pdf_path}")
                
                saved_files.append(pdf_path)
                print(f"✅ PDF Saved: {pdf_path}")
            except Exception as e:
                print(f"❌ PDF Generation Failed: {e}")
                pdf_path = None # Ensure pdf_path is defined even if failure
            
            # Generate Summary (Separate File)
            if summarizer:
                print("\n3️⃣  Generating Summary (Gemini - Article Mode)...")
                if data.get('html_content'):
                    source_text = data['html_content']
                else:
                    source_text = data['content']
                
                # Prepare Metadata for Article
                
                # Clean URL (Remove Query Params)
                parsed_url = urlparse(data['url'])
                clean_url = parsed_url._replace(query=None).geturl()
                
                metadata = {
                    'created': data.get('publish_date') or datetime.now().strftime("%Y-%m-%d"),
                    'source': clean_url, 
                    # clean된 PDF 파일명 전달
                    'pdf_filename': pdf_path.name if 'pdf_path' in locals() and pdf_path else "Unknown.pdf"
                }

                summary = summarizer.summarize_text(source_text, content_type='article', metadata=metadata)
                
                if summary:
                    summary_data = data.copy()
                    summary_data['title'] = f"{data['title']} (Summary)"
                    summary_data['content'] = summary
                    summary_data['type'] = f"{data['type']} - Summary"
                    
                    summary_path = md_gen.save(summary_data, image_processor=None)
                    
                     # 파일명 변경 (날짜 제거) - Article Summary
                    if summary_path.exists():
                        clean_name = re.sub(r'^\[\d{4}-\d{2}-\d{2}\]\s*', '', summary_path.name)
                        new_path = summary_path.parent / clean_name
                        if new_path.exists():
                            new_path.unlink()
                        summary_path.rename(new_path)
                        summary_path = new_path

                    saved_files.append(summary_path)
                    print(f"✅ Summary Saved: {summary_path}")
                else:
                    print("❌ Summary generation returned empty result.")

        # 4. Upload (Step 2)
        if uploader and drive_folder_id:
            print("\n4️⃣  Uploading to Google Drive...")
            print(f"   Target Folder ID: {drive_folder_id}")
            
            uploaded_count = 0
            for file_path in saved_files:
                file_id = uploader.upload_file(str(file_path), drive_folder_id)
                if file_id:
                    print(f"✅ Uploaded {file_path.name} -> ID: {file_id}")
                    uploaded_count += 1
                else:
                    print(f"❌ Upload Failed: {file_path.name}")
            
            # File Cleanup (User Request)
            if uploaded_count > 0:
                print("\n🧹 Cleaning up test_output directory...")
                for file_path in saved_files:
                    try:
                        if file_path.exists():
                            file_path.unlink()
                            print(f"Deleted: {file_path.name}")
                    except Exception as e:
                        print(f"Failed to delete {file_path.name}: {e}")
                
        else:
            print("\n4️⃣  Skipping Upload (Missing Token or Folder ID)")

            
        print("\n🎉 Test Complete!")
        
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scraper()
