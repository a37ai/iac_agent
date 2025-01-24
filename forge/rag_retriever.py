"""
RAG-based documentation retrieval system for DevOps tooling.
Provides fast, relevant documentation lookup for improved code generation.
"""
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import json
from dataclasses import dataclass, asdict
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
from tqdm import tqdm
import yaml
import re
from chromadb import Client, Settings
from chromadb.config import Settings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DocChunk:
    """A chunk of documentation with metadata"""
    content: str
    tool_name: str = "unknown"
    category: str = "unknown"
    source: Optional[str] = None
    version: Optional[str] = None
    topics: Optional[List[str]] = None
    error_patterns: Optional[List[str]] = None
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

class RAGRetriever:
    """Retriever for DevOps documentation using RAG"""
    
    def __init__(self, docs_dir: str = "docs"):
        """Initialize the retriever"""
        self.docs_dir = Path(docs_dir)
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize ChromaDB
        chroma_client = Client()
        self.collection = chroma_client.create_collection(
            name="devops_docs",
            metadata={"hnsw:space": "cosine"}
        )
        
    def ingest_documentation(self, directory: Optional[str] = None):
        """Ingest all documentation from the docs directory"""
        if directory is None:
            directory = self.docs_dir
        
        for path in Path(directory).rglob("*.md"):
            try:
                # Read the file and parse frontmatter
                content = path.read_text(encoding='utf-8')
                metadata, doc_content = self._parse_frontmatter(content)
                
                # Add to the collection
                self.add_documentation(
                    content=doc_content,
                    tool_name=metadata.get('tool', path.parent.name),
                    category=metadata.get('category', path.parent.parent.name),
                    source=str(path),
                    version=metadata.get('version'),
                    topics=metadata.get('topics', []),
                    error_patterns=self._extract_error_patterns(doc_content)
                )
                logger.info(f"Ingested documentation from {path}")
                
            except Exception as e:
                logger.error(f"Error ingesting {path}: {e}")
                
    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content"""
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if frontmatter_match:
            try:
                metadata = yaml.safe_load(frontmatter_match.group(1))
                content = frontmatter_match.group(2)
            except yaml.YAMLError:
                metadata = {}
        else:
            metadata = {}
        return metadata, content
        
    def _extract_error_patterns(self, content: str) -> List[str]:
        """Extract common error patterns from documentation"""
        error_patterns = []
        # Look for error patterns in code blocks or error sections
        error_blocks = re.finditer(r'```(?:error|bash)\n(.*?)\n```', content, re.DOTALL)
        for block in error_blocks:
            error_patterns.append(block.group(1).strip())
        return error_patterns
        
    def add_documentation(self, content: str, tool_name: str, category: str, source: str,
                         version: Optional[str] = None, topics: Optional[List[str]] = None,
                         error_patterns: Optional[List[str]] = None):
        """Add a new piece of documentation to the retriever"""
        # Split content into manageable chunks with overlap
        chunks = self._chunk_text(content)
        
        print(f"Processing {len(chunks)} chunks for {tool_name}...")
        
        # Prepare batch data for ChromaDB
        ids = []
        embeddings = []
        metadatas = []
        documents = []
        
        for i, chunk in enumerate(tqdm(chunks, desc="Generating embeddings")):
            chunk_id = f"{tool_name}_{category}_{i}"
            
            # Generate embedding
            embedding = self._embed_text(chunk)
            
            ids.append(chunk_id)
            embeddings.append(embedding)  
            metadatas.append({
                "tool_name": tool_name,
                "category": category,
                "source": source,
                "version": str(version) if version else "",
                "topics": json.dumps(topics) if topics else "[]",
                "error_patterns": json.dumps(error_patterns) if error_patterns else "[]"
            })
            documents.append(chunk)
        
        # Add to ChromaDB in batch
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )

    def _embed_text(self, text: str) -> List[float]:
        """Embed text using sentence transformers"""
        embeddings = self.embedder.encode([text], convert_to_tensor=False)
        return embeddings[0].tolist()  

    def retrieve(self, query: str, k: int = 3, 
                filter_criteria: Optional[Dict[str, Any]] = None) -> List[Tuple[DocChunk, float]]:
        """Retrieve the k most relevant documentation chunks for a query"""
        # Get query embedding
        query_embedding = self._embed_text(query)
        
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[query],
            n_results=min(k, self.collection.count()),  # Don't request more than we have
            include=['documents', 'metadatas', 'distances']
        )
        
        # Process results
        chunks = []
        if results and results['documents'] and len(results['documents']) > 0:
            for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                chunk = DocChunk(
                    content=doc,
                    tool_name=meta.get('tool_name', 'unknown'),
                    category=meta.get('category', 'unknown')
                )
                chunks.append((chunk, float(dist)))
                
        return chunks

    def query_by_criteria(self, criteria: Dict[str, Any], k: int = 3) -> List[DocChunk]:
        """Query documents by metadata criteria"""
        # Convert criteria to ChromaDB where clause format
        # ChromaDB requires a single $and operator at the top level
        where_clauses = []
        for key, value in criteria.items():
            where_clauses.append({key: value})
            
        where = {"$and": where_clauses} if where_clauses else None
            
        results = self.collection.query(
            query_texts=[""],  # Empty query since we're filtering by metadata
            n_results=min(k, self.collection.count()),
            where=where,
            include=['documents', 'metadatas']
        )
        
        chunks = []
        if results and results['documents'] and len(results['documents']) > 0:
            for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
                chunk = DocChunk(
                    content=doc,
                    tool_name=meta.get('tool_name', 'unknown'),
                    category=meta.get('category', 'unknown')
                )
                chunks.append(chunk)
                
        return chunks

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap, preserving markdown structure"""
        chunks = []
        current_chunk = []
        current_size = 0
        
        # Split by headers first
        sections = re.split(r'(#{1,6}\s+[^\n]+\n)', text)
        
        for section in sections:
            # If it's a header, start a new chunk if current one is getting full
            if re.match(r'#{1,6}\s+[^\n]+\n', section):
                if current_size >= 512 - len(section.split()):
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                        # Keep the last few lines for overlap
                        overlap_size = 0
                        overlap_chunk = []
                        for line in reversed(current_chunk[-5:]):  # Keep last 5 lines
                            if overlap_size + len(line.split()) <= 50:
                                overlap_chunk.insert(0, line)
                                overlap_size += len(line.split())
                        current_chunk = overlap_chunk
                        current_size = overlap_size
                current_chunk.append(section.strip())
                current_size += len(section.split())
                continue
                
            # Split section into sentences/lines
            lines = section.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                line_size = len(line.split())
                
                if current_size + line_size > 512:
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                        # Keep last few lines for overlap
                        overlap_size = 0
                        overlap_chunk = []
                        for prev_line in reversed(current_chunk[-5:]):
                            if overlap_size + len(prev_line.split()) <= 50:
                                overlap_chunk.insert(0, prev_line)
                                overlap_size += len(prev_line.split())
                        current_chunk = overlap_chunk
                        current_size = overlap_size
                
                current_chunk.append(line)
                current_size += line_size
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
            
        return chunks

    def save_index(self, path: str):
        """Save the current index to disk"""
        # ChromaDB already persists to disk, but we can save additional metadata
        metadata = {
            "docs_dir": str(self.docs_dir),
            "model_name": self.embedder.get_config_dict()['model_name']
        }
        with open(path, 'w') as f:
            json.dump(metadata, f)

    def load_index(self, path: str):
        """Load an index from disk"""
        # ChromaDB loads automatically, just update our metadata
        with open(path, 'r') as f:
            metadata = json.load(f)
            self.docs_dir = Path(metadata['docs_dir'])
