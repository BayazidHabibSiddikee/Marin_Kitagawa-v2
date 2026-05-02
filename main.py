import os
import re
import subprocess
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# marin.main() is the single source of truth:
#   ✓ preprocesses YouTube / image links
#   ✓ streams text chunks + __VIBE__ tag to FastAPI
#   ✓ pipes cleaned speech sentences to Piper → aplay in real-time
from marin import main as marin_main

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/generated', exist_ok=True)

VOICE_PATH = os.path.expanduser("~/.piper-voices/en_US-amy-medium.onnx")

# ── Intro TTS (Piper) ─────────────────────────────────────────────────────────
def play_intro():
    """Speak intro.txt through Piper when the chat page loads."""
    try:
        if os.path.exists("intro.txt"):
            cmd = (
                f"piper --model {VOICE_PATH} --output_raw < intro.txt"
                f" | aplay -r 22050 -f S16_LE -t raw"
            )
            subprocess.Popen(cmd, shell=True)
    except Exception as e:
        print(f"[Intro TTS] Failed: {e}")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def get_chat(request: Request):
    play_intro()
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/upload")
async def upload_image(image: UploadFile = File(...)):
    if not image.filename:
        return {"error": "No filename"}, 400

    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', image.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    with open(filepath, "wb") as buf:
        buf.write(await image.read())
    return {"ok": True, "path": f"/{filepath}"}

@app.post("/message")
async def handle_message(message: str = Form(...), image: UploadFile = File(None)):
    image_path = None
    
    if image and image.filename:
        filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', image.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(image_path, "wb") as buf:
            buf.write(await image.read())
            
        # Create an absolute path before passing to Marin (Cloud models need this)
        image_path = os.path.abspath(image_path)

    # FIX 5: Actually pass the image_path to marin_main!
    return StreamingResponse(marin_main(message, image_path=image_path), media_type="text/plain")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5069)