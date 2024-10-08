# helpers.py

import os
import json
import logging
import requests
import random
import asyncio
import aiohttp
import websockets
import concurrent.futures
from datetime import datetime, timedelta
from discord.ext import tasks
from PIL import Image
import io
import uuid

from config import (
    CONFIG_FILE, HISTORY_FILE, WHATSNEW_FILE, USER_PROFILES_FILE,
    MAX_HISTORY_SIZE, BANNED_WORDS, STANDARD_EMOJIS, CUSTOM_EMOJIS,
    COMFYUI_API_URL, COMFYUI_API_TOKEN, COMFYUI_SERVER_ADDRESS, COMFYUI_SERVER_PORT
)

# ---------------------- Global Variables ----------------------

last_message_time = {}
inactivity_threshold = 260  # in minutes
chat_histories = {}
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
configurations = {}

# ---------------------- Helper Functions ----------------------

def get_absolute_path(filename):
    """Get the absolute path of a file relative to the script."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def load_configurations():
    """Load configurations from the JSON file."""
    config_path = get_absolute_path(CONFIG_FILE)
    if not os.path.exists(config_path):
        logging.info(f"{CONFIG_FILE} not found. Starting with empty configurations.")
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding {CONFIG_FILE}: {str(e)}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error loading {CONFIG_FILE}: {str(e)}")
        return {}

def save_configurations(configurations):
    """Save configurations to the JSON file."""
    config_path = get_absolute_path(CONFIG_FILE)
    try:
        with open(config_path, 'w', encoding='utf-8') as file:
            json.dump(configurations, file, indent=4)
        logging.info(f"Configurations saved to {CONFIG_FILE}.")
    except Exception as e:
        logging.error(f"Error saving configurations: {str(e)}")

def load_chat_history():
    """Load chat history from the log file."""
    history_path = get_absolute_path(HISTORY_FILE)
    if not os.path.exists(history_path):
        logging.info(f"{HISTORY_FILE} not found. Starting with empty chat histories.")
        return {}
    chat_histories_loaded = {}
    try:
        with open(history_path, 'r', encoding='utf-8') as file:
            for line in file:
                try:
                    parts = line.strip().split('] ')[1].split(':', 3)
                    guild_id, channel_id, username, content = parts
                    guild_id = int(guild_id)
                    channel_id = int(channel_id)
                    if channel_id not in chat_histories_loaded:
                        chat_histories_loaded[channel_id] = []
                    chat_histories_loaded[channel_id].append({"role": "user", "content": content})
                except Exception as e:
                    logging.error(f"Failed to parse line in chat history: {line}. Error: {str(e)}")
    except Exception as e:
        logging.error(f"Failed to load chat history: {str(e)}")
    return chat_histories_loaded

def log_chat_history(message):
    """Log chat history to a file and update in-memory chat_histories."""
    try:
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        history_path = get_absolute_path(HISTORY_FILE)
        with open(history_path, 'a', encoding='utf-8') as file:
            file.write(f"[{timestamp}] {message.guild.id}:{message.channel.id}:{message.author.display_name}: {message.content}\n")

        # Check if history file exceeds MAX_HISTORY_SIZE
        if os.path.getsize(history_path) > MAX_HISTORY_SIZE:
            with open(history_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            # Keep the last half of the lines
            with open(history_path, 'w', encoding='utf-8') as file:
                file.writelines(lines[len(lines)//2:])
            logging.info(f"Trimmed chat history to maintain under {MAX_HISTORY_SIZE} bytes.")

        # Update in-memory chat_histories
        channel_id = message.channel.id
        if channel_id not in chat_histories:
            chat_histories[channel_id] = []
        chat_histories[channel_id].append({"role": "user", "content": message.content})

        update_user_profile(message.author)
    except Exception as e:
        logging.error(f"Failed to log message: {str(e)}")

def update_user_profile(user):
    """Update user profile in JSON."""
    try:
        profiles_path = get_absolute_path(USER_PROFILES_FILE)
        profiles = {}
        if os.path.exists(profiles_path):
            with open(profiles_path, 'r', encoding='utf-8') as file:
                profiles = json.load(file)
        profiles[str(user.id)] = {  # Use string keys for JSON compatibility
            'last_seen': datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            'name': user.display_name
        }
        with open(profiles_path, 'w', encoding='utf-8') as file:
            json.dump(profiles, file, indent=4)
    except Exception as e:
        logging.error(f"Failed to update user profile: {str(e)}")

def get_member_statuses(guild):
    """Get a list of currently online members."""
    statuses = []
    for member in guild.members:
        if member.status != discord.Status.offline and not member.bot:
            status = f"{member.display_name} ({member.status})"
            statuses.append(status)
    return '\n'.join(statuses) if statuses else "No members are currently online."

def generate_response(conversation_text, guild, channel_id):
    """Generate a response using LMStudio."""
    personality = load_personality(guild.id)
    url = "http://localhost:1234/v1/chat/completions"  # Local LMStudio API endpoint
    headers = {"Content-Type": "application/json"}

    if channel_id not in chat_histories:
        chat_histories[channel_id] = []

    chat_histories[channel_id].append({"role": "user", "content": conversation_text})

    messages = [{"role": "system", "content": personality}] + chat_histories[channel_id]

    payload = {
        "model": "your-openwebui-model",  # Ensure correct model name
        "messages": messages,
        "temperature": 0.9
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        if response.content.strip():
            bot_response = response.json()["choices"][0]["message"]['content']
            chat_histories[channel_id].append({"role": "assistant", "content": bot_response})
            return bot_response
        else:
            return "Error: The response was empty."
    except requests.RequestException as e:
        logging.error(f"Response generation failed: {str(e)}")
        return f"Error: Failed to generate response due to {str(e)}"
    except ValueError as e:
        logging.error(f"JSON parsing failed: {str(e)}")
        return f"Error: Failed to parse response as JSON: {str(e)}"

async def generate_response_async(conversation_text, guild, channel_id):
    """Asynchronous wrapper for generate_response."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, generate_response, conversation_text, guild, channel_id)

