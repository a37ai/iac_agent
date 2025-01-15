"""
Documentation manager for fetching and storing documentation from multiple sources.
"""
import asyncio
import logging
from typing import List, Dict, Optional
from pathlib import Path
import yaml
from database import DocumentationDB
from fetchers.terraform_fetcher import TerraformFetcher

logger = logging.getLogger(__name__)

class DocumentationManager:
    """Manages documentation fetching and storage"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.db = DocumentationDB()
        self._load_config()
        
        # Initialize fetchers with config
        terraform_config = self.config.get('terraform', {})
        self.fetchers = {
            'terraform': TerraformFetcher(
                api_url=terraform_config.get('api_url'),
                auth_token=terraform_config.get('auth_token')
            )
        }
    
    def _load_config(self):
        """Load configuration from YAML file"""
        try:
            with open(self.config_path) as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = {}
    
    async def update_all_documentation(self):
        """Update documentation for all configured tools"""
        tasks = []
        
        # Terraform documentation
        if 'terraform' in self.config:
            tasks.append(self._update_terraform_docs())
        
        # Add other tool documentation updates here
        
        await asyncio.gather(*tasks)
    
    async def _update_terraform_docs(self):
        """Update Terraform documentation"""
        try:
            fetcher = self.fetchers['terraform']
            
            # Fetch documentation from all sources
            docs = await fetcher.fetch_documentation()
            
            # Update database
            self.db.update_tool_documentation('terraform', docs)
            
            logger.info(f"Updated {len(docs)} Terraform documentation items")
            
        except Exception as e:
            logger.error(f"Error updating Terraform documentation: {e}")
    
    def search_documentation(self, query: str, tool_name: str = None, k: int = 3, 
                           min_similarity: float = 0.3, include_context: bool = True) -> List[Dict]:
        """
        Search for relevant documentation
        
        Args:
            query: Search query
            tool_name: Optional tool name to filter results
            k: Number of results to return
            min_similarity: Minimum similarity threshold
            include_context: Whether to include related context
        """
        try:
            # Get vector similarity matches
            vector_matches = self.db.vector_db.search_similar(query, k=k*2)  # Get more candidates for filtering
            
            results = []
            seen_content = set()  # Track unique content
            
            for vector_id, similarity in vector_matches:
                if similarity < min_similarity:
                    continue
                
                doc = self.db.get_doc_by_vector_id(vector_id)
                if not doc:
                    continue
                
                # Skip if tool_name specified and doesn't match
                if tool_name and doc['tool_name'] != tool_name:
                    continue
                
                # Skip duplicate content
                content_hash = hash(doc['content'])
                if content_hash in seen_content:
                    continue
                seen_content.add(content_hash)
                
                # Add similarity score
                doc['similarity'] = similarity
                
                # Add related context if requested
                if include_context:
                    doc['related_docs'] = self._get_related_docs(doc, exclude_ids=seen_content)
                
                results.append(doc)
                
                if len(results) >= k:
                    break
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching documentation: {e}")
            return []
    
    def _get_related_docs(self, doc: Dict, exclude_ids: set, max_related: int = 2) -> List[Dict]:
        """Get related documentation based on content similarity and metadata"""
        related = []
        
        try:
            # Get docs with same resource type or provider
            metadata = doc.get('metadata', {})
            resource_type = metadata.get('resource_type')
            provider = metadata.get('provider')
            
            if resource_type or provider:
                cursor = self.db.conn.execute('''
                    SELECT vector_id, content, metadata
                    FROM documentation
                    WHERE json_extract(metadata, '$.resource_type') = ? 
                    OR json_extract(metadata, '$.provider') = ?
                    LIMIT ?
                ''', (resource_type, provider, max_related))
                
                for row in cursor:
                    content_hash = hash(row[1])
                    if content_hash not in exclude_ids:
                        related.append({
                            'content': row[1],
                            'metadata': row[2],
                            'relation_type': 'same_resource' if resource_type else 'same_provider'
                        })
            
            return related[:max_related]
            
        except Exception as e:
            logger.error(f"Error getting related docs: {e}")
            return []
    
    def get_documentation_stats(self) -> Dict:
        """Get statistics about stored documentation"""
        try:
            cursor = self.db.conn.execute('''
                SELECT 
                    tool_name,
                    COUNT(*) as doc_count,
                    COUNT(DISTINCT json_extract(metadata, '$.provider')) as provider_count,
                    COUNT(DISTINCT json_extract(metadata, '$.resource_type')) as resource_count,
                    AVG(LENGTH(content)) as avg_content_length,
                    COUNT(CASE WHEN examples != '[]' THEN 1 END) as examples_count
                FROM documentation
                GROUP BY tool_name
            ''')
            
            stats = {}
            for row in cursor:
                stats[row[0]] = {
                    'document_count': row[1],
                    'provider_count': row[2],
                    'resource_count': row[3],
                    'average_content_length': int(row[4]),
                    'documents_with_examples': row[5]
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting documentation stats: {e}")
            return {}
