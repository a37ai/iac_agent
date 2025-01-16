"""
RAG-based documentation retrieval system for DevOps tooling.
Provides fast, relevant documentation lookup for improved code generation.
"""
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
from dataclasses import dataclass, asdict
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
from tqdm import tqdm

@dataclass
class DocChunk:
    """Represents a chunk of documentation with metadata"""
    content: str
    tool_name: str
    category: str  # e.g., 'IaC', 'CI/CD', 'Observability'
    source: str
    embedding: Optional[np.ndarray] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        d = asdict(self)
        if self.embedding is not None:
            d['embedding'] = self.embedding.tolist()
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> 'DocChunk':
        """Create from dictionary"""
        if d['embedding'] is not None:
            d['embedding'] = np.array(d['embedding'])
        return cls(**d)

class DevOpsRetriever:
    def __init__(self, docs_dir: str = "docs", chunk_size: int = 512, chunk_overlap: int = 50):
        """Initialize the retriever with a directory of documentation"""
        self.docs_dir = Path(docs_dir)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast and lightweight
        self.doc_chunks: List[DocChunk] = []
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        
    def add_documentation(self, content: str, tool_name: str, category: str, source: str):
        """Add a new piece of documentation to the retriever"""
        # Split content into manageable chunks with overlap
        chunks = self._chunk_text(content)
        
        print(f"Processing {len(chunks)} chunks for {tool_name}...")
        for chunk in tqdm(chunks, desc="Generating embeddings"):
            doc_chunk = DocChunk(
                content=chunk,
                tool_name=tool_name,
                category=category,
                source=source
            )
            # Generate embedding
            with torch.no_grad():
                doc_chunk.embedding = self.model.encode(chunk, convert_to_tensor=True).cpu().numpy()
            self.doc_chunks.append(doc_chunk)
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap"""
        chunks = []
        sentences = text.split('\n')
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence.split())
            
            if current_size + sentence_size > self.chunk_size:
                # Add the current chunk if it's not empty
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    # Keep last few sentences for overlap
                    overlap_size = 0
                    overlap_chunk = []
                    for sent in reversed(current_chunk):
                        sent_size = len(sent.split())
                        if overlap_size + sent_size <= self.chunk_overlap:
                            overlap_chunk.insert(0, sent)
                            overlap_size += sent_size
                        else:
                            break
                    current_chunk = overlap_chunk
                    current_size = overlap_size
                
            current_chunk.append(sentence)
            current_size += sentence_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
            
        return chunks

    def retrieve(self, query: str, k: int = 3) -> List[Tuple[DocChunk, float]]:
        """Retrieve the k most relevant documentation chunks for a query"""
        if not self.doc_chunks:
            return []
            
        with torch.no_grad():
            query_embedding = self.model.encode(query, convert_to_tensor=True).cpu().numpy()
        
        # Calculate similarities using numpy for efficiency
        chunk_embeddings = np.stack([chunk.embedding for chunk in self.doc_chunks])
        similarities = np.dot(chunk_embeddings, query_embedding)
        
        # Get top k indices
        top_k_indices = np.argsort(similarities)[-k:][::-1]
        
        # Return chunks and their similarities
        return [(self.doc_chunks[i], float(similarities[i])) for i in top_k_indices]

    def save_index(self, path: str):
        """Save the current index to disk"""
        data = [chunk.to_dict() for chunk in self.doc_chunks]
        with open(path, 'w') as f:
            json.dump(data, f)

    def load_index(self, path: str):
        """Load an index from disk"""
        with open(path, 'r') as f:
            data = json.load(f)
            
        self.doc_chunks = [DocChunk.from_dict(d) for d in data]
