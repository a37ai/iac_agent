"""
RAG workflow for processing queries in a chat-like manner.
"""
import asyncio
import sys
from forge.rag_coder import RAGCodeGenerator
from forge.rag_llm import RAGLLMPipeline
from forge.rag_retriever import RAGRetriever

class RAGChat:
    def __init__(self):
        """Initialize RAG components"""
        self.retriever = RAGRetriever()
        self.pipeline = RAGLLMPipeline(retriever=self.retriever)
        self.generator = RAGCodeGenerator(pipeline=self.pipeline)
        
        # Initialize by ingesting documentation
        print("Initializing RAG components...")
        print("\nIngesting documentation from docs...")
        self.retriever.ingest_documentation()
        print("\nReady to process queries!\n")
    
    async def process_query(self, query: str) -> dict:
        """Process a single query"""
        print(f"\nQuery: {query}")
        response = await self.generator.generate_code(query)
        print("\nResponse:")
        print(f"Tool: {response['tool']}")
        print(f"Category: {response['category']}")
        print(f"Answer: {response['answer']}")
        return response

    async def interactive_mode(self):
        """Run in interactive mode"""
        print("\nEntering interactive mode. Type 'exit' to quit.\n")
        while True:
            try:
                query = input("Enter your query: ")
                if query.lower() == 'exit':
                    break
                await self.process_query(query)
            except KeyboardInterrupt:
                print("\nExiting interactive mode...")
                break
            except Exception as e:
                print(f"Error processing query: {str(e)}")

async def main():
    """Main entry point"""
    chat = RAGChat()
    
    # Check if query was provided as command line argument
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        await chat.process_query(query)
    else:
        # No query provided, enter interactive mode
        await chat.interactive_mode()

if __name__ == "__main__":
    asyncio.run(main())
