
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")

try:
    import youtube_transcript_api
    print(f"\n[youtube_transcript_api]")
    print(f"File: {youtube_transcript_api.__file__}")
    print(f"Dir: {dir(youtube_transcript_api)}")
    
    if hasattr(youtube_transcript_api, '__version__'):
        print(f"Version: {youtube_transcript_api.__version__}")
    else:
        # Try finding version via pkg_resources
        try:
            from importlib.metadata import version
            print(f"Version (metadata): {version('youtube-transcript-api')}")
        except:
            print("Version: Unknown")
            
    print(f"\n[YouTubeTranscriptApi Class]")
    YTApi = youtube_transcript_api.YouTubeTranscriptApi
    print(f"Dir: {dir(YTApi)}")
    print(f"Type: {type(YTApi)}")
    
except ImportError as e:
    print(f"Error importing youtube_transcript_api: {e}")

try:
    import yt_dlp
    print(f"\n[yt-dlp]")
    print(f"File: {yt_dlp.__file__}")
    from importlib.metadata import version
    print(f"Version: {version('yt-dlp')}")
except Exception as e:
    print(f"Error checking yt-dlp: {e}")
