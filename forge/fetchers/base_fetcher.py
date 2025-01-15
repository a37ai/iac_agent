"""
Base class for documentation fetchers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict

class BaseFetcher(ABC):
    def __init__(self, api_url: str = None, auth_token: str = None, **kwargs):
        """Initialize fetcher with configuration"""
        self.api_url = api_url
        self.auth_token = auth_token
        self.config = kwargs
    
    @abstractmethod
    async def fetch_documentation(self) -> List[Dict]:
        """Fetch documentation from the tool's source"""
        raise NotImplementedError("Subclasses must implement fetch_documentation")
    
    @abstractmethod
    async def get_current_version(self) -> str:
        """Get the current version of the tool"""
        pass
