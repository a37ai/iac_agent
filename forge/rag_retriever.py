"""
Documentation retrieval system for enhancing Aider's code generation.
Initially focused on Terraform documentation.
"""
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
from documentation_manager import DocumentationManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AiderDocRetriever:
    """Retrieves relevant documentation for Aider's code generation"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or str(Path(__file__).parent / 'config.yaml')
        self.doc_manager = DocumentationManager(self.config_path)
    
    async def initialize(self):
        """Initialize by fetching documentation"""
        await self.doc_manager.update_all_documentation()
        logger.info("Documentation initialized")
    
    def get_relevant_docs(self, query: str, error_context: Optional[str] = None, k: int = 3) -> List[Dict]:
        """Get documentation relevant to the query and error context"""
        try:
            # Build search query
            search_query = query
            if error_context:
                search_query = f"{query} {error_context}"
            
            # Search documentation
            results = self.doc_manager.search_documentation(search_query, tool_name='terraform', k=k)
            
            # Filter and format results
            formatted_results = []
            for doc in results:
                if doc.get('similarity', 0) >= 0.3:  # Only include results above threshold
                    formatted_doc = {
                        'type': doc['content_type'],
                        'source': doc['metadata'].get('source', 'unknown'),
                        'similarity': doc.get('similarity', 0),
                        'summary': doc.get('summary', ''),
                        'content': doc['content'],
                        'examples': doc.get('examples', [])
                    }
                    
                    # Add resource-specific info if available
                    if 'resource_type' in doc['metadata']:
                        formatted_doc['resource_type'] = doc['metadata']['resource_type']
                    
                    # Add provider info if available
                    if 'provider' in doc['metadata']:
                        formatted_doc['provider'] = doc['metadata']['provider']
                    
                    formatted_results.append(formatted_doc)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error retrieving documentation: {e}")
            return []

async def test_retriever():
    """Test the documentation retriever with sample queries"""
    print("Initializing documentation retriever...")
    retriever = AiderDocRetriever()
    await retriever.initialize()
    
    # Print documentation statistics
    stats = retriever.doc_manager.get_documentation_stats()
    print("\nDocumentation Statistics:")
    for tool, tool_stats in stats.items():
        print(f"\n{tool.upper()} Documentation:")
        for key, value in tool_stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
    
    test_cases = [
        {
            "query": "Create an AWS ECS cluster",
            "error": None,
            "min_similarity": 0.3
        },
        {
            "query": "Set up an aws_ecs_cluster",
            "error": "Error: resource aws_ecs_cluster not found",
            "min_similarity": 0.4
        },
        {
            "query": "Configure AWS provider with assume role",
            "error": None,
            "min_similarity": 0.5
        },
        {
            "query": "Define ECS task definition with Fargate",
            "error": None,
            "min_similarity": 0.3
        },
        {
            "query": "Set up auto scaling for ECS service",
            "error": None,
            "min_similarity": 0.4
        }
    ]
    
    print("\nTesting queries...")
    for case in test_cases:
        print(f"\nQuery: {case['query']}")
        if case['error']:
            print(f"Error Context: {case['error']}")
        
        docs = retriever.get_relevant_docs(
            case['query'], 
            case['error'],
            k=3
        )
        
        print(f"\nFound {len(docs)} relevant documents:")
        
        for i, doc in enumerate(docs, 1):
            print(f"\nDocument {i}:")
            print(f"Type: {doc['type']}")
            print(f"Source: {doc['source']}")
            print(f"Similarity: {doc['similarity']:.3f}")
            
            if 'resource_type' in doc:
                print(f"Resource Type: {doc['resource_type']}")
            if 'provider' in doc:
                print(f"Provider: {doc['provider']}")
            
            print(f"\nSummary: {doc['summary']}")
            
            if doc['examples']:
                print("\nExample:")
                print(doc['examples'][0])
            
            if 'related_docs' in doc and doc['related_docs']:
                print("\nRelated Documentation:")
                for related in doc['related_docs']:
                    print(f"- {related['relation_type']}: {related.get('metadata', {}).get('title', 'Untitled')}")
            
            print("\nContent Preview:")
            content_preview = doc['content'][:300]
            print(content_preview + "..." if len(doc['content']) > 300 else content_preview)

if __name__ == "__main__":
    asyncio.run(test_retriever())
