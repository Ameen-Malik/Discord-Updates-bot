import os
import discord
from discord.ext import commands, tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
# Ensure DatabaseManager is imported
from database import DatabaseManager
import aiohttp
from aiohttp import web
import asyncio

# Load environment variables
load_dotenv()

# Get token from environment variable
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise ValueError("No Discord token found. Please set DISCORD_TOKEN environment variable.")

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.dm_messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
db = DatabaseManager()
scheduler = AsyncIOScheduler()

# Create aiohttp app for health check
app = web.Application()

async def health_check(request):
    return web.Response(text="Bot is running!")

app.router.add_get('/health', health_check)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        await db.init_db()
        scheduler.start()
        print("Database initialized and bot started successfully")
    except Exception as e:
        print(f"Error during initialization: {e}")
        raise

@bot.command()
@commands.has_permissions(administrator=True)
async def load_mentees(ctx, file: discord.Attachment):
    """Load mentees from a CSV file, skipping existing ones"""
    if not file.filename.endswith('.csv'):
        await ctx.send("Please provide a CSV file")
        return

    await file.save('temp_mentees.csv')
    try:
        df = pd.read_csv('temp_mentees.csv')

        added_count = 0
        skipped_count = 0
        total_rows = len(df)

        if 'name' not in df.columns or 'discord_id' not in df.columns:
             await ctx.send("CSV must contain 'name' and 'discord_id' columns.")
             return

        # Convert discord_id to string type to handle potential large integer issues
        df['discord_id'] = df['discord_id'].astype(str)

        message = await ctx.send(f"Processing {total_rows} rows from CSV...")

        for index, row in df.iterrows():
            # find_or_add_mentee returns (mentee_object, was_added_boolean)
            mentee, was_added = await db.find_or_add_mentee(row['name'], row['discord_id'])
            if was_added:
                added_count += 1
            else:
                skipped_count += 1
            # Optional: Update message periodically for long CSVs
            if (index + 1) % 10 == 0 or (index + 1) == total_rows:
                 # Use edit to update the previous message instead of sending new ones
                 await message.edit(content=f"Processed {index + 1}/{total_rows} rows. Added: {added_count}, Skipped: {skipped_count}")


        os.remove('temp_mentees.csv')
        # Final message update
        await message.edit(content=f"Finished loading mentees. Added {added_count}, skipped {skipped_count} (already existed).")


    except Exception as e:
        await ctx.send(f"An error occurred while processing the CSV: {e}")
        # Clean up temp file even if error occurs
        if os.path.exists('temp_mentees.csv'):
             os.remove('temp_mentees.csv')


# ... rest of the bot.py code remains the same ...

@bot.command()
@commands.has_permissions(administrator=True)
async def start_reminders(ctx, day: str, hour: int, minute: int):
    """Start sending weekly reminders at a custom time (24-hour format)
    day: Day of the week (sun, mon, tue, wed, thu, fri, sat)
    hour: Hour in 24-hour format (0-23)
    minute: Minute (0-59)
    """
    # Validate day input
    valid_days = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat']
    day = day.lower()
    if day not in valid_days:
        await ctx.send(f"Invalid day. Please use one of: {', '.join(valid_days)}")
        return

    # Validate time inputs
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        await ctx.send("Invalid time. Hour must be 0-23 and minute must be 0-59")
        return

    scheduler.remove_all_jobs() # Remove existing job if any to avoid duplicates
    # Schedule the job at the specified day, hour and minute
    scheduler.add_job(send_weekly_reminders, 'cron', day_of_week=day, hour=hour, minute=minute)
    await ctx.send(f"Weekly reminders scheduled for every {day.capitalize()} at {hour:02d}:{minute:02d}")


async def send_weekly_reminders():
    mentees = await db.get_all_mentees()
    for mentee in mentees:
        try:
            # Use fetch_user as you need the User object for DMs
            user = await bot.fetch_user(int(mentee.discord_id))
            
            await user.send(
                "Hi! I’m the **100x Update Buddy**, here to collect your weekly check-in 📝\n\n"
                "Your responses are reviewed by the 100x team and help us personalize your experience during Office Hour sessions and beyond.\n\n"
                "1. **This week’s progress** – What did you work on and accomplish?\n"
                "2. **Any blockers** – Are you facing any challenges we should be aware of or help you with?\n"
                "3. **Next week’s focus** – What are your key priorities for the coming week?\n\n"
                "Please make sure to reply with your update as soon as you can - latest by Sunday EoD. Looking forward to your update 🙂!"
            )
        except Exception as e:
            print(f"Failed to send reminder to {mentee.name} ({mentee.discord_id}): {e}")


