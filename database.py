import os 
from dotenv import load_dotenv 

from sqlalchemy.orm import sessionmaker, joinedload
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError # Import IntegrityError if you wanted to catch it explicitly, but 'find or add' avoids it
from models import Base, Mentee, Response
from datetime import datetime
import pandas as pd

load_dotenv()

class DatabaseManager:
    def __init__(self):
        # Read credentials from environment variables
        # db_host = os.getenv('SUPABASE_DB_HOST')
        # db_port = os.getenv('SUPABASE_DB_PORT')
        # db_name = os.getenv('SUPABASE_DB_NAME')
        # db_user = os.getenv('SUPABASE_DB_USER')
        # db_password = os.getenv('SUPABASE_DB_PASSWORD')

        
        # Format: postgresql+asyncpg://user:password@host:port/database
        # Using the connection pooler address is often recommended by Supabase
        DATABASE_URL = os.getenv('DATABASE_URL').replace('postgresql://', 'postgresql+asyncpg://')

        # Update the engine creation to use the new URL and asyncpg driver
        self.engine = create_async_engine(DATABASE_URL) 
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


# class DatabaseManager:
#     def __init__(self):
#         self.engine = create_async_engine('sqlite+aiosqlite:///mentor_bot.db')
#         self.async_session = sessionmaker(
#             self.engine, class_=AsyncSession, expire_on_commit=False
#         )

#     async def init_db(self):
#         async with self.engine.begin() as conn:
#             await conn.run_sync(Base.metadata.create_all)

    # Renamed/Modified method to find or add mentee
    async def find_or_add_mentee(self, name: str, discord_id: str):
        async with self.async_session() as session:
            # 1. Try to find the mentee by discord_id first
            existing_mentee = await self.get_mentee_by_discord_id(discord_id)

            if existing_mentee:
                # If mentee exists, return the existing one and indicate it wasn't added
                # We could also update the name here if desired, but the request is just to skip
                print(f"Mentee with Discord ID {discord_id} ({existing_mentee.name}) already exists. Skipping addition.")
                return existing_mentee, False # Return existing mentee and False (not added)
            else:
                # If mentee does not exist, create and add a new one
                mentee = Mentee(name=name, discord_id=discord_id)
                session.add(mentee)
                await session.commit()
                print(f"Added new mentee: {name} ({discord_id})")
                return mentee, True # Return new mentee and True (added)

    async def get_mentee_by_discord_id(self, discord_id: str):
        async with self.async_session() as session:
            result = await session.execute(
                select(Mentee).where(Mentee.discord_id == discord_id)
            )
            return result.scalar_one_or_none()

    async def get_mentee_by_name(self, name: str):
        async with self.async_session() as session:
            result = await session.execute(
                select(Mentee).where(Mentee.name == name)
            )
            return result.scalar_one_or_none()

    async def add_response(self, discord_id: str, text_response: str = None, voice_response_url: str = None):
        async with self.async_session() as session:
            # Need to find the mentee to link the response
            mentee = await self.get_mentee_by_discord_id(discord_id)
            if not mentee:
                # This case shouldn't ideally happen if only registered mentees interact,
                # but it's good practice to handle it.
                print(f"Received response from unknown Discord ID: {discord_id}")
                return None

            week_number = datetime.utcnow().isocalendar()[1]
            response = Response(
                mentee_id=mentee.id,
                week_number=week_number,
                text_response=text_response,
                voice_response_url=voice_response_url
            )
            session.add(response)
            await session.commit()
            return response

    # async def get_responses_by_discord_id(self, discord_id: str):
    #     async with self.async_session() as session:
    #         result = await session.execute(
    #             select(Response)
    #             .join(Mentee)
    #             .where(Mentee.discord_id == discord_id)
    #             .order_by(Response.created_at.desc())
    #         )
    #         return result.scalars().all()
    async def get_responses_by_discord_id(self, discord_id: str):
        async with self.async_session() as session:
            result = await session.execute(
                select(Response)
                .join(Mentee)
                .where(Mentee.discord_id == discord_id)
                .options(joinedload(Response.mentee)) # <--- Eager load the mentee relationship
                .order_by(Response.created_at.desc())
            )
            return result.scalars().all() # These Response objects will have their mentee attribute populated

    # async def get_responses_by_name(self, name: str):
    #     async with self.async_session() as session:
    #         result = await session.execute(
    #             select(Response)
    #             .join(Mentee)
    #             .where(Mentee.name == name)
    #             .order_by(Response.created_at.desc())
    #         )
    #         return result.scalars().all()

    async def get_responses_by_name(self, name: str):
        async with self.async_session() as session:
             # First find the mentee by name to get their ID
             mentee_result = await session.execute(
                 select(Mentee).where(Mentee.name == name)
             )
             mentee = mentee_result.scalar_one_or_none()

             if not mentee:
                 return [] # Return empty list if mentee not found

             # Then get responses using the found mentee's ID, eagerly loading mentee
             response_result = await session.execute(
                 select(Response)
                 .join(Mentee)
                 .where(Response.mentee_id == mentee.id) # Filter by mentee_id
                 .options(joinedload(Response.mentee)) # <--- Eager load the mentee relationship
                 .order_by(Response.created_at.desc())
             )
             return response_result.scalars().all() # These Response objects will have their mentee attribute populated

    async def get_all_mentees(self):
        async with self.async_session() as session:
            result = await session.execute(select(Mentee))
            return result.scalars().all()

    async def export_responses_to_csv(self, filename: str):
        async with self.async_session() as session:
            result = await session.execute(
                select(Response, Mentee)
                .join(Mentee)
                .order_by(Response.created_at.desc())
            )
            responses = result.all()

            data = []
            for response, mentee in responses:
                data.append({
                    'Week': response.week_number,
                    'Mentee Name': mentee.name,
                    'Discord ID': mentee.discord_id,
                    'Text Response': response.text_response,
                    'Voice Response URL': response.voice_response_url,
                    'Created At': response.created_at
                })

            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            return filename