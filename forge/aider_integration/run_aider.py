import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from aider.main import main as aider_main
from aider.commands import Commands
from forge.aider_integration.rag_aider_commands import RAGCommands

def main():
    # Monkey patch the Commands class with our RAG-enabled version
    Commands.__bases__ = (RAGCommands,)
    
    # Run Aider with the patched commands
    aider_main()

if __name__ == "__main__":
    main()
