import os
from typing import List, Optional
from domain.author import AuthorSubscription, AuthorRepository
from infrastructure.persistence.json_storage import JsonStorage
from infrastructure.persistence.repositories.base_repository_impl import BaseCreatorJsonRepository
from infrastructure.logger import error_logger
from core.constants import AUTHOR_JSON_FILE
from core.utils import get_current_time, generate_id


class AuthorJsonRepository(AuthorRepository):
    def __init__(self, storage: JsonStorage = None):
        self._file_path = AUTHOR_JSON_FILE
        self._storage = storage or JsonStorage(self._file_path)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not os.path.exists(self._file_path):
            default_data = {
                "authors": [],
                "last_updated": get_current_time()
            }
            self._storage.write(default_data)
    
    def get_all(self) -> List[AuthorSubscription]:
        data = self._storage.read()
        authors = data.get("authors", [])
        return [AuthorSubscription.from_dict(a) for a in authors]
    
    def get_by_id(self, author_id: str) -> Optional[AuthorSubscription]:
        data = self._storage.read()
        authors = data.get("authors", [])
        author_data = next((a for a in authors if a["id"] == author_id), None)
        return AuthorSubscription.from_dict(author_data) if author_data else None
    
    def get_by_name(self, name: str) -> Optional[AuthorSubscription]:
        data = self._storage.read()
        authors = data.get("authors", [])
        author_data = next((a for a in authors if a.get("name") == name), None)
        return AuthorSubscription.from_dict(author_data) if author_data else None
    
    def save(self, author: AuthorSubscription) -> bool:
        try:
            data = self._storage.read()
            authors = data.get("authors", [])
            
            index = next((i for i, a in enumerate(authors) if a["id"] == author.id), -1)
            
            if index >= 0:
                authors[index] = author.to_dict()
            else:
                authors.append(author.to_dict())
            
            data["authors"] = authors
            data["last_updated"] = get_current_time()
            
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"保存作者订阅失败: {e}")
            return False
    
    def delete(self, author_id: str) -> bool:
        try:
            data = self._storage.read()
            authors = data.get("authors", [])
            authors = [a for a in authors if a["id"] != author_id]
            data["authors"] = authors
            data["last_updated"] = get_current_time()
            return self._storage.write(data)
        except Exception as e:
            error_logger.error(f"删除作者订阅失败: {e}")
            return False
    
    def exists_by_name(self, name: str) -> bool:
        data = self._storage.read()
        authors = data.get("authors", [])
        return any(a.get("name") == name for a in authors)
    
    def create(self, name: str) -> Optional[AuthorSubscription]:
        if self.exists_by_name(name):
            return None
        
        author = AuthorSubscription(
            id=generate_id("author"),
            name=name,
            subscribe_time=get_current_time()
        )
        
        if self.save(author):
            return author
        return None


class AuthorJsonRepositoryV2(BaseCreatorJsonRepository):
    _data_key = "authors"
    
    def __init__(self, storage: JsonStorage = None):
        self._file_path = AUTHOR_JSON_FILE
        self._storage = storage or JsonStorage(self._file_path)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not os.path.exists(self._file_path):
            default_data = {
                "authors": [],
                "last_updated": get_current_time()
            }
            self._storage.write(default_data)
    
    def _get_entity_class(self):
        return AuthorSubscription
    
    def create(self, name: str) -> Optional[AuthorSubscription]:
        if self.exists_by_name(name):
            return None
        
        author = AuthorSubscription(
            id=generate_id("author"),
            name=name,
            subscribe_time=get_current_time()
        )
        
        if self.save(author):
            return author
        return None
