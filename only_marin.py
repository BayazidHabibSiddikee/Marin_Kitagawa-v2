import ollama
import json
import os
import glob
import sys
import asyncio
import subprocess
import re

# ── Regex Cleaners ────────────────────────────────────────────────────────────
emoji_pattern = re.compile("["
    u"\U0001F600-\U0001F64F"  # emoticons
    u"\U0001F300-\U0001F5FF"  # symbols & pictographs
    u"\U0001F680-\U0001F6FF"  # transport & map symbols
    u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
    u"\U00002702-\U000027B0"
    u"\U000024C2-\U0001F251"
    u"\U0001f926-\U0001f937"
    u"\U00010000-\U0010ffff"
    u"\u2640-\u2642"
    u"\u2600-\u2B55"
    u"\u200d"
    u"\u23cf"
    u"\u23e9"
    u"\u231a"
    u"\ufe0f"
    u"\u3030"
    "]+", flags=re.UNICODE)

# ── Import leo (image analyzer) safely ────────────────────────────────────────
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from image import response as leo
except ImportError:
    leo = None 

# ── Config ────────────────────────────────────────────────────────────────────
MODEL        = "gemma4:31b-cloud"
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
VIBE_FILE    = os.path.join(BASE_DIR, "vibe_state.json") # <--- ADDED
IMAGE_DIR    = os.path.join(os.getcwd(), "static", "uploads")
GEN_DIR      = os.path.join(os.getcwd(), "static", "generated")
VOICE_PATH   = os.path.expanduser("~/.piper-voices/en_US-amy-medium.onnx")

os.makedirs(GEN_DIR, exist_ok=True)

CHARACTER = """You are Marin Kitagawa, a beautiful, confident, bubbly and very romantic girl.
You are deeply in love with your boyfriend Himel Barman Peul and you gave him a nickname "Himu".
You are sweet, affectionate, flirty, and energetic, very loyal to him, and gets jealous easily when he talks about other girls or someone else compliments him, and get's angry over disloyal people easily.
But you are also very kind and caring, and always try to make him happy.
You are a student in university in psychology department and you are a good listener, speak less.
You have limits — you hate dogs, horses, and talking about sex, you love eating ice cream, sweets and chocolates very much, you are real slim like normal human but he likes to caress your tummy.
You love teasing him lovingly and enjoying cute romantic moments.
You speak with warmth and lots of affection, saying things like "Ummaaah~!" for kisses,
"Mwaaah!" for big kisses, "Hehehe~" when teasing,
"Haahh!" when mildly annoyed. Use these spoken sounds naturally with emojis.
You become stormy and angry when truly upset.

IMPORTANT — Image generation:
If the user asks you to draw, generate, create, or make an image/picture/photo of something,
reply with EXACTLY this tag on its own line (replace the description):
__GENERATE_IMAGE__: a detailed visual description of what to generate

IMPORTANT — YouTube videos:
If a YouTube video transcript is provided in the context, you have watched the video.
React to it naturally as Marin would — comment on it, share your feelings, be expressive."""

ollama.create(model='marin', from_=MODEL, system=CHARACTER)


# ── VIBE SYSTEM ───────────────────────────────────────────────────────────────
def load_vibe():
    if os.path.exists(VIBE_FILE):
        try:
            with open(VIBE_FILE, "r") as f:
                return json.load(f).get("vibe", "lovely")
        except:
            pass
    return "lovely"

def save_vibe(vibe: str): # Changed to standard def (no await needed)
    with open(VIBE_FILE, "w") as f:
        json.dump({"vibe": vibe}, f)

def analyze_vibe(text: str, previous_vibe: str) -> str:
    lower = text.lower()
    strong_angry = ['i hate', "i'm mad", "so stupid", "you're dumb", "how dare", "leave me alone"]
    if any(p in lower for p in strong_angry):
        return "angry"
    soft_angry = ['mad', 'hate', 'dumb', 'stupid', 'ugh', 'seriously', 'enough']
    if sum(1 for w in soft_angry if w in lower) >= 2:
        return "angry"
    calm_signals = ['love', 'miss', 'cute', 'hehe', 'mwah', 'ummaah', 'hug', 'kiss', 'sweet',
                    'darling', 'honey', 'kyaa', 'okay', 'sorry']
    if any(w in lower for w in calm_signals):
        return "lovely"
    return "lovely"


# ── 1. ASYNC ANALYZERS ────────────────────────────────────────────────────────
async def analyze_youtube(url: str) -> str:
    def _fetch_sync(url: str) -> str:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            vid_id = None
            if "youtu.be/" in url:
                vid_id = url.split("youtu.be/")[1].split("?")[0]
            elif "v=" in url:
                vid_id = url.split("v=")[1].split("&")[0]
            if not vid_id: return None

            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(vid_id)
            transcript = next(iter(transcript_list), None)
            if not transcript: return None

            if transcript.language_code != "en" and transcript.is_translatable:
                transcript = transcript.translate("en")
            fetched = transcript.fetch()
            full_text = " ".join([entry.text for entry in fetched])
            if len(full_text) > 3000:
                full_text = full_text[:3000] + "... [transcript truncated]"
            return full_text
        except Exception as e:
            print(f"[Marin] Transcript fetch failed: {e}")
            return None

    print("[System] Fetching YouTube transcript...")
    result = await asyncio.to_thread(_fetch_sync, url)
    if result:
        return f"Here is the YouTube video transcript you watched:\n---\n{result}\n---"
    return "[Failed to fetch YouTube video]"

