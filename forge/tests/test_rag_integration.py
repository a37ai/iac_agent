"""
Integration test for the complete RAG-enhanced code generation pipeline.
"""
import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from ..coders.rag_enhanced_coder import RAGEnhancedCoder

class TestRAGIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.docs_dir = Path(self.temp_dir) / "docs"
        self.docs_dir.mkdir()
        
        # Create test documentation
        self.terraform_doc = """
        # AWS ECS Cluster with Autoscaling
        
        To create an ECS cluster with autoscaling:
        
        1. Create the ECS cluster:
        ```hcl
        resource "aws_ecs_cluster" "main" {
          name = "my-ecs-cluster"
          capacity_providers = ["FARGATE", "FARGATE_SPOT"]
        }
        ```
        
        2. Set up autoscaling:
        ```hcl
        resource "aws_appautoscaling_target" "ecs_target" {
          max_capacity       = 4
          min_capacity       = 1
          resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.main.name}"
          scalable_dimension = "ecs:service:DesiredCount"
          service_namespace  = "ecs"
        }
        ```
        """
        
        # Write test documentation
        doc_path = self.docs_dir / "terraform_ecs.md"
        doc_path.write_text(self.terraform_doc)
        
        # Initialize coder
        self.coder = RAGEnhancedCoder()
        
        # Add documentation
        self.coder.add_documentation(
            doc_path=doc_path,
            tool_name="terraform",
            category="IaC"
        )

    async def test_code_generation(self):
        """Test the complete code generation pipeline"""
        # Test query about ECS
        query = "Create an AWS ECS cluster with autoscaling capabilities"
        response = await self.coder.get_response(query)
        
        # Verify response contains relevant information
        self.assertIn("aws_ecs_cluster", response.lower())
        self.assertIn("autoscaling", response.lower())
        
        # Test error handling
        query = "This is an invalid query that should still not crash"
        response = await self.coder.get_response(query)
        self.assertIsNotNone(response)

    def test_documentation_loading(self):
        """Test documentation is properly loaded"""
        # Save the index
        index_path = self.docs_dir / "index.json"
        self.coder.retriever.save_index(str(index_path))
        
        # Create new coder and load index
        new_coder = RAGEnhancedCoder()
        new_coder.retriever.load_index(str(index_path))
        
        # Verify documentation is loaded
        self.assertEqual(
            len(new_coder.retriever.doc_chunks),
            len(self.coder.retriever.doc_chunks)
        )

    def tearDown(self):
        # Cleanup
        import shutil
        shutil.rmtree(self.temp_dir)

def main():
    # Run async tests
    async def run_tests():
        test = TestRAGIntegration()
        test.setUp()
        try:
            await test.test_code_generation()
            test.test_documentation_loading()
        finally:
            test.tearDown()
    
    asyncio.run(run_tests())

if __name__ == '__main__':
    main()
