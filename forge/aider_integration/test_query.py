"""
Test a specific RAG query.
"""
import asyncio
from forge.rag_coder import RAGCodeGenerator
from forge.rag_llm import RAGLLMPipeline
from forge.rag_retriever import RAGRetriever

async def test_specific_query():
    """Test a specific query"""
    # Initialize components
    retriever = RAGRetriever()
    pipeline = RAGLLMPipeline(retriever=retriever)
    generator = RAGCodeGenerator(pipeline=pipeline)
    
    # Ingest documentation
    print("Ingesting documentation...")
    retriever.ingest_documentation()
    
    # Test the query
    query = "How do I write a Terraform script to deploy an EC2 instance?"
    print(f"\nQuery: {query}")
    response = await generator.generate_code(query)
    print("\nResponse:")
    print(f"Tool: {response['tool']}")
    print(f"Category: {response['category']}")
    print(f"Answer: {response['answer']}")

if __name__ == "__main__":
    asyncio.run(test_specific_query())
