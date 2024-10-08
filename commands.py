# commands.py

import discord
from discord.ext import commands
import logging
import asyncio
from datetime import datetime
from helpers import (
    generate_response_async, send_long_message, get_member_statuses,
    is_within_operating_hours, save_configurations, configurations,
    generate_image
)
from config import WHATSNEW_FILE, get_absolute_path, COMFYUI_SERVER_ADDRESS, COMFYUI_SERVER_PORT
import aiohttp
import websockets
import uuid
from PIL import Image
import io

def setup(bot):

    @bot.command(name='operatinghours')
    async def operating_hours(ctx):
        """Responds with the server's operating hours."""
        guild_id = str(ctx.guild.id)
        config = configurations.get(guild_id)
        if not config:
            await send_long_message(ctx.channel, "Operating hours are not configured for this server.")
            logging.warning(f"Operating hours requested but not configured in guild {ctx.guild.name}")
            return

        operating_hours = config.get('operating_hours', "Not set")
        prompt = f"{ctx.author.display_name} has asked what your operating hours are. After looking it up, you now know that your hours of operation are {operating_hours}."

        async with ctx.typing():
            response_from_chode = await generate_response_async(prompt, ctx.guild, ctx.channel.id)
            if response_from_chode and len(response_from_chode) > 0:
                await send_long_message(ctx.channel, response_from_chode)
                logging.info(f"Responded to operating hours request from {ctx.author.display_name}: {response_from_chode[:50]}...")
            else:
                await send_long_message(ctx.channel, "Sorry, I couldn't retrieve my operating hours at the moment.")
                logging.warning(f"No response generated for operating hours request from {ctx.author.display_name}")

    @bot.command(name='timecheck')
    async def time_check(ctx):
        """Responds with the current UTC and local times."""
        try:
            utc_now = datetime.utcnow()
            local_now = datetime.now()
            response = (f"**Current UTC Time:** {utc_now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"**Current Local Time:** {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
            await send_long_message(channel=ctx.channel, content=response)
            logging.info(f"Sent timecheck to {ctx.author.display_name}")
        except Exception as e:
            logging.error(f"Failed to execute timecheck command: {str(e)}")
            await send_long_message(ctx.channel, "Sorry, I couldn't retrieve the current time due to an error.")

    @bot.command(name='members')
    async def members(ctx):
        """Responds with a list of currently online members."""
        try:
            statuses = get_member_statuses(ctx.guild)
            await send_long_message(ctx.channel, f"**Online Members:**\n{statuses}")
            logging.info(f"Sent members list to {ctx.author.display_name}")
        except Exception as e:
            logging.error(f"Failed to execute members command: {str(e)}")
            await send_long_message(ctx.channel, "Sorry, I couldn't retrieve the member list due to an error.")

    @bot.command(name='whatsnew')
    async def whats_new(ctx):
        """Responds with the latest features or updates."""
        try:
            whatsnew_path = get_absolute_path(WHATSNEW_FILE)
            if not os.path.exists(whatsnew_path):
                await send_long_message(ctx.channel, "There are no new updates at the moment.")
                logging.info(f"WhatsNew file not found when requested by {ctx.author.display_name}")
                return

            with open(whatsnew_path, 'r', encoding='utf-8') as file:
                whats_new_list = file.read().strip()

            if not whats_new_list:
                await send_long_message(ctx.channel, "There are no new updates at the moment.")
                logging.info(f"WhatsNew file is empty when requested by {ctx.author.display_name}")
                return

            prompt = f"{ctx.author.display_name} wants to know what's new. You have the following updates to share:\n{whats_new_list}"
            
            async with ctx.typing():
                response_from_chode = await generate_response_async(prompt, ctx.guild, ctx.channel.id)
                if response_from_chode and len(response_from_chode) > 0:
                    await send_long_message(ctx.channel, response_from_chode)
                    logging.info(f"Responded to whatsnew request from {ctx.author.display_name}: {response_from_chode[:50]}...")
                else:
                    await send_long_message(ctx.channel, "Sorry, I couldn't retrieve the latest updates at the moment.")
                    logging.warning(f"No response generated for whatsnew request from {ctx.author.display_name}")
        except Exception as e:
            logging.error(f"Failed to execute whatsnew command: {str(e)}")
            await send_long_message(ctx.channel, "An error occurred while retrieving the latest updates.")

    @bot.command(name='setupchode')
    @commands.has_permissions(administrator=True)
    async def setup_chode(ctx):
        """Initiates the configuration process for Chode."""
        guild = ctx.guild
        if not guild:
            await send_long_message(ctx.channel, "Configuration can only be done within a server.")
            logging.warning("Configuration attempted in DM.")
            return

        guild_id = str(guild.id)

        # Step 1: Describe Chode's function and personality
        try:
            await ctx.send("Let's configure Chode! First, please describe Chode's function and personality (e.g., programmer, gamer friend, science expert, etc.):")

            def check_use(m):
                return m.author == ctx.author and m.channel == ctx.channel

            use_msg = await bot.wait_for('message', check=check_use, timeout=300)
            chode_description = use_msg.content.strip()

            # Step 2: Enter current time to determine server's time zone
            await ctx.send("Please enter the current time in your location in the format `HH:MM` (24-hour format). For example, `14:30` for 2:30 PM.")

            def check_time(m):
                return m.author == ctx.author and m.channel == ctx.channel

            time_msg = await bot.wait_for('message', check=check_time, timeout=120)
            user_time_str = time_msg.content.strip()

            # Validate time format
            try:
                user_time = datetime.strptime(user_time_str, "%H:%M")
                user_timezone = "Local Time"
                logging.debug(f"User time entered: {user_time_str}, assumed timezone: {user_timezone}")
            except ValueError:
                await ctx.send("Invalid time format. Please use `HH:MM` in 24-hour format. Configuration aborted.")
                logging.warning(f"Configuration aborted due to invalid time format by {ctx.author.display_name}")
                return

            # Step 3: Special instructions
            await ctx.send("Please provide any special instructions (e.g., AI). If none, type `none`.")

            def check_instructions(m):
                return m.author == ctx.author and m.channel == ctx.channel

            instructions_msg = await bot.wait_for('message', check=check_instructions, timeout=300)
            special_instructions = instructions_msg.content.strip()

            # Step 4: Set Operating Hours
            await ctx.send("Please specify the operating hours for Chode in the format `HH:MM-HH:MM` (24-hour format, local time). For example, `09:00-17:00`.")

            def check_hours(m):
                return m.author == ctx.author and m.channel == ctx.channel

            hours_msg = await bot.wait_for('message', check=check_hours, timeout=120)
            operating_hours = hours_msg.content.strip()

            # Validate operating hours format
            try:
                start_str, end_str = operating_hours.split('-')
                start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
                end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
                logging.debug(f"Parsed operating hours: Start - {start_time}, End - {end_time}")
            except ValueError:
                await ctx.send("Invalid time format for operating hours. Please use `HH:MM-HH:MM` in 24-hour format. Configuration aborted.")
                logging.warning(f"Configuration aborted due to invalid operating hours format by {ctx.author.display_name}")
                return

            # Save configuration
            configurations[guild_id] = {
                'description': chode_description,
                'timezone': user_timezone,
                'special_instructions': special_instructions,
                'operating_hours': operating_hours,
                'personality': chode_description
            }
            save_configurations(configurations)

            try:
                await ctx.send("Configuration complete! Chode is now set up and ready to use.")
                logging.info(f"Configured guild {guild.name} ({guild_id}) with description: {chode_description}, timezone: {user_timezone}, instructions: {special_instructions}, operating_hours: {operating_hours}")
            except Exception as e:
                logging.error(f"Failed to send configuration completion message: {str(e)}")

        except asyncio.TimeoutError:
            try:
                await ctx.send("Configuration timed out. Please try again later.")
                logging.warning(f"Configuration timed out for guild {guild.name}")
            except Exception as e:
                logging.error(f"Failed to send timeout message: {str(e)}")
        except Exception as e:
            logging.error(f"Error during configuration: {str(e)}")
            try:
                await ctx.send("An error occurred during configuration. Please try again later.")
            except Exception as e2:
                logging.error(f"Failed to send generic configuration error message: {str(e2)}")

    @bot.command(name='genimg')
    async def genimg(ctx, *, prompt: str):
        """
        Generates an image based on the provided prompt using ComfyUI.
        Usage: !!genimg <your prompt here>
        """
        await ctx.send(f"�️ Generating image for prompt: `{prompt}`. This may take a moment...")

        server_address = COMFYUI_SERVER_ADDRESS
        server_port = COMFYUI_SERVER_PORT
        client_id = str(uuid.uuid4())

        async def queue_prompt(session, prompt_text):
            url = f"http://{server_address}:{server_port}/prompt"
            payload = {
                "prompt": prompt_text,
                "client_id": client_id
            }
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    raise Exception(f"Failed to queue prompt: {response.status} {response.reason}")
                return await response.json()

        async def get_history(session, prompt_id):
            url = f"http://{server_address}:{server_port}/history/{prompt_id}"
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get history: {response.status} {response.reason}")
                return await response.json()

        async def get_image(session, filename, subfolder, folder_type):
            url = f"http://{server_address}:{server_port}/view"
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type
            }
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get image: {response.status} {response.reason}")
                return await response.read()

        try:
            async with aiohttp.ClientSession() as session:
                # Queue the prompt
                queue_response = await queue_prompt(session, prompt)
                prompt_id = queue_response.get('prompt_id')
                if not prompt_id:
                    await ctx.send("❌ Failed to queue the prompt. Please try again later.")
                    logging.error("No prompt_id returned from ComfyUI.")
                    return

                # Connect to WebSocket
                ws_url = f"ws://{server_address}:{server_port}/ws?clientId={client_id}"
                async with websockets.connect(ws_url) as websocket:
                    logging.info(f"Connected to ComfyUI WebSocket at {ws_url}")

                    # Listen for messages until execution is done
                    while True:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=300)  # 5 minutes timeout
                            if isinstance(message, str):
                                msg_json = json.loads(message)
                                if msg_json.get('type') == 'executing' and msg_json.get('data', {}).get('prompt_id') == prompt_id:
                                    node = msg_json['data'].get('node')
                                    if node is None:
                                        logging.info("Image generation completed.")
                                        break  # Execution done
                        except asyncio.TimeoutError:
                            await ctx.send("⏰ Image generation timed out. Please try again.")
                            logging.warning("WebSocket listening timed out.")
                            return
                        except websockets.exceptions.ConnectionClosed:
                            logging.warning("WebSocket connection closed unexpectedly.")
                            break

                # Retrieve history
                history = await get_history(session, prompt_id)
                outputs = history.get(prompt_id, {}).get('outputs', {})

                # Fetch images
                images = []
                for node_id, node_output in outputs.items():
                    if 'images' in node_output:
                        for image_info in node_output['images']:
                            image_data = await get_image(session, image_info['filename'], image_info['subfolder'], image_info['type'])
                            image = Image.open(io.BytesIO(image_data))
                            # Save image to a BytesIO object
                            img_byte_arr = io.BytesIO()
                            image.save(img_byte_arr, format='PNG')
                            img_byte_arr.seek(0)
                            images.append(img_byte_arr)

                if not images:
                    await ctx.send("❌ No images were generated. Please check the prompt and try again.")
                    logging.warning("No images found in ComfyUI history.")
                    return

                # Send images to Discord
                for idx, img in enumerate(images, start=1):
                    file = discord.File(fp=img, filename=f"generated_image_{idx}.png")
                    await ctx.send(file=file)
                    logging.info(f"Sent generated_image_{idx}.png to {ctx.guild.name} in channel {ctx.channel.name}")

        except Exception as e:
            logging.error(f"Error in genimg command: {str(e)}")
            await ctx.send(f"❌ An error occurred while generating the image: {str(e)}")

