import logging
import os
from logging.handlers import RotatingFileHandler
from core.constants import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

app_logger = logging.getLogger('app')
app_logger.setLevel(logging.INFO)

error_logger = logging.getLogger('error')
error_logger.setLevel(logging.ERROR)

access_logger = logging.getLogger('access')
access_logger.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s')

MAX_LOG_SIZE = 100 * 1024
BACKUP_COUNT = 20

app_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, 'app.log'),
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding='utf-8'
)
app_handler.setFormatter(formatter)

access_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, 'access.log'),
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding='utf-8'
)
access_handler.setFormatter(formatter)

error_handler = RotatingFileHandler(
    os.path.join(LOGS_DIR, 'error.log'),
    maxBytes=MAX_LOG_SIZE,
    backupCount=0,
    encoding='utf-8'
)
error_handler.setFormatter(formatter)

app_logger.addHandler(app_handler)
error_logger.addHandler(error_handler)
access_logger.addHandler(access_handler)
