"""
Two-step LLM pipeline for improved DevOps code generation using RAG.
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import asyncio
import logging
from .rag_retriever import DevOpsRetriever, DocChunk

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class RAGResponse:
    """Response from the RAG-enhanced LLM pipeline"""
    answer: str
    relevant_docs: List[DocChunk]
    confidence: float
    tool_name: str
    category: str

class RAGLLMPipeline:
    def __init__(self, retriever: DevOpsRetriever):
        """Initialize the RAG-enhanced LLM pipeline"""
        self.retriever = retriever
        
    async def process_query(self, query: str, context: Optional[Dict] = None) -> RAGResponse:
        """
        Process a query through the two-step LLM pipeline:
        1. First LLM call to determine which documentation to look up
        2. Second LLM call to generate response using the documentation
        """
        try:
            # Step 1: Use first LLM to determine documentation needs
            logger.info("Step 1: Determining relevant documentation...")
            doc_query = self._generate_doc_query(query, context)
            doc_chunks = self.retriever.retrieve(doc_query, k=3)
            
            if not doc_chunks:
                logger.warning("No relevant documentation found")
                return RAGResponse(
                    answer="I apologize, but I couldn't find relevant documentation to assist with your query.",
                    relevant_docs=[],
                    confidence=0.0,
                    tool_name="unknown",
                    category="unknown"
                )
            
            # Get the most relevant tool and category
            top_chunk, similarity = doc_chunks[0]
            tool_name = top_chunk.tool_name
            category = top_chunk.category
            
            # Step 2: Use second LLM (with larger context) to generate response
            logger.info(f"Step 2: Generating response using {tool_name} documentation...")
            relevant_content = self._format_doc_content(doc_chunks)
            
            # Format the prompt with documentation context
            full_prompt = self._format_prompt(query, relevant_content, context)
            
            # This would integrate with your actual LLM infrastructure
            # For now, returning a placeholder
            # In practice, this would call your large context model (e.g., GPT-4)
            response = "Placeholder response - integrate with your LLM"
            
            return RAGResponse(
                answer=response,
                relevant_docs=[chunk for chunk, _ in doc_chunks],
                confidence=max(sim for _, sim in doc_chunks),
                tool_name=tool_name,
                category=category
            )
            
        except Exception as e:
            logger.error(f"Error in RAG pipeline: {e}")
            return RAGResponse(
                answer=f"An error occurred while processing your query: {str(e)}",
                relevant_docs=[],
                confidence=0.0,
                tool_name="unknown",
                category="unknown"
            )
    
    def _generate_doc_query(self, query: str, context: Optional[Dict]) -> str:
        """Generate a documentation-focused query"""
        doc_query = f"""
        Find documentation about DevOps tools and practices related to:
        {query}
        
        Context:
        {context if context else 'No additional context provided'}
        
        Focus on:
        1. Infrastructure as Code (IaC)
        2. Container orchestration
        3. CI/CD pipelines
        4. Monitoring and observability
        5. Configuration management
        """
        return doc_query
    
    def _format_doc_content(self, doc_chunks: List[Tuple[DocChunk, float]]) -> str:
        """Format documentation content for the prompt"""
        content = []
        for chunk, similarity in doc_chunks:
            content.append(f"""
            Tool: {chunk.tool_name} ({chunk.category})
            Relevance: {similarity:.2f}
            Source: {chunk.source}
            
            {chunk.content}
            """)
        return "\n\n".join(content)
    
    def _format_prompt(self, query: str, docs: str, context: Optional[Dict]) -> str:
        """Format the prompt for the second LLM call"""
        prompt = f"""Given the following DevOps documentation and query, provide a detailed solution.
        
Documentation:
{docs}

Query:
{query}

Additional Context:
{context if context else 'No additional context provided'}

Please provide a solution that:
1. Directly addresses the query
2. Uses the provided documentation appropriately
3. Follows DevOps best practices
4. Includes any necessary code or configuration
5. Explains any assumptions or prerequisites
6. Highlights potential security considerations
7. Suggests monitoring and observability practices

Your response should be:
1. Accurate according to the documentation
2. Secure by default
3. Following infrastructure as code best practices
4. Including error handling and resilience
5. Considering scalability and maintenance
"""
        return prompt
