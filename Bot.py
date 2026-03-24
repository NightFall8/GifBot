import discord, requests, random, io, numpy as np, imageio.v2 as imageio, json
from discord.ext import commands
from PIL import Image, ImageSequence

config = json.load(open("config.json"))
# ==========================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config["prefix"], intents=intents)


# -------- GIPHY SEARCH --------
def search_gifs(query, limit=30):
    url = "https://api.giphy.com/v1/gifs/search"
    params = {
        "api_key": config["giphy_key"],
        "q": query,
        "limit": limit,
        "rating": "pg-13"
    }

    try:
        r = requests.get(url, params=params, headers=config["headers"], timeout=10)
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
        r = requests.get(url, headers=config["headers"], timeout=10)
        img = Image.open(io.BytesIO(r.content))
    except:
        return None

    frames = []
    for frame in ImageSequence.Iterator(img):
        frames.append(frame.convert("RGBA"))

    if not frames:
        return None

    # filter tiny gifs
    if frames[0].width < config["min_width"] or frames[0].height < config["min_height"]:
        return None

    return frames[:config["max_frames"]]


# -------- PICK WORKING GIF --------
def get_valid_gif(urls):
    for _ in range(config["max_fetch_tries"]):
        url = random.choice(urls)
        frames = load_gif(url)
        if frames:
            return frames

    return None


# -------- RANDOM BACKGROUND --------
def get_random_background():
    urls = search_gifs("landscape background sky", 25)

    for _ in range(config["max_fetch_tries"]):
        if not urls:
            break

        frames = get_valid_gif(urls)
        if frames:
            return frames

    # fallback gradient (only if everything fails)
    w, h = config["canvas_size_x"], config["canvas_size_y"]
    fallback = Image.new("RGBA", (w, h), (30, 30, 60, 255))
    return [fallback]


# -------- RANDOM POSITION --------
def random_position(size):
    max_x = config["canvas_size_x"] - size[0]
    max_y = config["canvas_size_y"] - size[1]

    if max_x <= 0 or max_y <= 0:
        return (0, 0)

    return (
        random.randint(0, max_x),
        random.randint(0, max_y)
    )


# -------- BUILD GIF --------
def build_gif(query):
    urls = search_gifs(query)

    if len(urls) < config["max_gifs"]:
        raise Exception("Not enough GIFs found")

    gif_layers = []

    attempts = 0
    while len(gif_layers) < config["max_gifs"] and attempts < config["max_fetch_tries"] * 2:
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

    if len(gif_layers) < config["max_gifs"]:
        raise Exception("Couldn't build enough valid GIF layers")

    bg_frames = get_random_background()

    total_frames = max(
        len(bg_frames),
        *(len(layer["frames"]) for layer in gif_layers)
    )

    output_frames = []

    for i in range(total_frames):
        canvas = Image.new("RGBA", (config["canvas_size_x"], config["canvas_size_y"]))

        # background
        bg = bg_frames[i % len(bg_frames)].resize(
            (config["canvas_size_x"], config["canvas_size_y"]),
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
        format="GIF", # type: ignore
        duration=config["frame_duration"],
        loop=0
    ) # type: ignore
    output.seek(0)

    return output

# # -------- SINGULAR GIF --------
# def build_singular_gif(query):
#     url = search_gifs(query)

#     if not url:
#         raise Exception("No GIF found")
#     frames = get_valid_gif(url)
#     if not frames:
#         raise Exception("No valid GIF found")
#     output = io.BytesIO()
#     imageio.mimsave(
#         output,
#         [np.array(f) for f in frames],
#         format="GIF", # type: ignore
#         duration=config["frame_duration"],
#         loop=0
#     ) # type: ignore
#     output.seek(0)

#     return output


# -------- COMMANDS --------
@bot.hybrid_command(name="gif", description="Generate a random GIF based on your query")
async def gif(ctx: commands.Context, *, query="random"):
    try:
        if ctx.interaction:
            await ctx.defer()
        else:
            await ctx.message.add_reaction("👍")
        gif_file = build_gif(query)
        await ctx.send(file=discord.File(gif_file, "gif.gif"))

    except Exception as e:
        await ctx.send(f"Error: {e}")
        
# @bot.hybrid_command(name="singular", description="Get a single random GIF based on your query")
# async def singular(ctx: commands.Context, *, query="random"):
#     try:
#         if ctx.interaction:
#             await ctx.defer()
#         else:
#             await ctx.message.add_reaction("👍")
#         gif_file = build_singular_gif(query)
#         await ctx.send(file=discord.File(gif_file, "gif.gif"))

#     except Exception as e:
#         await ctx.send(f"Error: {e}")


# -------- EVENTS --------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} and commands synced.")

# -------- RUN --------
bot.run(config["token"])