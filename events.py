import logging
import discord
from helpers import (
    log_chat_history, assign_role_based_on_activity, generate_response_async,
    send_long_message, is_message_allowed, is_within_operating_hours,
    fetch_custom_emojis, last_message_time, configurations, chat_histories
)

def setup(bot):

    @bot.event
    async def on_guild_join(guild):
        """Event triggered when the bot joins a new guild."""
        fetch_custom_emojis(guild)
        logging.info(f"Joined new guild: {guild.name} (ID: {guild.id}) and fetched its custom emojis.")

    @bot.event
    async def on_member_join(member):
        """Event triggered when a new member joins the guild."""
        guild = member.guild
        welcome_channel = discord.utils.get(guild.text_channels, name="welcome")
        if welcome_channel:
            prompt = f"Welcome {member.display_name} to the server! Make them feel at home."
            response = generate_response_async(prompt, guild, welcome_channel.id)
            try:
                if response:
                    await send_long_message(welcome_channel, response)
                    logging.info(f"Sent welcome message to {member.display_name} in guild {guild.name}")
                else:
                    logging.warning(f"No response generated for welcome message to {member.display_name} in guild {guild.name}")
            except Exception as e:
                logging.error(f"Failed to send welcome message: {str(e)}")

    @bot.event
    async def on_reaction_add(reaction, user):
        """Event triggered when a reaction is added to a message."""
        if user == bot.user:
            return

        message = reaction.message
        guild = message.guild

        # Only respond to reactions on the bot's own messages
        if message.author != bot.user:
            return

        prompt = f"{user.display_name} reacted with {reaction.emoji} to my message. Acknowledge their reaction."
        response = generate_response_async(prompt, guild, message.channel.id)
        try:
            if response:
                await send_long_message(message.channel, response)
                logging.info(f"Sent reaction acknowledgment to {user.display_name}: {response[:50]}...")
            else:
                logging.warning(f"No response generated for reaction from {user.display_name}")
        except Exception as e:
            logging.error(f"Failed to send reaction acknowledgment: {str(e)}")

    @bot.event
    async def on_message(message):
        """Event triggered when a new message is received."""
        if message.author == bot.user:
            return

        # Log and update activity
        log_chat_history(message)
        last_message_time[message.channel.id] = discord.utils.utcnow()

        guild = message.guild
        if guild:
            guild_id = str(guild.id)
        else:
            guild_id = None

        if guild_id and guild_id in configurations:
            config = configurations[guild_id]
            operating_hours = config.get('operating_hours')
            if operating_hours:
                try:
                    start_str, end_str = operating_hours.split('-')
                    start_time = discord.utils.parse_time(start_str.strip())
                    end_time = discord.utils.parse_time(end_str.strip())
                    within_hours = is_within_operating_hours(discord.utils.utcnow().time(), start_time, end_time)
                except ValueError:
                    logging.error(f"Invalid operating hours format for guild {guild_id}.")
                    within_hours = False
            else:
                within_hours = True
        else:
            within_hours = True

        if not is_message_allowed(message.content):
            try:
                await message.delete()
                await send_long_message(channel=message.channel, content=f"Sorry {message.author.mention}, your message contained inappropriate language.")
                logging.info(f"Deleted inappropriate message from {message.author.display_name}: {message.content}")
            except Exception as e:
                logging.error(f"Failed to delete message or send warning: {str(e)}")
            return

        # Handle interactions
        if 'chode' in message.content.lower() or message.content.startswith('!!'):
            prompt = f"{message.author.display_name} has said: {message.content}"
            async with message.channel.typing():
                response_from_chode = await generate_response_async(prompt, guild, message.channel.id)
                if response_from_chode:
                    await send_long_message(message.channel, response_from_chode)
                    logging.info(f"Responded to message from {message.author.display_name}: {response_from_chode[:50]}...")

