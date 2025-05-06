from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Mentee(Base):
    __tablename__ = 'mentees'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    discord_id = Column(String(20), unique=True, nullable=False)
    responses = relationship("Response", back_populates="mentee")

class Response(Base):
    __tablename__ = 'responses'
    
    id = Column(Integer, primary_key=True)
    mentee_id = Column(Integer, ForeignKey('mentees.id'))
    week_number = Column(Integer, nullable=False)
    text_response = Column(Text)
    voice_response_url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    mentee = relationship("Mentee", back_populates="responses")

def init_db():
    engine = create_engine('sqlite:///mentor_bot.db')
    Base.metadata.create_all(engine)
    return engine 