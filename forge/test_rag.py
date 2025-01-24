"""
Test script for the RAG documentation system.
"""
import asyncio
import os
from pathlib import Path
import pytest
from forge.rag_coder import RAGCodeGenerator
from forge.rag_llm import RAGLLMPipeline
from forge.rag_retriever import RAGRetriever

@pytest.mark.asyncio
async def test_documentation():
    """Test the documentation generation pipeline"""
    print("\nTesting general query...")
    
    # Initialize components
    retriever = RAGRetriever()
    pipeline = RAGLLMPipeline(retriever=retriever)
    generator = RAGCodeGenerator(pipeline=pipeline)
    
    # Add some sample documentation
    docs_dir = Path("docs")
    
    # Create sample Terraform documentation
    terraform_doc = """---
tool: terraform
category: iac
version: 1.0.0
topics:
  - state management
  - backends
  - s3
---
# Terraform S3 Backend Configuration

## Common Issues and Solutions

### Error: Failed to load state
When you encounter the error "Failed to load state: RequestError: send request failed", it usually indicates one of these issues:

1. AWS credentials are not properly configured
2. S3 bucket permissions are incorrect
3. Network connectivity issues

To resolve this:

```error
Error: Failed to load state: RequestError: send request failed
caused by: Get "https://my-bucket.s3.amazonaws.com/": dial tcp: lookup my-bucket.s3.amazonaws.com: no such host
```

Fix:
1. Verify AWS credentials:
```bash
aws configure list
aws sts get-caller-identity
```

2. Check S3 bucket permissions:
```hcl
terraform {
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "state/terraform.tfstate"
    region = "us-west-2"
  }
}
```

3. Ensure proper network connectivity to AWS S3.
"""
    
    terraform_doc_path = docs_dir / "iac" / "terraform" / "s3_backend.md"
    terraform_doc_path.parent.mkdir(parents=True, exist_ok=True)
    terraform_doc_path.write_text(terraform_doc)
    
    # Ingest documentation
    print("Ingesting documentation...")
    retriever.ingest_documentation()
    
    # Test general query
    query = "How do I set up an S3 backend for Terraform?"
    response = await pipeline.process_query(query)
    print("\nQuery Response:")
    print(f"Tool: {response['tool']}")
    print(f"Category: {response['category']}")
    print(f"Answer: {response['answer']}")
    
    # Test error query
    print("\nTesting error query...")
    error_query = "I'm getting an error: NoSuchBucket when trying to use S3 backend"
    error_response = await pipeline.process_query(error_query)
    print("\nError Response:")
    print(f"Tool: {error_response['tool']}")
    print(f"Category: {error_response['category']}")
    print(f"Answer: {error_response['answer']}")

    # Test multi-tool query
    print("\nTesting multi-tool query...")
    multi_query = "How do I set up monitoring for my kubernetes cluster using prometheus?"
    multi_response = await pipeline.process_query(multi_query)
    print("\nMulti-tool Response:")
    print(f"Tool: {multi_response['tool']}")
    print(f"Category: {multi_response['category']}")
    print(f"Answer: {multi_response['answer']}")

    # Test complex workflow query
    print("\nTesting complex workflow query...")
    workflow_query = "How do I set up a CI/CD pipeline that builds a Docker container and deploys it to AWS ECS?"
    workflow_response = await pipeline.process_query(workflow_query)
    print("\nWorkflow Response:")
    print(f"Tool: {workflow_response['tool']}")
    print(f"Category: {workflow_response['category']}")
    print(f"Answer: {workflow_response['answer']}")

if __name__ == "__main__":
    asyncio.run(test_documentation())