from typing import Any, List, Optional


class Validator:
    @staticmethod
    def not_empty(value: Any, field_name: str) -> Optional[str]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return f"{field_name}不能为空"
        return None
    
    @staticmethod
    def in_list(value: Any, valid_values: List[Any], field_name: str) -> Optional[str]:
        if value not in valid_values:
            return f"{field_name}必须是{valid_values}之一"
        return None
    
    @staticmethod
    def is_list(value: Any, field_name: str) -> Optional[str]:
        if not isinstance(value, list):
            return f"{field_name}必须是数组"
        return None
    
    @staticmethod
    def is_non_empty_list(value: Any, field_name: str) -> Optional[str]:
        if not isinstance(value, list) or len(value) == 0:
            return f"{field_name}必须是非空数组"
        return None
    
    @staticmethod
    def in_range(value: Any, min_val: Any, max_val: Any, field_name: str) -> Optional[str]:
        if value < min_val or value > max_val:
            return f"{field_name}范围{min_val}-{max_val}"
        return None
