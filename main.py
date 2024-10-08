import discord
from discord.ext import commands
import logging
import asyncio

from config import DISCORD_TOKEN  # Uses DISCORD_BOT_TOKEN2 from config.py
from helpers import (
    configurations, load_configurations, load_chat_history, chat_histories,
    fetch_custom_emojis, check_inactivity, scheduled_tasks
)
import events
import commands as bot_commands  # Alias to avoid conflict with 'commands' module

# ---------------------- Initialize Bot ----------------------

# Define Discord intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.presences = True
intents.members = True
intents.guilds = True

# Initialize the Bot with '!!' as the command prefix
bot = commands.Bot(command_prefix='!!', intents=intents)

# Load configurations and chat history at startup
configurations.update(load_configurations())
chat_histories.update(load_chat_history())
logging.info("Chat history loaded successfully.")

# Setup events and commands
events.setup(bot)
bot_commands.setup(bot)

# ---------------------- Bot Events ----------------------

@bot.event
async def on_ready():
    """Event triggered when the bot is ready."""
    print(f'Logged in as {bot.user}!')
    bot.loop.create_task(check_inactivity(bot, configurations))
    scheduled_tasks.start(bot)
    logging.info(f'Bot connected as {bot.user}')

    # Fetch custom emojis from all guilds the bot is part of
    for guild in bot.guilds:
        fetch_custom_emojis(guild)
        logging.info(f"Fetched custom emojis for guild: {guild.name} (ID: {guild.id})")

# ---------------------- Run the Bot ----------------------

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)  # Uses DISCORD_BOT_TOKEN2 from the environment
    except Exception as e:
        logging.critical(f"Failed to run the bot: {str(e)}")

