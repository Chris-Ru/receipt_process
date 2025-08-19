from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import sessionmaker

from db import get_Base

DATABASE_URL = 'sqlite:///receipts.db'


def get_session():
    engine = create_engine(DATABASE_URL)
    get_Base().metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
