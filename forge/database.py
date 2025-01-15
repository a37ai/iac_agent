"""
SQLite and vector database for storing documentation.
"""
from typing import List, Dict
import sqlite3
from datetime import datetime
import json
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import re
import logging

logger = logging.getLogger(__name__)

class VectorDB:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vectors: Dict[str, np.ndarray] = {}
        self.similarity_threshold = 0.3  # Minimum similarity score to consider
    
    def store_vector(self, content: str) -> str:
        """Store a vector embedding for content"""
        # Clean and preprocess content
        content = self._preprocess_content(content)
        
        # Generate embedding
        vector = self.model.encode(content, normalize_embeddings=True)  # Normalize for better similarity
        vector_id = str(hash(content))
        self.vectors[vector_id] = vector
        return vector_id
    
    def search_similar(self, query: str, k: int = 3) -> List[tuple]:
        """Find k most similar vectors with scores above threshold"""
        # Clean and preprocess query
        query = self._preprocess_content(query)
        
        # Generate query embedding
        query_vector = self.model.encode(query, normalize_embeddings=True)
        
        # Calculate similarities with cosine similarity
        similarities = []
        for vector_id, vector in self.vectors.items():
            similarity = np.dot(query_vector, vector)  # Cosine similarity since vectors are normalized
            if similarity >= self.similarity_threshold:
                similarities.append((vector_id, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]
    
    def _preprocess_content(self, text: str) -> str:
        """Clean and preprocess text for better embedding"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Add special tokens for Terraform-specific terms
        text = text.replace('resource', '[RESOURCE]')
        text = text.replace('provider', '[PROVIDER]')
        text = text.replace('module', '[MODULE]')
        text = text.replace('data', '[DATA]')
        
        return text

class DocumentationDB:
    def __init__(self, db_path: str = 'documentation.db'):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.vector_db = VectorDB()
        self._initialize_db()
    
    def _initialize_db(self):
        """Create necessary tables if they don't exist"""
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS documentation (
                id INTEGER PRIMARY KEY,
                tool_name TEXT,
                version TEXT,
                content_type TEXT,
                content TEXT,
                vector_id TEXT,
                last_updated TIMESTAMP,
                metadata TEXT,
                summary TEXT,
                examples TEXT
            )
        ''')
        self.conn.commit()
    
    def update_tool_documentation(self, tool_name: str, docs: List[Dict]):
        """Update documentation for a specific tool"""
        current_time = datetime.now()
        
        # First, remove old documentation for this tool
        self.conn.execute('DELETE FROM documentation WHERE tool_name = ?', (tool_name,))
        
        # Remove old vectors for this tool
        cursor = self.conn.execute('SELECT vector_id FROM documentation WHERE tool_name = ?', (tool_name,))
        old_vector_ids = [row[0] for row in cursor]
        for vector_id in old_vector_ids:
            if vector_id in self.vector_db.vectors:
                del self.vector_db.vectors[vector_id]
        
        for doc in docs:
            try:
                # Skip invalid documents
                if not doc.get('content'):
                    continue
                
                # Generate summary if not present
                summary = doc.get('summary', self._generate_summary(doc['content']))
                
                # Extract examples if present
                examples = doc.get('examples', self._extract_examples(doc['content']))
                examples_json = json.dumps(examples)
                
                # Generate vector embedding for the content
                vector_id = self.vector_db.store_vector(doc['content'])
                
                self.conn.execute('''
                    INSERT INTO documentation 
                    (tool_name, version, content_type, content, vector_id, last_updated, metadata, summary, examples)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tool_name,
                    doc['version'],
                    doc['content_type'],
                    doc['content'],
                    vector_id,
                    current_time,
                    json.dumps(doc.get('metadata', {})),
                    summary,
                    examples_json
                ))
            except Exception as e:
                logger.error(f"Error updating document: {e}")
                continue
        
        self.conn.commit()

    def get_doc_by_vector_id(self, vector_id: str) -> Dict:
        """Get document by its vector ID"""
        cursor = self.conn.execute('''
            SELECT tool_name, version, content_type, content, metadata, summary, examples
            FROM documentation
            WHERE vector_id = ?
        ''', (vector_id,))
        
        row = cursor.fetchone()
        if row:
            return {
                'tool_name': row[0],
                'version': row[1],
                'content_type': row[2],
                'content': row[3],
                'metadata': json.loads(row[4]),
                'summary': row[5],
                'examples': json.loads(row[6]) if row[6] else []
            }
        return None
    
    def _generate_summary(self, content: str) -> str:
        """Generate a brief summary of the content"""
        # Get first paragraph or first 200 characters
        paragraphs = content.split('\n\n')
        summary = paragraphs[0] if paragraphs else content
        return summary[:200] + '...' if len(summary) > 200 else summary
    
    def _extract_examples(self, content: str) -> List[str]:
        """Extract code examples from content"""
        examples = []
        
        # Look for markdown code blocks
        code_blocks = re.findall(r'```(?:hcl|terraform)?\n(.*?)\n```', content, re.DOTALL)
        if code_blocks:
            examples.extend(code_blocks)
        
        # Look for indented code blocks
        lines = content.split('\n')
        current_block = []
        in_block = False
        
        for line in lines:
            if line.startswith('    ') or line.startswith('\t'):
                current_block.append(line.strip())
                in_block = True
            elif in_block and not line.strip():
                current_block.append('')
            elif in_block:
                if current_block:
                    examples.append('\n'.join(current_block))
                current_block = []
                in_block = False
        
        if current_block:
            examples.append('\n'.join(current_block))
        
        return examples
    
    def get_tool_documentation(self, tool_name: str, version: str = None) -> List[Dict]:
        """Get all documentation for a specific tool"""
        if version:
            cursor = self.conn.execute('''
                SELECT version, content_type, content, metadata, summary, examples
                FROM documentation
                WHERE tool_name = ? AND version = ?
            ''', (tool_name, version))
        else:
            cursor = self.conn.execute('''
                SELECT version, content_type, content, metadata, summary, examples
                FROM documentation
                WHERE tool_name = ?
            ''', (tool_name,))
        
        docs = []
        for row in cursor:
            docs.append({
                'version': row[0],
                'content_type': row[1],
                'content': row[2],
                'metadata': json.loads(row[3]),
                'summary': row[4],
                'examples': json.loads(row[5]) if row[5] else []
            })
        return docs
