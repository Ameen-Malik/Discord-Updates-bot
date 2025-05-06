# Discord Mentor Bot

A Discord bot for managing weekly updates from mentees, supporting both text and voice responses.

## Features

- Weekly automated reminders to mentees
- Support for text and voice message responses
- SQLite database for storing responses
- Admin commands for managing mentees and viewing responses
- Export functionality for response history

## Setup

1. Create a Discord bot and get your token from the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a `.env` file in the project root with your bot token:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## CSV Format for Mentees

Create a CSV file with the following format:
```csv
name,discord_id
John Doe,123456789012345678
Jane Smith,234567890123456789
```

## Admin Commands

- `!load_mentees <csv_file>`: Load mentees from a CSV file
- `!start_reminders`: Start sending weekly reminders (Mondays at 10 AM)
- `!get_responses <identifier>`: Get responses by mentee name or Discord ID
- `!export_responses`: Export all responses to a CSV file

## Response Collection

- Mentees can respond to the bot's DMs with either text or voice messages
- Responses are automatically stored in the database
- Each response is tagged with the week number and timestamp

## Database

The bot uses SQLite for data storage. The database file (`mentor_bot.db`) will be created automatically when the bot starts.

## Security

- All admin commands require administrator permissions
- Bot token is stored in environment variables
- Database is local and not exposed to external access 