from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'
    item_id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey('receipts.id'))
    name = Column(String)
    quantity = Column(Integer)
    price = Column(Float)

    receipt = relationship("Receipt", back_populates="items")

class Receipt(Base):
    __tablename__ = 'receipts'
    id = Column(Integer, primary_key=True)
    store_name = Column(String)
    date = Column(String)
    time = Column(String)
    total = Column(Float)
    payment_method = Column(String)
    filepath = Column(String)

    items = relationship("Item", back_populates="receipt", cascade="all, delete-orphan")

def get_Base():
    return Base