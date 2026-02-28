import logging
import os
from core.constants import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

app_logger = logging.getLogger('app')
app_logger.setLevel(logging.INFO)

error_logger = logging.getLogger('error')
error_logger.setLevel(logging.ERROR)

access_logger = logging.getLogger('access')
access_logger.setLevel(logging.INFO)

app_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'app.log'), encoding='utf-8')
error_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'error.log'), encoding='utf-8')
access_handler = logging.FileHandler(os.path.join(LOGS_DIR, 'access.log'), encoding='utf-8')

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s')
app_handler.setFormatter(formatter)
error_handler.setFormatter(formatter)
access_handler.setFormatter(formatter)

app_logger.addHandler(app_handler)
error_logger.addHandler(error_handler)
access_logger.addHandler(access_handler)
