from pathlib import Path
from typing import Optional, Dict, Any
from aider.commands import Commands

from forge.rag_coder import RAGCodeGenerator
from forge.rag_llm import RAGLLMPipeline
from forge.rag_retriever import RAGRetriever

class RAGCommands(Commands):
    """Base class for RAG-enabled commands"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retriever = RAGRetriever()
        self.pipeline = RAGLLMPipeline(retriever=self.retriever)
        self.generator = RAGCodeGenerator(pipeline=self.pipeline)
        
        # Initialize by ingesting documentation
        self._initialize_docs()
    
    def _initialize_docs(self):
        """Initialize by ingesting documentation"""
        docs_dir = Path("docs")
        if not docs_dir.exists():
            return
            
        # Map of directories to tool categories
        doc_categories = {
            "iac": ["terraform", "cloudformation", "pulumi"],
            "containers": ["kubernetes", "docker"],
            "cicd": ["github_actions", "jenkins", "gitlab"],
            "monitoring": ["prometheus", "grafana"]
        }
        
        # Ingest all documentation
        for category, tools in doc_categories.items():
            category_dir = docs_dir / category
            if category_dir.exists():
                for tool in tools:
                    tool_dir = category_dir / tool
                    if tool_dir.exists():
                        for doc_file in tool_dir.glob("*.md"):
                            self.generator.add_documentation(
                                doc_path=doc_file,
                                tool_name=tool,
                                category=category
                            )
    
    async def do_rag(self, args: str) -> Optional[Dict[str, Any]]:
        """Run the RAG command with the given query"""
        if not args:
            return {"error": "Please provide a query for the RAG system"}
        
        try:
            # Process the query using RAG
            response = await self.generator.generate_code(args)
            
            # Format the response for Aider
            return {
                "tool": response["tool"],
                "category": response["category"],
                "answer": response["answer"]
            }
        except Exception as e:
            return {"error": f"Error processing RAG query: {str(e)}"}
            
    def help_rag(self) -> str:
        """Get help text for the RAG command"""
        return """
        RAG Command Help:
        -----------------
        The RAG command uses a Retrieval-Augmented Generation system to provide
        documentation-aware responses to your queries.
        
        Usage:
            /rag <query>
        
        Examples:
            /rag How do I configure AWS provider in Terraform?
            /rag What are some common Kubernetes deployment patterns?
            /rag How do I set up Grafana dashboards?
        
        The command will search through the documentation and provide relevant,
        context-aware responses to your queries.
        """
