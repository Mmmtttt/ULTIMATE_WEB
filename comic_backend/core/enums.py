from enum import Enum


class ResultCode(Enum):
    SUCCESS = 200
    BAD_REQUEST = 400
    NOT_FOUND = 404
    INTERNAL_ERROR = 500


class PageMode(Enum):
    LEFT_RIGHT = "left_right"
    UP_DOWN = "up_down"


class BackgroundColor(Enum):
    WHITE = "white"
    BLACK = "black"
    SEPIA = "sepia"


class ImageSource(Enum):
    LOCAL = "local"
    IMAGE_HOST = "image_host"


class ImportType(Enum):
    SCRIPT = "script"
    DIRECTORY = "directory"
    ZIP = "zip"
    IMAGE_HOST = "image_host"
