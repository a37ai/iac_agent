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
        "api_docs": "https://developer.hashicorp.com/terraform/plugin",
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
        "api_docs": "https://kubernetes.io/docs/reference/kubernetes-api/",
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
        self.executor = ThreadPoolExecutor(max_workers=5)
        # Get API token from environment
        self.terraform_token = os.getenv('TERRAFORM_REGISTRY_TOKEN')
        
    async def _get_registry_headers(self) -> Dict[str, str]:
        """Get headers for Terraform Registry API"""
        headers = {
            'User-Agent': 'Terraform-Docs-Fetcher/1.0',
            'Accept': 'application/json'
        }
        if self.terraform_token:
            headers['Authorization'] = f'Bearer {self.terraform_token}'
        return headers
        
    @sleep_and_retry
    @limits(calls=CALLS, period=RATE_LIMIT)
    async def fetch_url(self, url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Fetch content from URL with rate limiting"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:  # Too Many Requests
                        retry_after = int(response.headers.get('Retry-After', '60'))
                        logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                        await asyncio.sleep(retry_after)
                        return await self.fetch_url(url, headers)
                    else:
                        logger.error(f"Failed to fetch {url}: {response.status}")
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

    async def fetch_tool_docs(self, tool_name: str, config: dict, session: aiohttp.ClientSession) -> None:
        """Fetch documentation for a specific tool"""
        try:
            # Create tool directory
            tool_dir = self.output_dir / tool_name
            tool_dir.mkdir(exist_ok=True)
            
            # Fetch main documentation
            main_url = config['base_url']
            async with session.get(main_url) as response:
                if response.status == 200:
                    main_content = await response.text()
                    logger.info(f"Processed main docs for {tool_name}")
                    soup = BeautifulSoup(main_content, 'html.parser')
                    content = soup.get_text(strip=True, separator=' ')
                    doc_file = tool_dir / "main.txt"
                    doc_file.write_text(content)
            
            # Fetch API documentation
            api_url = config['api_docs']
            async with session.get(api_url) as response:
                if response.status == 200:
                    api_content = await response.text()
                    logger.info(f"Processed API docs for {tool_name}")
                    soup = BeautifulSoup(api_content, 'html.parser')
                    content = soup.get_text(strip=True, separator=' ')
                    doc_file = tool_dir / "api.txt"
                    doc_file.write_text(content)
                    
        except Exception as e:
            logger.error(f"Error processing {tool_name}: {e}")

    async def fetch_terraform_docs(self, session: aiohttp.ClientSession) -> None:
        """Fetch Terraform-specific documentation"""
        try:
            # Create terraform directory
            terraform_dir = self.output_dir / "terraform"
            terraform_dir.mkdir(exist_ok=True)
            
            # Fetch main Terraform documentation sections
            base_url = "https://developer.hashicorp.com/terraform"
            doc_sections = [
                "language/providers",
                "language/resources",
                "language/data-sources",
                "language/functions",
                "language/settings",
                "cli/commands"
            ]
            
            for section in doc_sections:
                url = f"{base_url}/{section}"
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"Processed Terraform docs for {section}")
                        soup = BeautifulSoup(content, 'html.parser')
                        text_content = soup.get_text(strip=True, separator=' ')
                        
                        # Save to file
                        section_name = section.replace('/', '_')
                        doc_file = terraform_dir / f"{section_name}.txt"
                        doc_file.write_text(text_content)
            
            # Fetch provider documentation from registry
            registry_base = "https://registry.terraform.io/v1/providers"
            registry_headers = await self._get_registry_headers()
            
            # Fetch AWS provider docs
            aws_versions_url = f"{registry_base}/hashicorp/aws/versions"
            async with session.get(aws_versions_url, headers=registry_headers) as response:
                if response.status == 200:
                    versions_data = await response.json()
                    if versions_data.get('versions'):
                        latest_version = versions_data['versions'][0]['version']
                        
                        # Fetch docs for latest version
                        aws_docs_url = f"{registry_base}/hashicorp/aws/{latest_version}/docs"
                        async with session.get(aws_docs_url, headers=registry_headers) as docs_response:
                            if docs_response.status == 200:
                                aws_docs = await docs_response.json()
                                for i, doc in enumerate(aws_docs):
                                    doc_file = terraform_dir / f"provider_aws_{i}.txt"
                                    doc_file.write_text(doc.get('content', ''))
                                    
        except Exception as e:
            logger.error(f"Error processing Terraform docs: {e}")

    async def fetch_all(self):
        """Fetch documentation for all configured tools"""
        # Process Terraform first
        async with aiohttp.ClientSession() as terraform_session:
            await self.fetch_terraform_docs(terraform_session)
        
        # Process other tools
        other_tools = {k: v for k, v in DOCS_CONFIG.items() if k != 'terraform'}
        for tool_name, config in other_tools.items():
            # Use a new session for each tool
            async with aiohttp.ClientSession() as tool_session:
                await self.fetch_tool_docs(tool_name, config, tool_session)
        
        logger.info("Completed fetching all documentation")

async def setup_examples_directory(base_dir: Path):
    """Setup example files directory structure"""
    examples_dir = base_dir / "examples"
    examples_dir.mkdir(exist_ok=True)
    
    # Create subdirectories for each tool
    for tool_name, config in DOCS_CONFIG.items():
        tool_dir = examples_dir / tool_name
        tool_dir.mkdir(exist_ok=True)
        
    logger.info(f"Example templates directory created at {examples_dir}")
    return examples_dir

async def main():
    """Main entry point"""
    try:
        # Setup directories
        base_dir = Path(__file__).parent.parent
        docs_dir = base_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        
        examples_dir = await setup_examples_directory(base_dir)
        
        # Initialize fetcher
        fetcher = DocsFetcher(docs_dir)
        await fetcher.fetch_all()
        
        logger.info(f"Documentation saved to {docs_dir}")
        logger.info(f"Example templates directory created at {examples_dir}")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
