import os
import re
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Import the main async generator from marin
from marin import main as marin_main

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/generated', exist_ok=True)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def get_chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/upload")
async def upload_image(image: UploadFile = File(...)):
    if not image.filename:
        return "No filename", 400
    
    # Secure filename without Flask dependencies
    filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', image.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    with open(filepath, "wb") as buf:
        buf.write(await image.read())
    return "OK", 200

@app.post("/message")
async def handle_message(message: str = ...):
    """
    marin_main(message) is an async generator.
    It does 3 things at once:
    1. Analyzes YouTube/Images
    2. Streams text to the browser (via yield)
    3. Streams audio to Piper (via stdin pipe)
    """
    return StreamingResponse(marin_main(message), media_type="text/plain")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5069)