from typing import TypedDict, List, Dict, Optional, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import StateGraph, END
from langgraph.graph import add_messages
import pinecone
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
from typing import Annotated
import json
from utils.general_helper_functions import configure_logger
from states.state import MemoryState
from utils.logging_helper_functions import initialize_logging, log_interaction, log_status_update
from ai_models.openai_models import get_open_ai


logger = configure_logger(__name__)

class MemoryService:
    def __init__(self):
        load_dotenv()
        
        # Initialize Pinecone
        pinecone.init(
            api_key=os.getenv('PINECONE_API_KEY'),
            environment="aws"  # Using AWS environment
        )
        
        # Connect to existing index
        self.index_name = "forge"  # Your existing index name
        self.index = pinecone.Index(self.index_name)
        self.namespace = os.getenv('PINECONE_NAMESPACE', 'default')
        
        # Initialize embeddings model
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=1536  # Matches your index dimensions
        )
        
        # Initialize LLM
        self.llm = get_open_ai(temperature=0.1, model='gpt-4o')

    
    def extract_memories(self, state: MemoryState) -> MemoryState:
        """Extract memories from file analyses and repository overview."""
        logger.info("Extracting memories from analysis")
        
        memories = []
        
        # Extract memories from file analyses
        for file_path, analysis in state["file_analyses"].items():
            memory = {
                "type": "file_analysis",
                "file_path": file_path,
                "content": json.dumps(analysis),
                "timestamp": datetime.now().isoformat(),
                "repo_path": state["repo_path"],
                "repo_type": state["repo_type"]
            }
            memories.append(memory)
        
        # Extract memory from repository overview
        if state["repo_overview"]:
            memory = {
                "type": "repo_overview",
                "content": state["repo_overview"],
                "timestamp": datetime.now().isoformat(),
                "repo_path": state["repo_path"],
                "repo_type": state["repo_type"]
            }
            memories.append(memory)
        
        state["memories"] = memories
        return state
    
    def store_memories(self, state: MemoryState) -> MemoryState:
        """Store memories in Pinecone."""
        logger.info("Storing memories in Pinecone")
        
        try:
            # Prepare vectors for upsert
            vectors = []
            for memory in state["memories"]:
                # Convert memory to string for embedding
                memory_str = json.dumps(memory)
                
                # Generate embedding using OpenAI
                embedding = self.embeddings.embed_query(memory_str)
                
                # Create vector ID
                vector_id = f"{memory['repo_path']}_{memory['type']}_{datetime.now().timestamp()}"
                
                # Add to vectors list
                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": memory
                })
            
            # Upsert to Pinecone
            self.index.upsert(vectors=vectors, namespace=self.namespace)
            logger.info(f"Successfully stored {len(vectors)} memories")
            
        except Exception as e:
            logger.error(f"Error storing memories: {str(e)}")
            raise
        
        return state
    
    def query_memories(self, query: str, repo_path: Optional[str] = None, k: int = 5) -> List[Dict]:
        """Query memories from Pinecone."""
        logger.info(f"Querying memories for: {query}")
        
        try:
            # Generate query embedding using OpenAI
            query_embedding = self.embeddings.embed_query(query)
            
            # Prepare filter if repo_path is provided
            filter_dict = {"repo_path": repo_path} if repo_path else None
            
            # Query Pinecone
            results = self.index.query(
                vector=query_embedding,
                top_k=k,
                namespace=self.namespace,
                filter=filter_dict,
                include_metadata=True
            )
            
            # Extract and return memories from results
            memories = [match.metadata for match in results.matches]
            logger.info(f"Retrieved {len(memories)} memories")
            
            return memories
            
        except Exception as e:
            logger.error(f"Error querying memories: {str(e)}")
            raise

