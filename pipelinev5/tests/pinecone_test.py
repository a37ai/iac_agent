import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
import json
from datetime import datetime
import os
from utils.general_helper_functions import load_config

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

def initialize_pinecone():
    """Initialize Pinecone client."""
    pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
    return pc.Index("forge")  # Using the same index name as in your code

def initialize_embeddings():
    """Initialize OpenAI embeddings."""
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        dimensions=1536
    )

def fetch_all_vectors(index, batch_size=100):
    """Fetch all vectors from the index."""
    # Create a dummy query vector of the correct dimension
    embeddings = initialize_embeddings()
    query_vector = embeddings.embed_query("dummy query")
    
    # Query with a high limit to get all vectors
    results = index.query(
        vector=query_vector,
        top_k=batch_size,
        include_metadata=True
    )
    
    return results.matches

def format_metadata(metadata):
    """Format metadata for pretty printing."""
    # Convert timestamp to readable format if it exists
    if 'timestamp' in metadata:
        try:
            dt = datetime.fromisoformat(metadata['timestamp'])
            metadata['timestamp'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
    
    return json.dumps(metadata, indent=2)

def main():
    # Load environment variables
    load_dotenv()
    
    print("\n=== Pinecone Database Inspector ===\n")
    
    try:
        # Initialize Pinecone
        index = initialize_pinecone()
        
        # Fetch all vectors
        vectors = fetch_all_vectors(index)
        
        print(f"Found {len(vectors)} records in the database:\n")
        
        # Group records by repo_path
        records_by_repo = {}
        for vector in vectors:
            metadata = vector.metadata
            repo_path = metadata.get('repo_path', 'Unknown Repository')
            
            if repo_path not in records_by_repo:
                records_by_repo[repo_path] = []
            records_by_repo[repo_path].append(metadata)
        
        # Print grouped records
        for repo_path, records in records_by_repo.items():
            print(f"\n{'='*80}")
            print(f"Repository: {repo_path}")
            print(f"Number of records: {len(records)}")
            print("='*80\n")
            
            # Group by type within repository
            records_by_type = {}
            for record in records:
                record_type = record.get('type', 'Unknown Type')
                if record_type not in records_by_type:
                    records_by_type[record_type] = []
                records_by_type[record_type].append(record)
            
            # Print records grouped by type
            for record_type, type_records in records_by_type.items():
                print(f"\nType: {record_type}")
                print(f"Count: {len(type_records)}")
                print("-" * 40)
                
                for record in type_records:
                    print(format_metadata(record))
                    print("-" * 40)

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()