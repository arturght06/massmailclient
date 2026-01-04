from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, scoped_session
import os
from dotenv import load_dotenv


DATABASE_URL = os.getenv("DATABASE_URL", "mysql+mysqlconnector://user:user@localhost:3306/emails_db")

engine = create_engine(DATABASE_URL, pool_recycle=3600)

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

class Account(Base):
    __tablename__ = 'accounts'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    imap_server = Column(String(255), nullable=False)
    imap_port = Column(Integer, default=993)
    status = Column(String(50), default='unknown')
    notes = Column(Text, default='')
    proxy = Column(String(255), default='')

    emails = relationship("Email", back_populates="account", cascade="all, delete-orphan")

class Email(Base):
    __tablename__ = 'emails'

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'), nullable=False)
    imap_uid = Column(String(100))
    subject = Column(Text)
    sender = Column(String(255))
    body = Column(Text)
    date_str = Column(String(100))

    account = relationship("Account", back_populates="emails")

    __table_args__ = (UniqueConstraint('account_id', 'imap_uid', name='_account_uid_uc'),)