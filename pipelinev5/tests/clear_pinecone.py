import os
from dotenv import load_dotenv
from pinecone import Pinecone
from utils.general_helper_functions import load_config

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

def clear_pinecone_index():
    # Load environment variables
    load_dotenv()
    
    # Initialize Pinecone
    pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
    index = pc.Index("forge")
    
    try:
        # Delete all vectors
        index.delete(delete_all=True)
        print("Successfully deleted all vectors from the Pinecone index")
    except Exception as e:
        print(f"Error clearing index: {str(e)}")

if __name__ == "__main__":
    clear_pinecone_index()