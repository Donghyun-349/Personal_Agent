import streamlit as st
import os
import sys
import shutil
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.utils import ImageProcessor
from src.generators import HTMLGenerator, PDFGenerator, MarkdownGenerator
from src.clippers import WebClipper, YouTubeClipper
from src.summarizer import GeminiSummarizer
from src.uploader import GDriveUploader

# --- Page Config ---
st.set_page_config(
    page_title="AI Content Analyst",
    page_icon="🧠",
    layout="wide"
)

# --- Session State Init ---
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'logs' not in st.session_state:
    page_title="Web Clipper & Summarizer",
    page_icon="📋",
    layout="centered"
)

st.title("📋 Web Clipper & Summarizer")
st.markdown("YouTube 영상 또는 웹 페이지를 요약하고 Google Drive에 저장합니다.")

# URL Input
url = st.text_input(
    "🔗 URL을 입력하세요",
    placeholder="https://www.youtube.com/watch?v=... 또는 https://blog.naver.com/...",
    help="YouTube 영상 또는 네이버 블로그, 웹 페이지 URL을 입력하세요"
)

# Process button
if st.button("🚀 시작", type="primary", use_container_width=True):
    if not url:
        st.error("URL을 입력해주세요!")
    else:
        try:
            # Initialize components
            with st.spinner("초기화 중..."):
                api_key = os.getenv('GOOGLE_API_KEY')
                token_json = os.getenv('GOOGLE_TOKEN_JSON')
                folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
                
                if not api_key:
                    st.error("GOOGLE_API_KEY가 설정되지 않았습니다!")
                    st.stop()
                
                summarizer = GeminiSummarizer(api_key)
                    if not drive_token:
                         possible_tokens = ["credentials/token.json", "token.json"]
                         for t in possible_tokens:
                             if (cwd / t).exists():
                                 drive_token = str(cwd / t)
                                 break
                    # Check Streamlit Secrets fallback
                    if not drive_token and "GOOGLE_TOKEN_JSON" in st.secrets:
                         drive_token_content = st.secrets["GOOGLE_TOKEN_JSON"]
                         # Write to temporary file because GDriveUploader expects a path usually, 
                         # BUT checked db_adapter logic - GDriveUploader might expect file path.
                         # Let's assume standard file path for now.
                         # If deploying to cloud, might need to write secret to file.
                         pass 
                         
                    if drive_token:
                        uploader = GDriveUploader(drive_token)
                        log("✅ Google Drive Uploader Initialized")
                    else:
                        log("⚠️ Drive Token Not Found. Upload skipped.")

                # 2. Extract
                is_youtube = 'youtube.com' in url or 'youtu.be' in url
                
                if is_youtube:
                    log("🎥 Detected YouTube URL")
                    clipper = YouTubeClipper(image_processor, log_callback=log)
                else:
                    log("📰 Detected Web Article")
                    clipper = WebClipper(image_processor, html_gen)

                data = clipper.extract_content(url)
                log(f"✅ Extracted: {data['title']}")

                saved_files = []
                final_summary = ""
                
                # 3. Process & Summarize
                if is_youtube:
                    # YouTube Flow
                    metadata = {}
                    if 'upload_date' in data and len(data['upload_date']) == 8:
                        ud = data['upload_date']
                        metadata['publish_date'] = f"{ud[:4]}-{ud[4:6]}-{ud[6:]}"
                    
                    log("🤖 Summarizing (YouTube)...")
                    summary = summarizer.summarize_text(data['content'], content_type='youtube', metadata=metadata)
                    
                    if summary:
                        final_summary = summary
                        transcript_section = f"\n\n---\n\n{data['content']}"
                        data['content'] = f"{summary}{transcript_section}"
                        
                        # Save Transcript MD
                        md_path = md_gen.save(data, image_processor=image_processor)
                        
                        # Renaming Logic (Remove Date Prefix)
                        if md_path.exists():
                            clean_name = re.sub(r'^\[\d{4}-\d{2}-\d{2}\]\s*', '', md_path.name)
                            new_path = md_path.parent / clean_name
                            if new_path.exists(): new_path.unlink()
                            md_path.rename(new_path)
                            md_path = new_path
                            
                        saved_files.append(md_path)
                        log(f"✅ Saved MD: {md_path.name}")
                    else:
                        log("❌ Summary Failed")

                else:
                    # Article Flow
                    # Generate PDF First
                    log("📄 Generating PDF...")
                    pdf_path = pdf_gen.save(data, data.get('html_content'), source_html_path=None)
                    
                    # Renaming Logic (PDF)
                    if pdf_path and pdf_path.exists():
                        clean_pdf_name = re.sub(r'^\[\d{4}-\d{2}-\d{2}\]\s*', '', pdf_path.name)
                        new_pdf_path = pdf_path.parent / clean_pdf_name
                        if new_pdf_path.exists(): new_pdf_path.unlink()
                        pdf_path.rename(new_pdf_path)
                        pdf_path = new_pdf_path
                        log(f"✅ PDF Renamed: {pdf_path.name}")
                    
                    saved_files.append(pdf_path)

                    # Summarize
                    log("🤖 Summarizing (Article)...")
                    
                    # Clean URL (Remove Query Params)
                    parsed_url = urlparse(data['url'])
                    clean_url = parsed_url._replace(query=None).geturl()
                    
                    metadata = {
                        'created': data.get('publish_date') or datetime.now().strftime("%Y-%m-%d"),
                        'source': clean_url,
                        'pdf_filename': pdf_path.name if pdf_path else "Unknown.pdf"
                    }
                    
                    source_text = data.get('html_content') or data['content']
                    summary = summarizer.summarize_text(source_text, content_type='article', metadata=metadata)
                    
                    if summary:
                        final_summary = summary
                        summary_data = data.copy()
                        summary_data['title'] = f"{data['title']} (Summary)"
                        summary_data['content'] = summary
                        summary_data['type'] = f"{data['type']} - Summary"
                        
                        summary_path = md_gen.save(summary_data, image_processor=None)
                        
                        # Renaming Logic (Summary MD)
                        if summary_path.exists():
                            clean_name = re.sub(r'^\[\d{4}-\d{2}-\d{2}\]\s*', '', summary_path.name)
                            new_path = summary_path.parent / clean_name
                            if new_path.exists(): new_path.unlink()
                            summary_path.rename(new_path)
                            summary_path = new_path
                        
                        saved_files.append(summary_path)
                        log(f"✅ Saved Summary MD: {summary_path.name}")

                # 4. Upload
                if uploader and upload_to_drive and folder_id:
                    log("☁️ Uploading to Drive...")
                    for f in saved_files:
                        if f and f.exists():
                            fid = uploader.upload_file(str(f), folder_id)
                            if fid: log(f"✅ Uploaded {f.name}")
                            else: log(f"❌ Upload Failed {f.name}")
                
                # 5. Store Result in Session for Display
                # Read file contents for download options
                downloads = []
                for f in saved_files:
                    if f and f.exists():
                        with open(f, "rb") as file:
                            downloads.append({
                                "name": f.name,
                                "data": file.read(),
                                "mime": "application/pdf" if f.suffix == '.pdf' else "text/markdown"
                            })
                
                st.session_state.processed_data = {
                    "summary": final_summary,
                    "downloads": downloads
                }
                
                # Cleanup Output Folder (Optional - Streamlit runs locally so maybe keep? 
                # User asked for cleanup in 'test_local'. In Web App, we handle bytes.
                # Let's clean up to avoid disk usage bloat.)
                log("🧹 Cleaning up local files...")
                for f in saved_files:
                     if f and f.exists(): f.unlink()
                # shutil.rmtree(assets_dir) # Maybe too aggressive if concurrent?
                
                log("🎉 Analysis Complete!")
                
            except Exception as e:
                st.error(f"오류 발생: {str(e)}")
                log(f"ERROR: {str(e)}")

# --- Display Results ---
if st.session_state.processed_data:
    st.divider()
    st.subheader("📝 Analysis Result")
    
    data = st.session_state.processed_data
    
    # Show Summary
    with st.expander("📄 요약 내용 보기 (Preview)", expanded=True):
        st.markdown(data["summary"])
        
    # Download Buttons
    st.subheader("💾 Downloads")
    cols = st.columns(len(data["downloads"]))
    for idx, d in enumerate(data["downloads"]):
        with cols[idx]:
            st.download_button(
                label=f"Download {d['name']}",
                data=d['data'],
                file_name=d['name'],
                mime=d['mime']
            )
