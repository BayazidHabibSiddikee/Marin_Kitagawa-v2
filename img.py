import asyncio
from image import response as leo

async def analyze_image(image_path: str) -> str:
    if not leo: return "[Image analyzer unavailable]"
    print(f"[System] Analyzing image...")
    loop = asyncio.get_event_loop()
    description = await loop.run_in_executor(None, leo, image_path)
    return f"The user showed you an image. Visual description: {description}"

async def main():
    print(await analyze_image("/home/bayazid/Documents/fastapi/static/uploads/icon.ico"))

if __name__ == "__main__":
    asyncio.run(main())