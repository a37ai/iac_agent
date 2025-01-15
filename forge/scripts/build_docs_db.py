"""
Script to build and maintain the DevOps documentation database.
Fetches documentation from official sources and processes it for RAG.
"""
import asyncio
import aiohttp
import os
from pathlib import Path
from typing import List, Dict, Optional
import yaml
import json
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin
import re
from concurrent.futures import ThreadPoolExecutor
import markdown
import requests
from ratelimit import limits, sleep_and_retry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting for API calls
CALLS = 25
RATE_LIMIT = 60

# Documentation sources with structured information
DOCS_CONFIG = {
    "terraform": {
        "category": "IaC",
        "base_url": "https://developer.hashicorp.com/terraform/docs",
        "api_docs": "https://developer.hashicorp.com/terraform/plugin/framework/handling-data",
        "github_docs": "https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/main/docs",
        "local_examples": "examples/terraform/*.tf",
        "patterns": [
            r"resource\s+\"aws_\w+\"",
            r"data\s+\"aws_\w+\"",
            r"provider\s+\"aws\""
        ]
    },
    "kubernetes": {
        "category": "Container Orchestration",
        "base_url": "https://kubernetes.io/docs",
        "api_docs": "https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/",
        "github_docs": "https://raw.githubusercontent.com/kubernetes/website/main/content/en/docs",
        "local_examples": "examples/kubernetes/*.yaml",
        "patterns": [
            r"kind:\s+\w+",
            r"apiVersion:",
            r"metadata:"
        ]
    },
    "prometheus": {
        "category": "Observability",
        "base_url": "https://prometheus.io/docs",
        "api_docs": "https://prometheus.io/docs/prometheus/latest/querying/api/",
        "github_docs": "https://raw.githubusercontent.com/prometheus/prometheus/main/docs",
        "local_examples": "examples/prometheus/*.yaml",
        "patterns": [
            r"rule_files:",
            r"scrape_configs:",
            r"alerting:"
        ]
    },
    "github_actions": {
        "category": "CI/CD",
        "base_url": "https://docs.github.com/en/actions",
        "api_docs": "https://docs.github.com/en/rest/actions",
        "github_docs": "https://raw.githubusercontent.com/actions/runner/main/docs",
        "local_examples": "examples/github-actions/*.yaml",
        "patterns": [
            r"on:",
            r"jobs:",
            r"steps:"
        ]
    },
    "ansible": {
        "category": "Configuration Management",
        "base_url": "https://docs.ansible.com",
        "api_docs": "https://docs.ansible.com/ansible/latest/collections/index.html",
        "github_docs": "https://raw.githubusercontent.com/ansible/ansible/devel/docs",
        "local_examples": "examples/ansible/*.yaml",
        "patterns": [
            r"tasks:",
            r"hosts:",
            r"vars:"
        ]
    }
}

class DocsFetcher:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.session = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        
    @sleep_and_retry
    @limits(calls=CALLS, period=RATE_LIMIT)
    async def fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL with rate limiting and retries"""
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Failed to fetch {url}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def extract_content(self, html: str, tool_name: str) -> str:
        """Extract and clean content with tool-specific patterns"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script, style, and nav elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
            
            # Extract main content based on common documentation patterns
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main_content:
                text = main_content.get_text()
            else:
                text = soup.get_text()
            
            # Clean and normalize text
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = '\n'.join(lines)
            
            # Look for tool-specific patterns
            patterns = DOCS_CONFIG[tool_name].get('patterns', [])
            matches = []
            for pattern in patterns:
                matches.extend(re.finditer(pattern, text))
            
            # If we found specific patterns, prioritize those sections
            if matches:
                sections = []
                last_pos = 0
                for match in matches:
                    start = max(0, match.start() - 500)  # Include context before pattern
                    end = min(len(text), match.end() + 500)  # Include context after pattern
                    sections.append(text[start:end])
                    last_pos = end
                return '\n\n'.join(sections)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting content: {e}")
            return ""

    async def process_tool(self, tool_name: str, config: Dict):
        """Process documentation for a specific tool"""
        try:
            tool_dir = self.output_dir / tool_name
            tool_dir.mkdir(exist_ok=True)
            
            # Fetch main documentation
            content = await self.fetch_url(config['base_url'])
            if content:
                main_doc = self.extract_content(content, tool_name)
                main_file = tool_dir / "main.txt"
                main_file.write_text(main_doc)
                logger.info(f"Processed main docs for {tool_name}")
            
            # Fetch API documentation
            api_content = await self.fetch_url(config['api_docs'])
            if api_content:
                api_doc = self.extract_content(api_content, tool_name)
                api_file = tool_dir / "api.txt"
                api_file.write_text(api_doc)
                logger.info(f"Processed API docs for {tool_name}")
            
            # Fetch GitHub documentation
            github_content = await self.fetch_url(config['github_docs'])
            if github_content:
                github_doc = self.extract_content(github_content, tool_name)
                github_file = tool_dir / "github.txt"
                github_file.write_text(github_doc)
                logger.info(f"Processed GitHub docs for {tool_name}")
            
        except Exception as e:
            logger.error(f"Error processing {tool_name}: {e}")

    async def fetch_all(self):
        """Fetch documentation for all configured tools"""
        async with aiohttp.ClientSession() as session:
            self.session = session
            tasks = []
            for tool_name, config in DOCS_CONFIG.items():
                task = self.process_tool(tool_name, config)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            logger.info("Completed fetching all documentation")

def setup_examples_directory(base_dir: Path):
    """Setup example files directory structure"""
    examples_dir = base_dir / "examples"
    examples_dir.mkdir(exist_ok=True)
    
    # Create subdirectories for each tool
    for tool in DOCS_CONFIG.keys():
        tool_dir = examples_dir / tool
        tool_dir.mkdir(exist_ok=True)
        
    return examples_dir

def main():
    # Setup directories
    base_dir = Path(__file__).parent.parent
    docs_dir = base_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    
    # Setup examples directory
    examples_dir = setup_examples_directory(base_dir)
    
    # Create fetcher and run
    fetcher = DocsFetcher(docs_dir)
    asyncio.run(fetcher.fetch_all())
    
    # Save configuration
    config_file = docs_dir / "docs_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(DOCS_CONFIG, f)
    
    logger.info(f"Documentation saved to {docs_dir}")
    logger.info(f"Example templates directory created at {examples_dir}")

if __name__ == "__main__":
    main()
