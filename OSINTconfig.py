import os
from pathlib import Path

def loadSecretKey():
    if os.path.isfile("./secret.key"):
        return Path("./secret.key").read_text()
    else:
        currentSecretKey = secrets.token_urlsafe(256)
        with os.fdopen(os.open(Path("./secret.key"), os.O_WRONLY | os.O_CREAT, 0o400), 'w') as file:
            file.write(currentSecretKey)
        return currentSecretKey


class Config(object):
    DB_FILE_PATH = os.environ.get("DB_FILE_PATH") or "./osinter_users.db"
    DB_USER_TABLE = os.environ.get('DB_USER_TABLE') or "users"
    ELASTICSEARCH_ARTICLE_INDEX = os.environ.get("ARTICLE_INDEX") or "osinter_articles"
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL') or "http://localhost:9200"
    SECRET_KEY = os.environ.get('SECRET_KEY') or loadSecretKey()
