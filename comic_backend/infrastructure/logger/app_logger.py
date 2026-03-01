import logging
import os
import sys
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

class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = self.rotation_filename("%s.%d" % (self.baseFilename, i))
                dfn = self.rotation_filename("%s.%d" % (self.baseFilename, i + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        try:
                            os.remove(dfn)
                        except (OSError, PermissionError):
                            pass
                    try:
                        os.rename(sfn, dfn)
                    except (OSError, PermissionError):
                        pass
            dfn = self.rotation_filename(self.baseFilename + ".1")
            if os.path.exists(dfn):
                try:
                    os.remove(dfn)
                except (OSError, PermissionError):
                    pass
            try:
                os.rename(self.baseFilename, dfn)
            except (OSError, PermissionError):
                pass
        if not self.delay:
            self.stream = self._open()

app_handler = WindowsSafeRotatingFileHandler(
    os.path.join(LOGS_DIR, 'app.log'),
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding='utf-8'
)
app_handler.setFormatter(formatter)

access_handler = WindowsSafeRotatingFileHandler(
    os.path.join(LOGS_DIR, 'access.log'),
    maxBytes=MAX_LOG_SIZE,
    backupCount=BACKUP_COUNT,
    encoding='utf-8'
)
access_handler.setFormatter(formatter)

error_handler = WindowsSafeRotatingFileHandler(
    os.path.join(LOGS_DIR, 'error.log'),
    maxBytes=MAX_LOG_SIZE,
    backupCount=0,
    encoding='utf-8'
)
error_handler.setFormatter(formatter)

app_logger.addHandler(app_handler)
error_logger.addHandler(error_handler)
access_logger.addHandler(access_handler)