@bot.event
async def on_message(message):
    if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
        author_id_str = str(message.author.id) # Get author ID as string

        # Handle text response
        if message.content:
            # add_response finds the mentee within its own session
            response = await db.add_response(author_id_str, text_response=message.content)
            if response: # Check if response was successfully added (mentee found)
                 await message.channel.send("Thank you for your text response!")
            # else: Mentee not found, maybe send a message back? Or just ignore.

        # Handle voice message
        # Iterate through attachments regardless of text content
        for attachment in message.attachments:
            # Check if attachment content type is audio
            if attachment.content_type and 'audio' in attachment.content_type:
                # add_response finds the mentee within its own session
                response = await db.add_response(author_id_str, voice_response_url=attachment.url)
                if response: # Check if response was successfully added (mentee found)
                    await message.channel.send("Thank you for your voice response!")
                # else: Mentee not found, maybe send a message back? Or just ignore.


    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def get_responses(ctx, identifier: str):
    """Get responses by mentee name or Discord ID"""
    # Ensure identifier is treated as a string for database lookup
    identifier_str = str(identifier).strip() # Also strip whitespace

    # Try to get responses by Discord ID first (this method now eager loads mentee)
    responses = await db.get_responses_by_discord_id(identifier_str)

    # If no responses found AND the identifier wasn't a valid Discord ID format (optional check),
    # OR if the identifier was an ID but yielded no responses, try by name.
    # Simpler logic: Just try by name if no responses found by ID.
    if not responses:
        # get_responses_by_name now also eager loads mentee and handles mentee not found
        responses = await db.get_responses_by_name(identifier_str)


    if not responses:
        await ctx.send(f"No responses or mentee found for '{identifier}'")
        return

    # Create a formatted message
    # Access the eagerly loaded mentee directly from the first response
    first_response = responses[0]
    mentee = first_response.mentee # This is now loaded and accessible

    # Use the mentee's actual name and ID for the header
    header_identifier = mentee.name if mentee else identifier_str # Use name if mentee object is valid, else input
    header_discord_id = mentee.discord_id if mentee else "Unknown" # Use ID if mentee object is valid

    message = f"Responses for {header_identifier} ({header_discord_id}):\n\n"
    for response in responses:
        # Access mentee through the relationship, which is now loaded
        mentee = response.mentee # It's already there!
        message += f"Week {response.week_number}:\n"
        if response.text_response:
            message += f"Text: {response.text_response}\n"
        if response.voice_response_url:
            message += f"Voice: {response.voice_response_url}\n"
        message += f"Date: {response.created_at.strftime('%Y-%m-%d %H:%M UTC')}\n\n" # Format date for readability

    # Split message if too long
    if len(message) > 2000:
        chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
        for chunk in chunks:
            await ctx.send(chunk)
    else:
        await ctx.send(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def export_responses(ctx):
    """Export all responses to a CSV file"""
    filename = f"responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        # export_responses_to_csv now returns the filename path
        exported_filepath = await db.export_responses_to_csv(filename)
        await ctx.send("Responses exported successfully!", file=discord.File(exported_filepath))
    except Exception as e:
        await ctx.send(f"An error occurred during export: {e}")
        # Clean up temporary file even if sending fails
    finally:
         # Ensure file is removed even if sending fails
         if os.path.exists(filename):
              os.remove(filename)


# Run the bot with error handling
if __name__ == "__main__":
    try:
        # Start the web server
        runner = web.AppRunner(app)
        asyncio.get_event_loop().run_until_complete(runner.setup())
        site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 8080)))
        asyncio.get_event_loop().run_until_complete(site.start())
        
        # Start the bot
        bot.run(TOKEN)
    except Exception as e:
        print(f"Error running bot: {e}")
        raise
