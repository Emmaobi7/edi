from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SegmentNLP(Base):
    __tablename__ = 'segmentnlp'
    
    id = Column(Integer, primary_key=True)
    agency = Column(String(10))
    version = Column(String(20))
    transactionid = Column(String(50))  # transaction set ID
    segment_id = Column(String(10))
    description = Column(Text)
    release = Column(Integer, default=0)

class ElementUsageDefs(Base):
    __tablename__ = 'elementusagedefs'
    
    id = Column(Integer, primary_key=True)
    agency = Column(String(10))
    version = Column(String(20))
    segment_id = Column(String(10))
    description = Column(Text)
    requirement_designator = Column(String(10))
    position = Column(Integer)
    release = Column(Integer, default=0) 