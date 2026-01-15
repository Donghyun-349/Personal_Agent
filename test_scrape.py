# -*- coding: utf-8 -*-
"""
Quick test script for PDF scraping (without summarization)
Tests: Content extraction + Image download + PDF generation
"""
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from clippers import WebClipper
from generators import PDFGenerator
from utils import ImageProcessor

def test_scrape():
    print("🧪 Quick Scrape Test (No Summarization)")
    print("=" * 60)
    
    # Test URL - 사용자가 원하는 URL로 변경 가능
    url = "https://blog.naver.com/tri99er/224140816612"
    print(f"📌 Target URL: {url}\n")
    
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
    clipper = WebClipper(image_processor)
    print("✅ Components ready\n")
    
    try:
        # Extract content
        print("📥 Extracting content...")
        data = clipper.extract_content(url)
        print(f"✅ Title: {data['title']}")
        print(f"✅ Content length: {len(data['content'])} chars\n")
        
        # Generate PDF
        print("📄 Generating PDF...")
        html_content = data.get('html_content')
        pdf_path = pdf_gen.save(data, html_content, source_html_path=None)
        
        print(f"\n{'='*60}")
        print(f"✅ SUCCESS!")
        print(f"📄 PDF saved: {pdf_path.name}")
        print(f"📂 Location: {pdf_path.parent}")
        print(f"📊 File size: {pdf_path.stat().st_size / 1024:.1f} KB")
        print(f"{'='*60}")
        
        # Check images
        img_dir = test_output / "img"
        if img_dir.exists():
            images = list(img_dir.glob("*"))
            print(f"\n🖼️  Downloaded {len(images)} images:")
            for img in images[:5]:  # Show first 5
                print(f"   - {img.name} ({img.stat().st_size / 1024:.1f} KB)")
            if len(images) > 5:
                print(f"   ... and {len(images) - 5} more")
        
        print(f"\n💡 Open the PDF to verify image quality!")
        print(f"   Expected: Images should be up to 2400px (2x larger than before)")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scrape()
