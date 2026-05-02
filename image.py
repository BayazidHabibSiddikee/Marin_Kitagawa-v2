import ollama
import os
import json
import glob
import subprocess
import asyncio
import time

# ── Config ─────────────────────────────────────────────────────────────────────
MODEL          = "moondream" #"gemini-3-flash-preview:cloud"#"moondream"
CHARACTER_NAME = "leo"
CHARACTER      = """You are Leonardo Da Vinci — the Renaissance genius.
You see hidden geometry, divine proportion, and deeper meaning in everything.
Speak dramatically, find patterns and beauty. Be poetic but brief."""

# history lives RIGHT NEXT TO this file
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "leo_history.json")  # separate from other histories


def setup_model():
    """Only create the model once — skip if it already exists."""
    try:
        # FIX: ollama.list() returns objects, not dicts
        existing = [m.model for m in ollama.list().models]
        if f"{CHARACTER_NAME}:latest" not in existing:
            print(f"[Leo] First time setup — creating model...")
            ollama.create(model=CHARACTER_NAME, from_=MODEL, system=CHARACTER)
        else:
            print(f"[Leo] Model ready.")
    except Exception as e:
        print(f"[Leo] Setup warning: {e} — trying anyway")
        ollama.create(model=CHARACTER_NAME, from_=MODEL, system=CHARACTER)


def response(prompt: str, image_path=None):
    setup_model()
    # ... [history loading stays the same] ...
    # ── Load history ──────────────────────────────────────────────────────────
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            history = []

    messages = [{"role": "system", "content": CHARACTER}]
    for msg in history:
        messages.append(msg)

    # ── Build user message ────────────────────────────────────────────────────
    user_message = {"role": "user", "content": prompt}
    #user_message = {"role": "user", "content": prompt}

    if image_path and os.path.exists(image_path):
        # FIX 1: Force absolute path for Cloud Models
        user_message["images"] = [os.path.abspath(image_path)]   
        print(f"[Leo] Analyzing: {os.path.basename(image_path)}")
    else:
        if image_path:
            print(f"[Leo] Image not found at: {image_path}")
        else:
            print(f"[Leo] No image provided — text only")

    messages.append(user_message)

    # ── Stream reply ──────────────────────────────────────────────────────────
    reply = ""
    print("\n[Leo] Contemplating...\n")
    try:
        for chunk in ollama.chat(model=CHARACTER_NAME, messages=messages, stream=True):
            piece  = chunk['message']['content']
            reply += piece
            yield piece
    except Exception as e:
        print(f"\n[Leo] Error: {e}")
        yield f"[Error: {e}]"
        return

    # ── Save history ──────────────────────────────────────────────────────────
    history.append({"role": "user",      "content": prompt})
    history.append({"role": "assistant", "content": reply})

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-20:], f, ensure_ascii=False, indent=4)



# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    subprocess.Popen(["ollama", "serve"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    import time; time.sleep(1)

    # FIX 2: Look in the static/uploads folder, not the root folder!
    search_dir = os.path.join(BASE_DIR, "static", "uploads")
    os.makedirs(search_dir, exist_ok=True)
    
    image_files = (glob.glob(os.path.join(search_dir, "*.jpg"))  +
                   glob.glob(os.path.join(search_dir, "*.jpeg")) +
                   glob.glob(os.path.join(search_dir, "*.png"))  +
                   glob.glob(os.path.join(search_dir, "*.webp")) +
                   glob.glob(os.path.join(search_dir, "*.ico")))

    if not image_files:
        print(f"[Leo] No image found in {search_dir} — put an image there.")
        exit(1)

    latest_image = max(image_files, key=os.path.getctime)
    print(f"[Leo] Found image: {latest_image}")

    prompt = "This is a safe general image. Describe only what you literally see. Be brief."
    for piece in response(prompt, image_path=latest_image):
        print(piece, end="", flush=True)
    print("\n")