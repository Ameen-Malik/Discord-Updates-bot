from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from models import Base, Mentee, Response
from datetime import datetime
import pandas as pd

class DatabaseManager:
    def __init__(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///mentor_bot.db')
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def add_mentee(self, name: str, discord_id: str):
        async with self.async_session() as session:
            mentee = Mentee(name=name, discord_id=discord_id)
            session.add(mentee)
            await session.commit()
            return mentee

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
            mentee = await self.get_mentee_by_discord_id(discord_id)
            if not mentee:
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

    async def get_responses_by_discord_id(self, discord_id: str):
        async with self.async_session() as session:
            result = await session.execute(
                select(Response)
                .join(Mentee)
                .where(Mentee.discord_id == discord_id)
                .order_by(Response.created_at.desc())
            )
            return result.scalars().all()

    async def get_responses_by_name(self, name: str):
        async with self.async_session() as session:
            result = await session.execute(
                select(Response)
                .join(Mentee)
                .where(Mentee.name == name)
                .order_by(Response.created_at.desc())
            )
            return result.scalars().all()

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