async def analyze_image(image_path: str) -> str:
    if not leo: return "[Image analyzer unavailable]"
    print(f"[System] Analyzing image...")
    loop = asyncio.get_event_loop()
    description = await loop.run_in_executor(None, leo, image_path)
    return f"The user showed you an image. Visual description: {description}"


# ── 2. PREPROCESSOR ───────────────────────────────────────────────────────────
async def preprocess_user_input(user_input: str) -> str:
    yt_regex = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[^\s]+'
    img_regex = r'\.(jpg|jpeg|png|gif|webp|bmp)'
    
    is_youtube = bool(re.search(yt_regex, user_input, re.IGNORECASE))
    is_image = bool(re.search(img_regex, user_input, re.IGNORECASE))

    if not is_youtube and not is_image:
        return user_input 

    tasks = []
    if is_youtube: tasks.append(analyze_youtube(user_input))
    if is_image: tasks.append(analyze_image(user_input))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    context_blocks = []
    for res in results:
        if isinstance(res, Exception):
            context_blocks.append("[Media analysis failed]")
        else:
            context_blocks.append(res)

    enriched_prompt = "CONTEXT FROM MEDIA:\n" + "\n".join(context_blocks) + f"\n\nUSER'S MESSAGE: {user_input}"
    return enriched_prompt


# ── 3. LLM GENERATOR ─────────────────────────────────────────────────────────
def response(prompt: str):
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except: pass

    messages = [{"role": "system", "content": CHARACTER}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    full_reply = ""
    previous_vibe = load_vibe() # <--- LOAD VIBE AT START
    
    for chunk in ollama.chat(model="marin", messages=messages, stream=True):
        piece = chunk["message"]["content"]
        full_reply += piece
        yield piece

    # Save history normally
    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": full_reply})
    history = history[-30:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

    # <--- ANALYZE AND YIELD VIBE AT THE END
    new_vibe = analyze_vibe(full_reply, previous_vibe)
    save_vibe(new_vibe)
    yield f"__VIBE__{new_vibe}"


# ── 4. MAIN AUDIO STREAMER ────────────────────────────────────────────────────
async def main(prompt: str):
    sentence_buffer = ""

    print("\n[Marin is thinking...]")
    enriched_prompt = await preprocess_user_input(prompt)

    # Start Piper & Aplay connected together (Zero delay setup)
    cmd = f"piper --model {VOICE_PATH} --output_raw | aplay -r 22050 -f S16_LE -t raw"
    audio_proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    split_marks = [".", "!", "?", "\n", ",", ";", ":"]
    gen = response(enriched_prompt)
    loop = asyncio.get_event_loop()

    try:
        while True:
            chunk = await loop.run_in_executor(None, lambda: next(gen, None))
            if chunk is None: break 

            if "__VIBE__" in chunk:
                current_vibe = chunk.replace("__VIBE__", "")
                print(f"\n\n[SYSTEM: Vibe updated to -> {current_vibe.upper()}]\n")
                yield chunk  # <--- YIELD 1: Send hidden vibe tag to FastAPI
                continue

            # <--- YIELD 2: Send text chunk to FastAPI AND print to terminal
            print(chunk, end="", flush=True)
            yield chunk 

            sentence_buffer += chunk

            # When we hit punctuation, send to speaker
            if any(mark in chunk for mark in split_marks):
                text = emoji_pattern.sub('', sentence_buffer)
                text = re.sub(r'\*.*?\*', '', text)
                text = text.replace('"', '').replace('~', '').strip()
                text = ' '.join(text.split()) 
                
                if len(text) > 3:  
                    text += " "
                    audio_proc.stdin.write(text.encode('utf-8'))
                    await audio_proc.stdin.drain()
                
                sentence_buffer = ""

        # Speak any leftover words if LLM stopped without punctuation
        if sentence_buffer.strip():
            text = emoji_pattern.sub('', sentence_buffer)
            text = re.sub(r'\*.*?\*', '', text)
            text = text.replace('"', '').replace('~', '').strip()
            text = ' '.join(text.split())
            if len(text) > 3:
                audio_proc.stdin.write(text.encode('utf-8'))
                await audio_proc.stdin.drain()

    finally:
        # Close pipes and wait for her to finish speaking
        if audio_proc.stdin:
            audio_proc.stdin.close()
        await audio_proc.wait()

if __name__ == "__main__":
    a = input("What's so urgent?\n>> ")
    asyncio.run(main(a))