def load_personality(guild_id):
    """Load personality from configuration or use default."""
    try:
        config = configurations.get(str(guild_id), {})
        return config.get('personality', "Your name is Chode. Always answer with short, direct answers. State that you are in Safe Mode.")
    except Exception as e:
        logging.error(f"Failed to load personality for guild {guild_id}: {str(e)}")
        return "Your name is Chode. Always answer with short, direct answers. State that you are in Safe Mode."

async def assign_role_based_on_activity(user, guild):
    """Assign the 'Active' role based on user activity."""
    if guild is None:
        return

    active_role = discord.utils.get(guild.roles, name="Active")
    if active_role and active_role not in user.roles:
        try:
            await user.add_roles(active_role)
            await user.send("You've been assigned the 'Active' role for your engagement!")
            logging.info(f"Assigned 'Active' role to {user.display_name} in guild {guild.name}")
        except Exception as e:
            logging.error(f"Failed to assign role: {str(e)}")

def fetch_custom_emojis(guild):
    """Fetch custom emojis from a guild."""
    try:
        CUSTOM_EMOJIS[guild.id] = [str(emoji) for emoji in guild.emojis]
        logging.debug(f"Fetched {len(CUSTOM_EMOJIS[guild.id])} custom emojis from guild '{guild.name}'.")
    except Exception as e:
        logging.error(f"Failed to fetch custom emojis for guild '{guild.name}': {str(e)}")

async def proactive_engagement(channel):
    """Send proactive engagement messages to inactive channels."""
    prompts = [
        "Hey everyone! How's your day going?",
        "What's something exciting you're working on?",
        "Need any help or have any questions?"
    ]
    prompt = random.choice(prompts)
    response = generate_image(prompt)
    if response and response.startswith("http"):
        try:
            await send_long_message(channel, f"Here is a generated image to spark the conversation: {response}")
            logging.info(f"Sent proactive image to {channel.name}: {response}")
        except Exception as e:
            logging.error(f"Failed to send proactive image to {channel.name}: {str(e)}")
    else:
        try:
            await send_long_message(channel, "No one has been active lately. Let's get the conversation going!")
            logging.info(f"Sent proactive engagement message to {channel.name}")
        except Exception as e:
            logging.error(f"Failed to send proactive engagement message to {channel.name}: {str(e)}")

