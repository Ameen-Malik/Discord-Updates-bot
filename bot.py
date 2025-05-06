import os
import discord
from discord.ext import commands, tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from database import DatabaseManager

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.dm_messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
db = DatabaseManager()
scheduler = AsyncIOScheduler()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await db.init_db()
    scheduler.start()

@bot.command()
@commands.has_permissions(administrator=True)
async def load_mentees(ctx, file: discord.Attachment):
    """Load mentees from a CSV file"""
    if not file.filename.endswith('.csv'):
        await ctx.send("Please provide a CSV file")
        return

    await file.save('temp_mentees.csv')
    df = pd.read_csv('temp_mentees.csv')
    
    for _, row in df.iterrows():
        await db.add_mentee(row['name'], str(row['discord_id']))
    
    os.remove('temp_mentees.csv')
    await ctx.send(f"Successfully loaded {len(df)} mentees")

# @bot.command()
# @commands.has_permissions(administrator=True)
# async def start_reminders(ctx):
#     """Start sending weekly reminders"""
#     scheduler.add_job(send_weekly_reminders, 'cron', day_of_week='tue', hour=16)
#     await ctx.send("Weekly reminders scheduled for every Monday at 10 AM")
@bot.command()
@commands.has_permissions(administrator=True)
async def start_reminders(ctx, hour: int, minute: int):
    """Start sending weekly reminders at a custom time (24-hour format)"""
    # Remove existing job if any to avoid duplicates
    scheduler.remove_all_jobs()
    
    # Schedule the job at the specified hour and minute every Tuesday
    scheduler.add_job(send_weekly_reminders, 'cron', day_of_week='tue', hour=hour, minute=minute)
    
    await ctx.send(f"Weekly reminders scheduled for every Tuesday at {hour:02d}:{minute:02d}")


async def send_weekly_reminders():
    mentees = await db.get_all_mentees()
    for mentee in mentees:
        try:
            user = await bot.fetch_user(int(mentee.discord_id))
            await user.send(
                "Hi! Please provide your weekly update:\n"
                "1. What progress have you made this week?\n"
                "2. Are you facing any blockers?\n"
                "3. What are your plans for next week?\n\n"
                "You can respond with text or a voice message."
            )
        except Exception as e:
            print(f"Failed to send reminder to {mentee.name}: {e}")

@bot.event
async def on_message(message):
    if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
        # Handle text response
        if message.content:
            await db.add_response(
                str(message.author.id),
                text_response=message.content
            )
            await message.channel.send("Thank you for your text response!")

        # Handle voice message
        for attachment in message.attachments:
            if attachment.content_type and 'audio' in attachment.content_type:
                await db.add_response(
                    str(message.author.id),
                    voice_response_url=attachment.url
                )
                await message.channel.send("Thank you for your voice response!")

    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def get_responses(ctx, identifier: str):
    """Get responses by mentee name or Discord ID"""
    # Try to get responses by Discord ID first
    responses = await db.get_responses_by_discord_id(identifier)
    
    # If no responses found, try by name
    if not responses:
        responses = await db.get_responses_by_name(identifier)
    
    if not responses:
        await ctx.send(f"No responses found for {identifier}")
        return

    # Create a formatted message
    message = f"Responses for {identifier}:\n\n"
    for response in responses:
        message += f"Week {response.week_number}:\n"
        if response.text_response:
            message += f"Text: {response.text_response}\n"
        if response.voice_response_url:
            message += f"Voice: {response.voice_response_url}\n"
        message += f"Date: {response.created_at}\n\n"

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
    await db.export_responses_to_csv(filename)
    await ctx.send("Responses exported successfully!", file=discord.File(filename))
    os.remove(filename)

# Run the bot
bot.run(TOKEN) 