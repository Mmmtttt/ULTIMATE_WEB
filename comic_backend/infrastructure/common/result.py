from typing import Generic, TypeVar, Optional
from core.enums import ResultCode

T = TypeVar('T')


class Result(Generic[T]):
    def __init__(
        self,
        code: ResultCode = ResultCode.SUCCESS,
        data: Optional[T] = None,
        message: str = "成功"
    ):
        self.code = code
        self.data = data
        self.message = message
    
    @property
    def is_success(self) -> bool:
        return self.code == ResultCode.SUCCESS
    
    @staticmethod
    def ok(data: T = None, message: str = "成功") -> "Result[T]":
        return Result(ResultCode.SUCCESS, data, message)
    
    @staticmethod
    def fail(message: str, code: ResultCode = ResultCode.BAD_REQUEST) -> "Result":
        return Result(code, None, message)
    
    def to_dict(self) -> dict:
        return {
            "code": self.code.value,
            "data": self.data,
            "message": self.message
        }


class ServiceResult:
    def __init__(self, success: bool, data=None, message: str = ""):
        self.success = success
        self.data = data
        self.message = message
    
    @staticmethod
    def ok(data=None, message: str = "操作成功") -> "ServiceResult":
        return ServiceResult(True, data, message)
    
    @staticmethod
    def error(message: str = "操作失败") -> "ServiceResult":
        return ServiceResult(False, None, message)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message
        }
