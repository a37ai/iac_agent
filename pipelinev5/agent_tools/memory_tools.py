import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging
from pathlib import Path
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from states.state import Memory, MemoryContext
from utils.general_helper_functions import configure_logger

logger = configure_logger(__name__)

class MemoryTools:
    def __init__(self):
        pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
        self.index_name = "forge"
        self.index = pc.Index(self.index_name)
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=1536
        )

    def store_memories(self, memories: List[Memory]) -> None:
        vectors = []
        for memory in memories:
            memory_str = json.dumps(memory.dict())
            embedding = self.embeddings.embed_query(memory_str)
            vector_id = f"{memory.repo_path}_{memory.type}_{datetime.now().timestamp()}"
            
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": memory.dict()
            })
        
        self.index.upsert(vectors=vectors)
        logger.info(f"Stored {len(vectors)} memories")

    def query_memories(self, repo_url: str, k: int = 1000) -> MemoryContext:
        query_embedding = self.embeddings.embed_query(repo_url)
        
        results = self.index.query(
            vector=query_embedding,
            top_k=k,
            include_metadata=True
        )

        if not results.matches:
            return MemoryContext()

        # Group memories by type
        file_analyses = {}
        overview = None
        latest_timestamp = None

        for match in results.matches:
            metadata = match.metadata
            if not latest_timestamp or metadata["timestamp"] > latest_timestamp:
                latest_timestamp = metadata["timestamp"]
                
            if metadata["type"] == "file_analysis":
                file_analyses[metadata["file_path"]] = json.loads(metadata["content"])
            elif metadata["type"] == "repo_overview":
                overview = metadata["content"]

        return MemoryContext(
            past_repo_url=repo_url if file_analyses or overview else None,
            last_accessed=latest_timestamp,
            past_analyses=file_analyses,
            past_overview=overview
        )