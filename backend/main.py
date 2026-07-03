import os
import re
import shutil
import tempfile
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import yt_dlp

YOUTUBE_URL_RE = re.compile(
    r"^https?://(www\.)?(youtube\.com/watch\?v=|youtube\.com/shorts/|youtu\.be/)[\w\-]+"
)

QUALITY_FORMATS = {
    "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "720": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
    "480": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]",
}

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

ALLOWED_ORIGINS = [
    "https://ytconverter-paolo98.web.app",
    "https://ytconverter-paolo98.firebaseapp.com",
    "http://localhost:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def validate_url(url: str) -> None:
    if not url or not YOUTUBE_URL_RE.match(url):
        raise HTTPException(status_code=400, detail="URL YouTube non valido")


COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE", "/etc/secrets/cookies.txt")


def base_ydl_opts() -> dict:
    opts = {
        "quiet": True,
        "noplaylist": True,
        # L'IP dei provider cloud viene spesso classificato come "bot" da YouTube;
        # spoofare il client Android riduce la frequenza del blocco "Sign in to confirm".
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    return opts


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/info")
@limiter.limit("30/hour")
def info(request: Request, url: str):
    validate_url(url)
    ydl_opts = {**base_ydl_opts(), "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(url, download=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Impossibile leggere il video: {e}")

    return {
        "title": data.get("title"),
        "thumbnail": data.get("thumbnail"),
        "duration": data.get("duration"),
        "uploader": data.get("uploader"),
    }


@app.get("/api/download")
@limiter.limit("15/hour")
def download(request: Request, url: str, quality: str = "720"):
    validate_url(url)
    if quality != "audio" and quality not in QUALITY_FORMATS:
        raise HTTPException(status_code=400, detail="Qualità non valida")

    job_id = uuid.uuid4().hex
    tmp_dir = tempfile.mkdtemp(prefix=f"ytdl_{job_id}_")
    outtmpl = os.path.join(tmp_dir, "%(title).100s.%(ext)s")

    if quality == "audio":
        ydl_opts = {
            **base_ydl_opts(),
            "outtmpl": outtmpl,
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ],
        }
        media_type = "audio/mpeg"
    else:
        ydl_opts = {
            **base_ydl_opts(),
            "outtmpl": outtmpl,
            "format": QUALITY_FORMATS[quality],
            "merge_output_format": "mp4",
        }
        media_type = "video/mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Download fallito: {e}")

    files = [f for f in os.listdir(tmp_dir) if not f.endswith(".part")]
    if not files:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="File non generato")

    file_path = os.path.join(tmp_dir, files[0])
    filename = files[0]

    def iterfile():
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iterfile(), media_type=media_type, headers=headers)
