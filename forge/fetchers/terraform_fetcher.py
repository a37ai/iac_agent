"""
Terraform documentation fetcher.
"""
import aiohttp
import logging
from typing import List, Dict
from bs4 import BeautifulSoup
import re
import json
from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

class TerraformFetcher(BaseFetcher):
    PROVIDER_URLS = {
        'aws': 'https://registry.terraform.io/providers/hashicorp/aws/latest/docs',
        'google': 'https://registry.terraform.io/providers/hashicorp/google/latest/docs',
        'azure': 'https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs',  # Use azurerm instead of azure
        'kubernetes': 'https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs'
    }
    
    REGISTRY_PROVIDERS = ['aws', 'google', 'azurerm', 'kubernetes']
    
    def __init__(self, api_url: str = None, auth_token: str = None, **kwargs):
        """Initialize Terraform fetcher"""
        super().__init__(api_url=api_url, auth_token=auth_token, **kwargs)
        self.api_url = api_url or "https://registry.terraform.io/v1"
    
    async def fetch_documentation(self) -> List[Dict]:
        """Fetch Terraform documentation from multiple sources"""
        docs = []
        
        try:
            # Fetch from registry
            registry_docs = await self._fetch_registry_docs()
            docs.extend(registry_docs)
            
            # Fetch from provider docs
            for provider, url in self.PROVIDER_URLS.items():
                provider_docs = await self._fetch_provider_docs(provider, url)
                docs.extend(provider_docs)
            
            # Fetch from HashiCorp docs
            hashicorp_docs = await self._fetch_hashicorp_docs()
            docs.extend(hashicorp_docs)
            
            # Fetch from Registry provider docs
            for provider in self.REGISTRY_PROVIDERS:
                registry_provider_docs = await self._fetch_registry_provider_docs(provider)
                docs.extend(registry_provider_docs)
            
            return docs
            
        except Exception as e:
            logger.error(f"Error fetching Terraform documentation: {e}")
            return []
    
    async def _fetch_registry_docs(self) -> List[Dict]:
        """Fetch documentation from Terraform Registry"""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
            
            # Fetch popular modules
            async with session.get(f"{self.api_url}/modules/popular") as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch registry docs: {response.status}")
                    return []
                
                data = await response.json()
                docs = []
                
                for module in data.get('modules', []):
                    # Get detailed module info
                    module_id = module.get('id')
                    if not module_id:
                        continue
                        
                    async with session.get(f"{self.api_url}/modules/{module_id}") as mod_response:
                        if mod_response.status != 200:
                            continue
                            
                        mod_data = await mod_response.json()
                        docs.append({
                            'version': mod_data.get('version', 'latest'),
                            'content_type': 'module',
                            'content': mod_data.get('readme_content', ''),
                            'metadata': {
                                'namespace': mod_data.get('namespace'),
                                'name': mod_data.get('name'),
                                'provider': mod_data.get('provider'),
                                'source': 'terraform_registry',
                                'downloads': mod_data.get('downloads'),
                                'verified': mod_data.get('verified', False)
                            }
                        })
                
                return docs
    
    async def _fetch_provider_docs(self, provider: str, base_url: str) -> List[Dict]:
        """Fetch provider documentation from Terraform Registry"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(base_url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {provider} provider docs: {response.status}")
                        return []
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    docs = []
                    
                    # Find main content
                    main_content = soup.find('div', {'class': 'content'}) or soup.find('main')
                    if not main_content:
                        return []
                    
                    # Process each section
                    for section in main_content.find_all(['section', 'div'], {'class': ['docs-content', 'content']}):
                        # Get title
                        title = section.find(['h1', 'h2', 'h3'])
                        if not title:
                            continue
                        
                        # Clean content
                        for tag in section.find_all(['script', 'style', 'nav']):
                            tag.decompose()
                        
                        content = section.get_text(separator='\n').strip()
                        if len(content) < 50:  # Skip very short sections
                            continue
                        
                        # Extract code examples
                        examples = []
                        for code in section.find_all('code'):
                            if code.get_text().strip():
                                examples.append(code.get_text().strip())
                        
                        # Extract resource type if present
                        resource_match = re.search(fr'{provider}_\w+', title.get_text(), re.IGNORECASE)
                        resource_type = resource_match.group(0).lower() if resource_match else None
                        
                        doc = {
                            'version': 'latest',
                            'content_type': 'resource' if resource_type else 'guide',
                            'content': content,
                            'metadata': {
                                'title': title.get_text().strip(),
                                'provider': provider,
                                'source': 'provider_docs',
                                'url': base_url
                            }
                        }
                        
                        if resource_type:
                            doc['metadata']['resource_type'] = resource_type
                        
                        if examples:
                            doc['examples'] = examples
                        
                        docs.append(doc)
                    
                    return docs
                    
            except Exception as e:
                logger.error(f"Error fetching {provider} provider docs: {e}")
                return []
    
    async def _fetch_hashicorp_docs(self) -> List[Dict]:
        """Fetch documentation from HashiCorp's website"""
        async with aiohttp.ClientSession() as session:
            docs = []
            
            # List of important Terraform doc pages
            urls = [
                "https://developer.hashicorp.com/terraform/docs",
                "https://developer.hashicorp.com/terraform/language",
                "https://developer.hashicorp.com/terraform/cli",
                "https://developer.hashicorp.com/terraform/internals"
            ]
            
            for url in urls:
                try:
                    async with session.get(url) as response:
                        if response.status != 200:
                            continue
                        
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Find main content sections
                        for section in soup.find_all(['section', 'article']):
                            title = section.find(['h1', 'h2', 'h3'])
                            if not title:
                                continue
                            
                            # Clean content
                            for tag in section.find_all(['script', 'style']):
                                tag.decompose()
                            
                            content = section.get_text(separator='\n').strip()
                            if len(content) < 50:  # Skip very short sections
                                continue
                            
                            docs.append({
                                'version': 'latest',
                                'content_type': 'guide',
                                'content': content,
                                'metadata': {
                                    'title': title.get_text().strip(),
                                    'source': 'hashicorp_docs',
                                    'url': url
                                }
                            })
                            
                except Exception as e:
                    logger.error(f"Error fetching HashiCorp docs from {url}: {e}")
            
            return docs
    
    async def _fetch_registry_provider_docs(self, provider: str) -> List[Dict]:
        """Fetch provider documentation from Terraform Registry"""
        async with aiohttp.ClientSession() as session:
            try:
                url = f"https://registry.terraform.io/v2/providers/{provider}"
                async with session.get(url) as response:
                    if response.status != 200:
                        return []
                    
                    data = await response.json()
                    docs = []
                    
                    # Get provider documentation
                    if 'docs' in data:
                        for doc in data['docs']:
                            docs.append({
                                'version': data.get('version', 'latest'),
                                'content_type': 'provider',
                                'content': doc.get('content', ''),
                                'metadata': {
                                    'title': doc.get('title'),
                                    'provider': provider,
                                    'source': 'registry_provider',
                                    'category': doc.get('category')
                                }
                            })
                    
                    return docs
                    
            except Exception as e:
                logger.error(f"Error fetching registry provider docs for {provider}: {e}")
                return []
    
    async def get_current_version(self) -> str:
        """Get current Terraform version"""
        async with aiohttp.ClientSession() as session:
            url = "https://checkpoint-api.hashicorp.com/v1/check/terraform"
            async with session.get(url) as response:
                if response.status != 200:
                    return "latest"
                data = await response.json()
                return data.get('current_version', 'latest')