def is_message_allowed(message_content):
    """Check if the message contains any banned words."""
    for word in BANNED_WORDS:
        if word in message_content.lower():
            return False
    return True

def generate_image(prompt):
    """Generate an image using ComfyUI."""
    try:
        headers = {
            "Authorization": f"Bearer {COMFYUI_API_TOKEN}",
            "Content-Type": "application/json"
        } if COMFYUI_API_TOKEN else {"Content-Type": "application/json"}

        payload = {
            "prompt": prompt,
            "width": 1024,
            "height": 1024,
            "steps": 30,
            "cfg_scale": 7.5
        }

        response = requests.post(COMFYUI_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "image_url" in data:
            return data["image_url"]
        else:
            return "Error: The API response did not contain an image URL."
    except requests.RequestException as e:
        logging.error(f"Image generation failed: {str(e)}")
        return f"Error: Failed to generate image due to {str(e)}"
    except ValueError as e:
        logging.error(f"JSON parsing failed: {str(e)}")
        return f"Error: Failed to parse response as JSON: {str(e)}"

def is_within_operating_hours(current_time, start_time, end_time):
    """Determine if the current time is within the operating hours."""
    if start_time <= end_time:
        result = start_time <= current_time <= end_time
    else:
        result = current_time >= start_time or current_time <= end_time
    logging.debug(f"Operating Hours Check - Start: {start_time}, End: {end_time}, Current: {current_time}, Within: {result}")
    return result

async def send_long_message(channel, content, filename="response.txt", **kwargs):
    """Send a long message to a Discord channel."""
    if len(content) <= 2000:
        try:
            await channel.send(content, **kwargs)
            logging.debug(f"Sent message to {channel.name}: {content[:50]}...")
        except Exception as e:
            logging.error(f"Failed to send message to {channel.name}: {str(e)}")
    else:
        try:
            chunks = [content[i:i+2000] for i in range(0, len(content), 2000)]
            for chunk in chunks:
                await channel.send(chunk, **kwargs)
                await asyncio.sleep(1)
            logging.debug(f"Sent long message to {channel.name} in {len(chunks)} parts.")
        except Exception as e:
            logging.error(f"Failed to send long message to {channel.name}: {str(e)}")
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                await channel.send(file=discord.File(fp=filename, filename=filename))
                logging.debug(f"Sent long message as file to {channel.name}.")
                os.remove(filename)
            except Exception as e2:
                logging.error(f"Failed to send message as file to {channel.name}: {str(e2)}")

async def check_inactivity(bot, configurations):
    """Check for inactive channels and send proactive engagement."""
    while True:
        now = datetime.utcnow()
        for guild in bot.guilds:
            guild_id_str = str(guild.id)
            config = configurations.get(guild_id_str, {})
            operating_hours = config.get('operating_hours')
            if operating_hours:
                try:
                    start_str, end_str = operating_hours.split('-')
                    start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
                    end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
                    current_time = datetime.now().time()
                    if not is_within_operating_hours(current_time, start_time, end_time):
                        continue
                except ValueError:
                    logging.error(f"Invalid operating hours format for guild {guild.id}. Expected 'HH:MM-HH:MM'.")
                    continue

            for channel in guild.text_channels:
                last_time = last_message_time.get(channel.id, now)
                if now - last_time > timedelta(minutes=inactivity_threshold):
                    await proactive_engagement(channel)
                    last_message_time[channel.id] = now
        await asyncio.sleep(60)

@tasks.loop(minutes=60)
async def scheduled_tasks(bot):
    """Scheduled tasks to run every hour."""
    for guild in bot.guilds:
        general_channel = discord.utils.get(guild.text_channels, name="general")
        if general_channel:
            prompt = "Provide a daily summary or reminder for the server."
            response = generate_response(prompt, guild, general_channel.id)
            try:
                if response:
                    await send_long_message(general_channel, response)
                    logging.info(f"Sent scheduled task message to {general_channel.name} in guild {guild.name}")
                else:
                    logging.warning(f"No response generated for daily summary in guild {guild.name}")
            except Exception as e:
                logging.error(f"Failed to send scheduled task message in guild {guild.name}: {str(e)}")

