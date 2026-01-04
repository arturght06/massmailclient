import time
from sqlalchemy.exc import OperationalError
import os
from models import Base, engine


def wait_for_db():
    retries = 30
    while retries > 0:
        try:
            with engine.connect() as conn:
                return
        except OperationalError:
            print("MySQL not ready... waiting 2s")
            time.sleep(2)
            retries -= 1
    raise Exception("Could not connect to MySQL database after several attempts")

def init_db():
    print("Checking database connection...")
    wait_for_db()
    
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()