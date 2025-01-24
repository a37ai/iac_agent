"""
Two-step LLM pipeline for improved DevOps code generation using RAG.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import re
import json

from forge.llm_interface import LLMInterface
from .rag_retriever import RAGRetriever, DocChunk

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
    error_matches: Optional[List[str]] = None
    suggested_fixes: Optional[List[str]] = None

class RAGLLMPipeline:
    def __init__(self, retriever: RAGRetriever, model: str = "gpt-3.5-turbo"):
        """Initialize the RAG-enhanced LLM pipeline"""
        self.retriever = retriever
        self.llm = LLMInterface(model=model)
        
    async def process_query(self, query: str) -> str:
        """Process a query using the RAG pipeline"""
        try:
            # Step 1: Analyze query to determine relevant documentation
            logger.info("Step 1: Analyzing query and determining relevant documentation...")
            analysis = await self.llm.analyze_query(query)
            
            # Step 2: Retrieve relevant documentation
            if analysis:
                tool = analysis.get('tool')
                category = analysis.get('category')
                
                # Get relevant docs
                relevant_docs = []
                if tool or category:
                    criteria = {}
                    if tool:
                        criteria['tool_name'] = tool
                    if category:
                        criteria['category'] = category
                    relevant_docs = self.retriever.query_by_criteria(criteria)
                
                if not relevant_docs:  # Fall back to semantic search
                    doc_chunks = self.retriever.retrieve(query)
                    relevant_docs = [chunk for chunk, _ in doc_chunks]
                
                # Step 3: Generate response using retrieved documentation
                if relevant_docs:
                    context = "\n---\n".join(chunk.content for chunk in relevant_docs)
                    response = await self.llm.generate_answer(query, context)
                    return {
                        'tool': tool or 'unknown',
                        'category': category or 'unknown',
                        'answer': response
                    }
            
            return {
                'tool': 'unknown',
                'category': 'unknown',
                'answer': "I'm sorry, I couldn't find any relevant documentation to help answer your query."
            }
            
        except Exception as e:
            logger.error(f"Error in RAG pipeline: {str(e)}")
            return {
                'tool': 'unknown',
                'category': 'unknown',
                'answer': f"An error occurred while processing your query: {str(e)}"
            }
    
    def _is_error_query(self, query: str) -> bool:
        """Determine if this is an error-related query"""
        error_indicators = [
            r'error',
            r'exception',
            r'failed',
            r'failure',
            r'invalid',
            r'denied',
            r'permission',
            r'timeout',
            r'refused'
        ]
        return any(re.search(pattern, query, re.IGNORECASE) for pattern in error_indicators)
    
    def _extract_error_patterns(self, text: str) -> List[str]:
        """Extract error patterns from text"""
        patterns = []
        
        # Common error message patterns
        error_patterns = [
            r'Error:\s*(.*?)(?:\n|$)',
            r'Exception:\s*(.*?)(?:\n|$)',
            r'failed:\s*(.*?)(?:\n|$)',
            r'stderr:\s*(.*?)(?:\n|$)',
            r'\[(ERROR|FATAL)\]\s*(.*?)(?:\n|$)'
        ]
        
        for pattern in error_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                error_msg = match.group(1).strip()
                if error_msg:
                    patterns.append(error_msg)
                    
        return patterns
    
    def _extract_fixes_from_docs(self, doc_chunks: List[Tuple[DocChunk, float]]) -> List[str]:
        """Extract potential fixes from documentation chunks"""
        fixes = []
        fix_patterns = [
            r'(?:fix|solution|resolve):\s*(.*?)(?:\n|$)',
            r'to resolve this:\s*(.*?)(?:\n|$)',
            r'you can fix this by:\s*(.*?)(?:\n|$)',
            r'recommended solution:\s*(.*?)(?:\n|$)'
        ]
        
        for chunk, _ in doc_chunks:
            for pattern in fix_patterns:
                matches = re.finditer(pattern, chunk.content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    fix = match.group(1).strip()
                    if fix and fix not in fixes:
                        fixes.append(fix)
                        
        return fixes
    
    def _analyze_query(self, query: str) -> Dict:
        """Analyze query to determine relevant documentation"""
        # Use LLM to analyze query and determine documentation needs
        logger.info("Analyzing query and determining relevant documentation...")
        query_analysis = self.llm.analyze_query(query)
        
        # Use error patterns if it's an error query
        is_error = self._is_error_query(query)
        if is_error:
            error_patterns = self._extract_error_patterns(query)
            if error_patterns:
                query_analysis['error_patterns'] = error_patterns
        
        return query_analysis
    
    def _generate_response(self, query: str, context: str) -> str:
        """Generate response using retrieved documentation"""
        # Generate answer using LLM
        answer = self.llm.generate_answer(query, context)
        
        return answer
    
    def _format_doc_content(self, doc_chunks: List[Tuple[DocChunk, float]]) -> str:
        """Format documentation content for the prompt"""
        content = []
        for chunk, similarity in doc_chunks:
            content.append(f"""
            Tool: {chunk.tool_name} ({chunk.category})
            Version: {chunk.version if chunk.version else 'N/A'}
            Topics: {', '.join(chunk.topics) if chunk.topics else 'N/A'}
            Relevance: {similarity:.2f}
            Source: {chunk.source}
            
            {chunk.content}
            """)
        return "\n\n".join(content)
