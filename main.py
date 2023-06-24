import requests
import discord
import asyncio
import replicate
from datetime import datetime, timedelta
import random
import pandas
import os
import json
from urllib.parse import quote
import yt_dlp
import queue

voice_clients = {}
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")
song_queues = {}
yt_dl_opts = {'format': 'bestaudio/best'}
ytdl = yt_dlp.YoutubeDL(yt_dl_opts)
ffmpeg_options = {'options': "-vn"}
champ_data = pandas.read_json("./champions.json")
API_KEY = os.environ.get("RIOT_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
TOKEN = os.environ.get("TOKEN")
CHANNEL_ID = 1111027488253022310  
BOT_USER_ID = 776149156745183282
TARGET_HOURS = [18]
intents = discord.Intents.all()
intents.message_content = True
intents.presences = True
intents.members = True
intents.guilds = True
intents.voice_states = True
client = discord.Client(intents=intents)
replicate.Client(api_token=REPLICATE_API_TOKEN)

waifu_category_list_for_lazy_people_sfw = ["waifu", "neko", "shinobu", "megumin", "bully", "cuddle", "cry", "hug",
                                           "awoo", "kiss", "lick", "pat", "smug",
                                           "bonk", "yeet", "blush", "smile", "wave", "highfive", "handhold", "nom",
                                           "bite", "glomp", "slap", "kill",
                                           "kick", "happy", "wink", "poke", "dance", "cringe"]
waifu_category_list_for_lazy_people_nsfw = ["waifu", "neko", "trap", "blowjob"]
waifu_type_list = ["nsfw", "sfw"]


class CustomQueue(queue.Queue):
    def put_start(self, item):
        self.queue.appendleft(item)


@client.event
async def on_ready():
    print(f'Logged in as {client.user.name} ({client.user.id})')
    print('---------------------------------------------------')
    await send_now()  # Send a message immediately after the bot starts
    await send_scheduled_messages()


@client.event
async def play_next_song(guild_id):
    if guild_id in song_queues and not song_queues[guild_id].empty():

        url = song_queues[guild_id].queue[0]  # Get the URL of the song without removing it from the queue
        try:
            ytdl = yt_dlp.YoutubeDL({'format': 'bestaudio'})

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            ffmpeg_options = {
                'options': '-vn',
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
            }
            song = data['url']
            player = discord.FFmpegPCMAudio(song, **ffmpeg_options)

            voice_client = voice_clients[guild_id]
            voice_client.play(player)


            while voice_client.is_playing() or voice_client.is_paused():
                await asyncio.sleep(1)

            # Song finished playing, remove it from the queue
            song_queues[guild_id].get()

            # Check if there are more songs in the queue
            if not song_queues[guild_id].empty():
                await play_next_song(guild_id)
            else:
                # Queue is empty, bot needs to join the voice channel again
                if guild_id in voice_clients:
                    voice_client = voice_clients[guild_id]
                    await voice_client.disconnect()
                    del voice_clients[guild_id]
                    # Check if the bot is already in a voice channel and rejoin
                    if not voice_client.channel:
                        await voice_client.channel.connect()
                        print("Rejoined the voice channel.")


        except Exception as err:
            print(f"Error playing song: {err}")


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if "?p" in message.content:
        try:
            if message.guild.id not in song_queues:
                song_queues[message.guild.id] = queue.Queue()

            voice_client = voice_clients.get(message.guild.id)

            if voice_client:
                # Check if the bot is already connected to a voice channel
                if voice_client.is_playing() or voice_client.is_paused():
                    # Add the URL to the song queue
                    query = " ".join(message.content.split(maxsplit=1)[1:])
                    ydl_opts = {
                        'default_search': 'ytsearch',
                        'noplaylist': True,
                        'quiet': True,
                        'format': 'bestaudio/best',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info_dict = ydl.extract_info(query, download=False)
                        if 'entries' in info_dict:
                            # If the query search returned multiple results, choose the first one
                            info_dict = info_dict['entries'][0]
                        song_url = f"https://www.youtube.com/watch?v={info_dict['id']}"
                        song_title = info_dict['title']

                        if song_url is None:
                            raise ValueError('No URL found for the video.')

                    song_queues[message.guild.id].put(song_url)

                    await message.channel.send(f"Song added to queue:\n{song_title}")
                    return

                # Check if the bot is already connected to the user's voice channel
                if voice_client.channel == message.author.voice.channel:
                    # Bot is already connected to the user's voice channel
                    query = " ".join(message.content.split(maxsplit=1)[1:])
                    ydl_opts = {
                        'default_search': 'ytsearch',
                        'noplaylist': True,
                        'quiet': True,
                        'format': 'bestaudio/best',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info_dict = ydl.extract_info(query, download=False)
                        if 'entries' in info_dict:
                            # If the query search returned multiple results, choose the first one
                            info_dict = info_dict['entries'][0]
                        song_url = f"https://www.youtube.com/watch?v={info_dict['id']}"
                        song_title = info_dict['title']
                        print(song_title)

                        if song_url is None:
                            raise ValueError('No URL found for the video.')

                    song_queues[message.guild.id].put(song_url)
                    await message.channel.send(f"Song added to queue:\n{song_title}")
                    print(song_queues[message.guild.id].queue)

                    if not voice_client.is_playing() and not voice_client.is_paused():
                        await play_next_song(message.guild.id)
                    return

                # Disconnect from the current voice channel
                await voice_client.disconnect()
                del voice_clients[message.guild.id]

            if message.author.voice and message.author.voice.channel:
                # Connect to the user's voice channel
                voice_channel = message.author.voice.channel
                voice_client = await voice_channel.connect()
                voice_clients[message.guild.id] = voice_client

                query = " ".join(message.content.split(maxsplit=1)[1:])
                ydl_opts = {
                    'default_search': 'ytsearch',
                    'noplaylist': True,
                    'quiet': True,
                    'format': 'bestaudio/best',
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(query, download=False)
                    if 'entries' in info_dict:
                        # If the query search returned multiple results, choose the first one
                        info_dict = info_dict['entries'][0]
                    song_url = f"https://www.youtube.com/watch?v={info_dict['id']}"
                    song_title = info_dict['title']
                    print(song_title)

                    if song_url is None:
                        raise ValueError('No URL found for the video.')

                song_queues[message.guild.id].put(song_url)
                await message.channel.send(f"Song added to queue:\n{song_title}")
                print(song_queues[message.guild.id].queue)

                if not voice_client.is_playing() and not voice_client.is_paused():
                    await play_next_song(message.guild.id)

        except Exception as err:
            print(f"Error playing song: {err}")

    if "?next" in message.content:
        try:
            guild_id = message.guild.id
            if guild_id in voice_clients and voice_clients[guild_id]:
                if voice_clients[guild_id].is_playing() or voice_clients[guild_id].is_paused():
                    voice_clients[guild_id].stop()
                    await message.channel.send("Skipped the current song.")
                else:
                    if not song_queues[guild_id].empty():
                        await play_next_song(guild_id)
                        await message.channel.send("Skipped the current song.")
                    else:
                        await message.channel.send("The queue is empty.")
            else:
                await message.channel.send("The bot is not connected to a voice channel.")

        except Exception as err:
            print(f"Error skipping to next song: {err}")

    if "?queue" in message.content:
        try:
            if message.guild.id in song_queues:

                queue_list = list(song_queues[message.guild.id].queue)
                print(queue_list)
                queue_message = "Current queue:\n"

                if voice_clients[message.guild.id].is_playing() or voice_clients[message.guild.id].is_paused():
                    current_song = song_queues[message.guild.id].queue[0]  # Get the currently playing song
                    queue_message += ""

                    if len(queue_list) > 0:
                        for i, item in enumerate(queue_list):
                            if isinstance(item, tuple):
                                # If it's a tuple, extract the title and URL
                                song_title, url = item
                                queue_message += f"{i}. {song_title} - {url}\n"
                            else:
                                # If it's not a tuple, assume it's a query
                                queue_message += f"{i}. {item}\n"
                    else:
                        queue_message += "No songs in the queue.\n"
                else:
                    if len(queue_list) > 0:
                        for i, item in enumerate(queue_list):
                            if isinstance(item, tuple):
                                # If it's a tuple, extract the title and URL
                                song_title, url = item
                                queue_message += f"{i}. {song_title} - {url}\n"
                            else:
                                # If it's not a tuple, assume it's a query
                                queue_message += f"{i}. {item}\n"
                    else:
                        queue_message += "The queue is currently empty."

                await message.channel.send(queue_message)
            else:
                await message.channel.send("The queue is currently empty.")

        except Exception as err:
            print(f"Error displaying queue: {err}")

    if "?remove" in message.content:
        try:
            index = int(message.content.split()[1]) - 1

            if message.guild.id in song_queues and index >= 0 and index < song_queues[message.guild.id].qsize():
                if index == 0 and voice_clients[message.guild.id].is_playing():
                    voice_clients[message.guild.id].stop()

                else:
                    queue_list = list(song_queues[message.guild.id].queue)
                    removed_song = queue_list.pop(index)
                    song_queues[message.guild.id] = queue.Queue()
                    for song in queue_list:
                        song_queues[message.guild.id].put(song)
                    await message.channel.send(f"Removed song from queue: {removed_song}")
                    print(f"Removed song from queue: {removed_song}")

        except Exception as err:
            print(f"Error removing song from queue: {err}")
    if "?pause" in message.content:
        try:
            voice_clients[message.guild.id].pause()
        except Exception as err:
            print(f"Error pausing song: {err}")
    # Resume the current song if it's been paused
    if "?resume" in message.content:
        try:
            voice_clients[message.guild.id].resume()
        except Exception as err:
            print(f"Error resuming song: {err}")
    # Stop the currently playing song and disconnect from the voice channel
    if "?quit" in message.content:
        try:
            voice_clients[message.guild.id].stop()
            await voice_clients[message.guild.id].disconnect()
            await message.channel.send("Successfully left the channel.")
        except Exception as err:
            print(f"Error stopping song: {err}")

    if message.content.lower() == "?commands randomwaifu":
        await message.channel.send("Selectable categories for ?randomwaifu:\n\n"
                                   "For SFW:\n"
                                   "waifu, neko, shinobu, megumin, bully, cuddle, cry, hug, awoo, kiss, lick, pat, smug,"
                                   " bonk, yeet, blush, smile, wave, highfive, handhold, nom, bite , glomp, slap, kill,"
                                   " kick, happy, wink, poke, dance, cringe\n\n"
                                   "For NSFW:\n"
                                   "waifu, neko, trap, blowjob")

    if message.content.lower() == "?commands":
        await message.channel.send("-------***AVAILABLE COMMANDS : 19***-------\n"
                                   "For the commands with $ at the beginning:\n"
                                   "Type '?commands [command] for specific info.'\n"
                                   "------------------------------------------\n"
                                   "?hello: Greets you.\n"
                                   "?dnd game start: Plays a short dnd game with you.\n\n\n"


                                   "?play [youtube url]: Plays a song.\n"
                                   "?pause: Pauses the current playing song.\n"
                                   "?resume: Resumes the current playing song.\n"
                                   "?quit: Stops the current playing song and disconnects from the joined channel.\n"
                                   "?next: If there's a queue, plays the next song.\n"
                                   "?remove [queue number]: Removes the song with the queue number index from queue.\n"
                                   "?queue: Shows the song playing and to be played.\n\n\n"


                                   "?randomfox: Shows a random fox image.\n"
                                   "?randomdog: Shows a random dog image.\n"
                                   "?randomcat: Shows a random cat image.\n"
                                   "?randomnews: Shows random news.\n"
                                   "($)?randomwaifu [nsfw/sfw] [category]: Shows a random anime girl image, "
                                   "using parameters is optional.\n"
                                   "?joke me: Jokes you.\n\n\n"


                                   "?lolmastery [Champion Name(no spaces)] [Summoner Name(no spaces)] [Server]: "
                                   "Shows the mastery points for desired character.\n"

                                   "?lollevel [Summoner Name(no spaces)] [Server]: Shows account level on League of Legends.\n"

                                   "?lolrank [Summoner Name(no spaces)] [Server] [flex/soloq]: "
                                   "Shows flex or soloq rank on League of Legends.")

    if "?lolmastery" in message.content.lower():
        split_content = message.content.split()
        server_name = split_content[-1].lower().upper()
        champ_name = split_content[1].lower().title()
        summoner_name = split_content[2]
        if len(split_content) == 5:
            summoner_name = split_content[2] + split_content[3]
        elif len(split_content) == 6:
            summoner_name = split_content[2] + split_content[3]
        elif len(split_content) == 7:
            summoner_name = split_content[2] + split_content[3] + split_content[4]
        elif len(split_content) == 8:
            summoner_name = split_content[2] + split_content[3] + split_content[4] + split_content[5]

        champ_title = champ_data["data"][champ_name]["title"]
        mastery_points = await get_mastery_points(summoner_name, champ_name, server_name)
        if mastery_points is not None:
            await message.channel.send(
                f"{server_name} {summoner_name} has {mastery_points} mastery points on {champ_name}, {champ_title}.")
            if mastery_points > 1000000:
                await message.channel.send("1 million?!")
            elif mastery_points == 0:
                await message.channel.send("0? How come you have never played this character?")
        else:
            await message.channel.send("Failed to retrieve mastery points.")

    if "?lollevel" in message.content.lower():
        server_name = message.content.split()[2].upper()
        summoner_name = message.content.split()[1]
        summoner_level = await get_summoner_level(summoner_name, server_name)
        await message.channel.send(f"{server_name} {summoner_name}'s level is {summoner_level}.")

    if "?lolrank" in message.content.lower():
        ranked_type = message.content.split()[3]
        summoner_name = message.content.split()[1]
        server_name = message.content.split()[2].upper()
        if ranked_type == "flex":
            summoner_rank = await get_summoner_rank_flex(summoner_name, server_name)
            await message.channel.send(f"{server_name} {summoner_name}'s {ranked_type} rank is {summoner_rank}.")
        if ranked_type == "soloq":
            summoner_rank = await get_summoner_rank_soloq(summoner_name, server_name)
            await message.channel.send(f"{server_name} {summoner_name}'s {ranked_type} rank is {summoner_rank}.")

    if message.content.lower() == '?hello':
        response = 'Hi, how can I help?'
        await message.channel.send(response)

    if message.content.lower() == "?randomfox":
        fox_response = requests.get("https://randomfox.ca/floof/?ref=apilist.fun#")
        await message.channel.send(fox_response.json()["image"])

    if "?randomwaifu" in message.content.lower():
        split_waifu = message.content.split()
        if len(split_waifu) == 3:
            waifu_type = split_waifu[1]
            waifu_category = split_waifu[2]
            waifu_response = requests.get(url=f"https://api.waifu.pics/{waifu_type}/{waifu_category}")
            await message.channel.send(waifu_response.json()["url"])
        elif len(split_waifu) == 2:
            waifu_type = split_waifu[1]
            if waifu_type == "nsfw":
                random_category = random.choice(waifu_category_list_for_lazy_people_nsfw)
                waifu_response = requests.get(url=f"https://api.waifu.pics/{waifu_type}/{random_category}")
                await message.channel.send(waifu_response.json()["url"])
            else:
                random_category = random.choice(waifu_category_list_for_lazy_people_sfw)
                waifu_response = requests.get(url=f"https://api.waifu.pics/sfw/{random_category}")
                await message.channel.send(waifu_response.json()["url"])

        else:
            random_category = random.choice(waifu_category_list_for_lazy_people_sfw)
            waifu_response = requests.get(url=f"https://api.waifu.pics/sfw/{random_category}")
            await message.channel.send(waifu_response.json()["url"])

    if message.content.lower() == "?randomcat":
        cat_response = requests.get("https://api.thecatapi.com/v1/images/search")
        print(cat_response.json())
        await message.channel.send(cat_response.json()[0]["url"])

    if message.content.lower() == "?randomdog":
        dog_response = requests.get("https://random.dog/woof.json?ref=apilist.fun")
        print(dog_response.json())
        await message.channel.send(dog_response.json()["url"])

    if message.content.lower() == "?joke me":
        joke_response = requests.get("https://v2.jokeapi.dev/joke/Any")
        if joke_response.json()["type"] == "twopart":
            await message.channel.send(joke_response.json()["setup"])
            await asyncio.sleep(5)
            await message.channel.send(joke_response.json()["delivery"])
        if joke_response.json()["type"] == "single":
            await message.channel.send(joke_response.json()["joke"])

    if message.content.lower() == "?randomnews" :
        news_response = requests.get(url=f"https://newsapi.org/v2/top-headlines?country=tr&apiKey={NEWS_API_KEY}")
        news_response.raise_for_status()
        print(news_response.json())
        articles = news_response.json()["articles"]

        if articles:
            random_article = random.choice(articles)
            await message.channel.send(random_article["title"])
            if random_article["description"] != None:
                await message.channel.send(random_article["description"])
            await message.channel.send(random_article["url"])
        else:
            await message.channel.send("No news articles found.")
    if message.content.lower() == '?dnd game start':
        player_id = message.author.id
        response = "Game starts!\nYou have entered a room with 2 doors, on the right side, " \
                   "there is a door with a mark of a bear's claw on it. On the left side " \
                   "there is a door with a mark of a lion's claw on it. Which door will you pick?(lion/bear)"
        await message.channel.send(response)

        def check(m):
            return m.author.id == player_id and m.channel == message.channel

        try:
            reply = await client.wait_for('message', check=check, timeout=30)
            if reply.content.lower() == 'lion':
                response = "You won an item:\nLion's Roar\n\nYou beat the lion.  " \
                           "Now you are facing 2 powerful enemies. One of them is a thousand year old vampire, " \
                           "other one is a simple doctor. You have to attack one of them." \
                           "(vampire/doctor)"
                await message.channel.send(response)
                try:
                    reply = await client.wait_for('message', check=check, timeout=30)
                    if reply.content.lower() == 'vampire':
                        response = "You couldn't win against the vampire, he was too strong for you. You died.(end)"
                    elif reply.content.lower() == 'doctor':
                        response = "You have won! You now work as a part-time doctor replacing the doctor you won against.(end)"
                    else:
                        response = "You entered an invalid option."
                except asyncio.TimeoutError:
                    response = "Game ended because you didn't answer."


            elif reply.content.lower() == 'bear':
                response = "You won an item:\nBear's Paw(end)"
            else:
                response = "You entered an invalid option."
        except asyncio.TimeoutError:
            response = "Game ended because you didn't answer."
        await message.channel.send(response)


@client.event
async def send_scheduled_messages():
    channel = client.get_channel(CHANNEL_ID)
    while True:
        now = datetime.now()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        if now.hour in TARGET_HOURS:
            message = f"Hello, it's {now.strftime('%H:%M')}! This is an automated message."
            await channel.send(message)

        delta = next_hour - datetime.now()
        await asyncio.sleep(delta.seconds)


async def get_summoner_rank_flex(summoner_name, server):
    summoner_name = quote(summoner_name)
    url = f"https://{server}1.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        summoner_data = response.json()
        summoner_id = summoner_data["id"]

        rank_url = f"https://{server}1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}?api_key={API_KEY}"
        rank_response = requests.get(rank_url)
        rank_response.raise_for_status()
        rank_data = rank_response.json()

        ranked_info = None
        for entry in rank_data:
            if entry["queueType"] == "RANKED_FLEX_SR":
                ranked_info = entry
                break

        if ranked_info:
            tier = ranked_info["tier"]
            rank = ranked_info["rank"]
            lp = ranked_info["leaguePoints"]
            wins = ranked_info["wins"]
            losses = ranked_info["losses"]
            return f"{tier} {rank} (LP: {lp}, W: {wins}, L: {losses})"
        else:
            return "Unranked"
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")
        return None


async def get_summoner_rank_soloq(summoner_name, server):
    summoner_name = quote(summoner_name)
    url = f"https://{server}1.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        summoner_data = response.json()
        summoner_id = summoner_data["id"]

        rank_url = f"https://{server}1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}?api_key={API_KEY}"
        rank_response = requests.get(rank_url)
        rank_response.raise_for_status()
        rank_data = rank_response.json()

        ranked_info = None
        for entry in rank_data:
            if entry["queueType"] == "RANKED_SOLO_5x5":
                ranked_info = entry
                break

        if ranked_info:
            tier = ranked_info["tier"]
            rank = ranked_info["rank"]
            lp = ranked_info["leaguePoints"]
            wins = ranked_info["wins"]
            losses = ranked_info["losses"]
            return f"{tier} {rank} (LP: {lp}, W: {wins}, L: {losses})"
        else:
            return "Unranked"
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")
        return None


async def get_summoner_level(summoner_name, server):
    summoner_name = quote(summoner_name)
    url = f"https://{server}1.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={API_KEY}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        summoner_data = response.json()
        summoner_level = summoner_data["summonerLevel"]
        return summoner_level
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")
        return None


async def get_mastery_points(summoner_name, champ_name, server):
    summoner_name = quote(summoner_name)
    url = f"https://{server}1.api.riotgames.com/lol/summoner/v4/summoners/by-name/{summoner_name}?api_key={API_KEY}"
    champ_data = None

    with open("./champions.json", "r") as file:
        champ_data = json.load(file)
        print(champ_data)

    champ_id = int(champ_data["data"][champ_name]["key"])

    print(champ_id)
    try:
        response = requests.get(url)
        response.raise_for_status()
        summoner_id = response.json()["id"]

        mastery_url = f"https://{server}1.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-summoner/{summoner_id}?api_key={API_KEY}"
        mastery_response = requests.get(mastery_url)
        mastery_response.raise_for_status()
        mastery_data = mastery_response.json()
        print(mastery_data)

        champ_mastery = next((mastery for mastery in mastery_data if mastery["championId"] == champ_id), None)
        print(champ_mastery)
        if champ_mastery:
            return champ_mastery["championPoints"]
        else:
            return 0
    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")
        return None


async def send_now():
    channel = client.get_channel(CHANNEL_ID)
    message = "ikigai online\n" \
              "My prefix is '?'"
    await channel.send(message)


client.run(TOKEN)

