# System Mapper with Persistent Memory and DevOps Agent

This system combines a comprehensive codebase mapper with a DevOps agent that can execute infrastructure and deployment tasks.

## Features

- Repository cloning and analysis
- File tree generation
- File content analysis with intelligent summaries
- Environment detection
- Comprehensive system mapping in JSON format
- Long-term memory storage and retrieval
- Semantic search across codebase history
- Automated DevOps task execution

## DevOps Agent

The DevOps agent uses a simple but powerful workflow:

1. **Decision Making Head**
   - Takes current state (plan, step, history)
   - Uses LLM to decide next action
   - Chooses from available tools
   - Updates state with decision

2. **Tool Execution**
   - Executes chosen tool
   - Updates knowledge sequence
   - Returns to decision head

### Available Tools

The agent has access to these core tools:

1. **Execute Command**
   - Run shell commands with pattern matching
   - Handles command completion and error detection

2. **Execute Code**
   - Run code through Forge
   - Supports various execution environments

3. **Ask Human**
   - Request user input/confirmation
   - Handle blocking operations

4. **Run File**
   - Execute files directly
   - Support for scripts and executables

5. **Validate Output**
   - Check command output against criteria
   - Verify execution results

6. **Validate Code Changes**
   - Compare code modifications
   - Ensure changes match expectations

7. **Validate File Output**
   - Verify file contents
   - Check against expected output

8. **Delete File**
   - Remove files from codebase
   - Clean up operations

9. **Create File**
   - Create new files
   - Write content with proper permissions

## Setup

1. Copy `.env.template` to `.env` and fill in your repository details:
   ```bash
   cp .env.template .env
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure your `.env` file with:
   - Repository Configuration:
     - `REPO_URLS`: Repository URLs (comma-separated for multiple repositories)
     - `REPO_TYPE`: Either 'mono' or 'poly'
     - `REPO_BRANCH`: Branch to analyze (default: main)
     - `LOCAL_CLONE_PATH`: Where to clone repositories
     - `GIT_USERNAME`: (Optional) Git username for authentication
     - `GIT_TOKEN`: (Optional) Git token for authentication

   - AI Configuration:
     - `GOOGLE_API_KEY`: Gemini API key for repository overview
     - `OPENAI_API_KEY`: OpenAI API key for file analysis

   - Memory Service Configuration:
     - `PINECONE_API_KEY`: Your Pinecone API key
     - `PINECONE_ENVIRONMENT`: Pinecone environment (e.g., gcp-starter)
     - `PINECONE_INDEX_NAME`: Name for the Pinecone index (default: iac-memory)
     - `PINECONE_NAMESPACE`: Namespace for the Pinecone index (default: default)

   Example for monorepo:
   ```
   REPO_URLS=https://github.com/user/monorepo
   REPO_TYPE=mono
   ```

   Example for polyrepo:
   ```
   REPO_URLS=https://github.com/user/repo1,https://github.com/user/repo2
   REPO_TYPE=poly
   ```

## Usage

Run the system mapper:
```bash
python system_mapper.py
```

This will:
1. Generate a system map with file analysis and repository overview
2. Store the analysis in Pinecone for long-term memory
3. Create three output files:
   - `file_summaries.txt`: Concise summaries of each file
   - `file_tree.txt`: Repository structure
   - `codebase_overview.txt`: Comprehensive analysis of the codebase

## Memory Service

The memory service provides persistent storage of codebase analysis using Pinecone vector database. It stores:
- File-level analysis
- Repository overviews
- Environment configurations
- Historical changes

### Querying Memory

You can query the memory service to get historical information about your codebase:

```python
from memory_service.memory_graph import MemoryService

# Initialize memory service
memory_service = MemoryService()

# Query memories
memories = memory_service.query_memories(
    query="What is the main purpose of this repository?",
    repo_path="/path/to/repo"  # Optional: Filter by repository
)

# Process results
for memory in memories:
    print(f"Type: {memory['type']}")
    print(f"Content: {memory['content']}")
```

## Output Format

The generated `system_map.json` contains:
```json
{
    "repository_type": "mono|poly",
    "file_tree": {
        "directory": {
            "subdirectory": {...},
            "file": "file"
        }
    },
    "environments": {
        "development": ["path/to/dev/files"],
        "staging": ["path/to/staging/files"],
        "production": ["path/to/prod/files"]
    },
    "file_analyses": {
        "path/to/file": {
            "main_purpose": "2-3 sentence overview",
            "key_components": ["component1", "component2"],
            "patterns": ["pattern1", "pattern2"],
            "devops_relevance": {
                "configuration": "...",
                "infrastructure": "...",
                "pipeline": "...",
                "security": "...",
                "monitoring": "..."
            }
        }
    }
}
``` 
</rewritten_file>