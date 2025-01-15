"""
RAG-enhanced coder that integrates documentation context with existing coders.
"""
from typing import Optional, Dict, List, Tuple
from pathlib import Path

from .base_coder import Coder
from .editblock_coder import EditBlockCoder
from ..rag_retriever import DevOpsRetriever
from ..rag_llm import RAGLLMPipeline

class RAGEnhancedCoder(EditBlockCoder):
    """A coder that enhances EditBlockCoder with RAG capabilities."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retriever = DevOpsRetriever()
        self.pipeline = RAGLLMPipeline(self.retriever)
        self._load_documentation()

    def _load_documentation(self):
        """Load documentation from the docs directory"""
        docs_dir = Path(self.abs_root_path("docs"))
        if not docs_dir.exists():
            docs_dir.mkdir(parents=True)
            
        # Load existing documentation index if it exists
        index_path = docs_dir / "docs_index.json"
        if index_path.exists():
            self.retriever.load_index(str(index_path))

    async def get_response(self, prompt: str, messages: List[Dict] = None) -> str:
        """Override to enhance with RAG context"""
        # Get relevant documentation
        doc_chunks = self.retriever.retrieve(prompt, k=3)
        
        # Add documentation context to the prompt
        doc_context = "\n\n".join([
            f"Documentation for {chunk.tool_name} ({chunk.category}):\n{chunk.content}"
            for chunk in doc_chunks
        ])
        
        enhanced_prompt = f"""Given the following DevOps documentation and task, provide a solution.
        
Documentation Context:
{doc_context}

Task:
{prompt}

Additional Context:
- Use the documentation provided to inform your solution
- Follow DevOps best practices
- Ensure configuration is secure and follows standards
"""
        
        # Call parent class's get_response with enhanced prompt
        return await super().get_response(enhanced_prompt, messages)

    def add_documentation(self, doc_path: Path, tool_name: str, category: str):
        """Add new documentation to the retriever"""
        with open(doc_path, 'r') as f:
            content = f.read()
        self.retriever.add_documentation(
            content=content,
            tool_name=tool_name,
            category=category,
            source=str(doc_path)
        )
        
        # Save updated index
        docs_dir = Path(self.abs_root_path("docs"))
        index_path = docs_dir / "docs_index.json"
        self.retriever.save_index(str(index_path))
