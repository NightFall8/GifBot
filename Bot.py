import discord
from discord.ext import commands
import requests
import random
import io
import numpy as np
from PIL import Image, ImageSequence
import imageio.v2 as imageio

# ================= CONFIG =================
TOKEN = "YOUR_DISCORD_BOT_TOKEN"
GIPHY_API_KEY = "YOUR_GIPHY_KEY"

CANVAS_SIZE = (500, 500)
MAX_GIFS = 4
MAX_FRAMES = 40
FRAME_DURATION = 0.06

HEADERS = {"User-Agent": "Mozilla/5.0"}

MIN_WIDTH = 80
MIN_HEIGHT = 80
MAX_FETCH_TRIES = 10

# ==========================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# -------- GIPHY SEARCH --------
def search_gifs(query, limit=30):
    url = "https://api.giphy.com/v1/gifs/search"
    params = {
        "api_key": GIPHY_API_KEY,
        "q": query,
        "limit": limit,
        "rating": "pg-13"
    }

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = r.json().get("data", [])
    except:
        return []

    urls = []
    for gif in data:
        title = gif.get("title", "").lower()
        if "benjammin" in title:
            continue

        urls.append(gif["images"]["original"]["url"])

    return list(set(urls))


# -------- DOWNLOAD + VALIDATE --------
def load_gif(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        img = Image.open(io.BytesIO(r.content))
    except:
        return None

    frames = []
    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert("RGBA"))

    if not frames:
        return None

    # filter tiny gifs
    if frames[0].width < MIN_WIDTH or frames[0].height < MIN_HEIGHT:
        return None

    return frames[:MAX_FRAMES]


# -------- PICK WORKING GIF --------
def get_valid_gif(urls):
    for _ in range(MAX_FETCH_TRIES):
        url = random.choice(urls)
        frames = load_gif(url)
        if frames:
            return frames

    return None


# -------- RANDOM BACKGROUND --------
def get_random_background():
    urls = search_gifs("landscape background sky", 25)

    for _ in range(MAX_FETCH_TRIES):
        if not urls:
            break

        frames = get_valid_gif(urls)
        if frames:
            return frames

    # fallback gradient (only if everything fails)
    w, h = CANVAS_SIZE
    fallback = Image.new("RGBA", (w, h), (30, 30, 60, 255))
    return [fallback]


# -------- RANDOM POSITION --------
def random_position(size):
    max_x = CANVAS_SIZE[0] - size[0]
    max_y = CANVAS_SIZE[1] - size[1]

    if max_x <= 0 or max_y <= 0:
        return (0, 0)

    return (
        random.randint(0, max_x),
        random.randint(0, max_y)
    )


# -------- BUILD GIF --------
def build_gif(query):
    urls = search_gifs(query)

    if len(urls) < MAX_GIFS:
        raise Exception("Not enough GIFs found")

    gif_layers = []

    attempts = 0
    while len(gif_layers) < MAX_GIFS and attempts < MAX_FETCH_TRIES * 2:
        frames = get_valid_gif(urls)
        attempts += 1

        if not frames:
            continue

        # random scale
        scale = random.uniform(0.3, 0.8)
        resized = [
            f.resize(
                (int(f.width * scale), int(f.height * scale)),
                Image.Resampling.LANCZOS
            )
            for f in frames
        ]

        pos = random_position(resized[0].size)

        gif_layers.append({
            "frames": resized,
            "pos": pos
        })

    if len(gif_layers) < MAX_GIFS:
        raise Exception("Couldn't build enough valid GIF layers")

    bg_frames = get_random_background()

    total_frames = max(
        len(bg_frames),
        *(len(layer["frames"]) for layer in gif_layers)
    )

    output_frames = []

    for i in range(total_frames):
        canvas = Image.new("RGBA", CANVAS_SIZE)

        # background
        bg = bg_frames[i % len(bg_frames)].resize(
            CANVAS_SIZE,
            Image.Resampling.LANCZOS
        )
        canvas.paste(bg, (0, 0))

        # overlays
        for layer in gif_layers:
            frame = layer["frames"][i % len(layer["frames"])]
            canvas.paste(frame, layer["pos"], frame)

        output_frames.append(np.array(canvas))

    output = io.BytesIO()
    imageio.mimsave(
        output,
        output_frames,
        format="GIF",
        duration=FRAME_DURATION
    )
    output.seek(0)

    return output


# -------- COMMAND --------
@bot.command()
async def gif(ctx, *, query="random"):
    try:
        await ctx.message.add_reaction("👍")
        gif_file = build_gif(query)
        await ctx.send(file=discord.File(gif_file, "gif.gif"))

    except Exception as e:
        await ctx.send(f"Error: {e}")


# -------- RUN --------
bot.run(TOKEN)