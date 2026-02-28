class AppException(Exception):
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotFoundException(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, 404)


class ValidationException(AppException):
    def __init__(self, message: str = "参数验证失败"):
        super().__init__(message, 400)


class PersistenceException(AppException):
    def __init__(self, message: str = "数据持久化失败"):
        super().__init__(message, 500)


class ImportException(AppException):
    def __init__(self, message: str = "导入失败"):
        super().__init__(message, 400)
