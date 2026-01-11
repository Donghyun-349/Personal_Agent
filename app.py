# -*- coding: utf-8 -*-
import streamlit as st
import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from clippers import YouTubeClipper, WebClipper
from generators import MarkdownGenerator, PDFGenerator
from utils import ImageProcessor
from summarizer import GeminiSummarizer
from uploader import GDriveUploader

# Load environment variables
load_dotenv()

st.set_page_config(
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
                uploader = GDriveUploader()
                
                if token_json:
                    uploader.authenticate(token_json)
                else:
                    st.warning("Google Drive 인증 정보가 없습니다. 업로드를 건너뜁니다.")
                
                image_processor = ImageProcessor()
                md_gen = MarkdownGenerator()
                pdf_gen = PDFGenerator()
            
            # Determine content type
            is_youtube = 'youtube.com' in url or 'youtu.be' in url
            
            # Extract content
            with st.spinner("콘텐츠 추출 중..."):
                if is_youtube:
                    clipper = YouTubeClipper()
                    st.info("🎥 YouTube 영상 처리 중...")
                else:
                    clipper = WebClipper()
                    st.info("🌐 웹 페이지 처리 중...")
                
                data = clipper.extract_content(url)
                st.success(f"✅ 추출 완료: {data['title']}")
            
            # Generate summary
            if is_youtube:
                with st.spinner("AI 요약 생성 중..."):
                    metadata = {}
                    if data.get('use_gemini_url'):
                        metadata['use_gemini_url'] = True
                        metadata['youtube_url'] = data['url']
                        metadata['video_title'] = data.get('title', '제목 없음')
                    
                    summary = summarizer.summarize_text(
                        data['content'],
                        content_type='youtube',
                        metadata=metadata
                    )
                    
                    if summary:
                        # Extract title from Gemini summary if using URL mode
                        if data.get('use_gemini_url'):
                            title_match = re.search(r'^#\s+(.+)$', summary, re.MULTILINE)
                            if title_match:
                                data['title'] = title_match.group(1).strip()
                        
                        data['content'] = f"{summary}\n\n---\n\n{data['content']}"
                        st.success("✅ 요약 완료")
                
                # Save markdown
                with st.spinner("파일 저장 중..."):
                    md_path = md_gen.save(data, image_processor=image_processor)
                    
                    # Remove date prefix from filename
                    clean_name = re.sub(r'^\[\d{4}-\d{2}-\d{2}\]\s*', '', md_path.name)
                    new_path = md_path.parent / clean_name
                    if new_path.exists():
                        new_path.unlink()
                    md_path.rename(new_path)
                    md_path = new_path
                    
                    st.success(f"✅ 저장 완료: {md_path.name}")
                
                # Upload to Drive
                if folder_id and uploader:
                    with st.spinner("Google Drive 업로드 중..."):
                        file_id = uploader.upload_file(str(md_path), folder_id)
                        st.success(f"✅ Google Drive 업로드 완료!")
                        st.markdown(f"[Google Drive에서 보기](https://drive.google.com/file/d/{file_id}/view)")
            
            else:
                # Web/Blog processing
                with st.spinner("PDF 생성 중..."):
                    html_content = data.get('html_content')
                    pdf_path = pdf_gen.save(data, html_content, source_html_path=None)
                    st.success(f"✅ PDF 저장 완료: {pdf_path.name}")
                
                # Generate summary
                with st.spinner("AI 요약 생성 중..."):
                    metadata = {'Source Link': url}
                    summary = summarizer.summarize_text(
                        data['content'],
                        content_type='article',
                        metadata=metadata
                    )
                    
                    if summary:
                        summary_data = {
                            'title': f"{data['title']} - Summary",
                            'content': summary
                        }
                        summary_path = md_gen.save(summary_data, image_processor=None)
                        st.success(f"✅ 요약 저장 완료: {summary_path.name}")
                
                # Upload to Drive
                if folder_id and uploader:
                    with st.spinner("Google Drive 업로드 중..."):
                        pdf_id = uploader.upload_file(str(pdf_path), folder_id)
                        if summary:
                            summary_id = uploader.upload_file(str(summary_path), folder_id)
                        st.success("✅ Google Drive 업로드 완료!")
            
            st.balloons()
            st.success("🎉 모든 작업이 완료되었습니다!")
            
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
            st.exception(e)

# Footer
st.markdown("---")
st.markdown("💡 **Tip**: `.env` 파일에 `GOOGLE_API_KEY`, `GOOGLE_TOKEN_JSON`, `GOOGLE_DRIVE_FOLDER_ID`를 설정하세요.")
