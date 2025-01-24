"""
Aider integration for RAG-enhanced documentation lookup.
"""
from .rag_command import RAGCommand

def register_commands(aider):
    """Register RAG commands with Aider"""
    aider.register_command(RAGCommand)
