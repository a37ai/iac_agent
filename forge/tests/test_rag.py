"""
Test suite for the RAG-based documentation retrieval system.
"""
import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
from ..rag_retriever import DevOpsRetriever, DocChunk

class TestDevOpsRetriever(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test docs
        self.temp_dir = tempfile.mkdtemp()
        self.retriever = DevOpsRetriever(docs_dir=self.temp_dir)
        
        # Sample documentation
        self.terraform_doc = """
        resource "aws_ecs_cluster" "main" {
          name = "my-ecs-cluster"
          
          setting {
            name  = "containerInsights"
            value = "enabled"
          }
        }
        
        This creates an Amazon ECS cluster with Container Insights enabled.
        The cluster can be used to run containerized applications.
        """
        
        self.k8s_doc = """
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: nginx-deployment
        spec:
          replicas: 3
          
        This creates a Kubernetes deployment running 3 replicas of nginx.
        The deployment ensures the desired number of pods are running.
        """

    def test_chunking(self):
        """Test document chunking functionality"""
        chunks = self.retriever._chunk_text(self.terraform_doc)
        self.assertTrue(len(chunks) > 0)
        # Verify chunks have reasonable size
        for chunk in chunks:
            self.assertTrue(len(chunk.split()) <= self.retriever.chunk_size)

    def test_add_documentation(self):
        """Test adding documentation"""
        self.retriever.add_documentation(
            content=self.terraform_doc,
            tool_name="terraform",
            category="IaC",
            source="test"
        )
        self.assertTrue(len(self.retriever.doc_chunks) > 0)
        # Verify embeddings were created
        self.assertIsNotNone(self.retriever.doc_chunks[0].embedding)

    def test_retrieval(self):
        """Test document retrieval"""
        # Add both documents
        self.retriever.add_documentation(
            content=self.terraform_doc,
            tool_name="terraform",
            category="IaC",
            source="test"
        )
        self.retriever.add_documentation(
            content=self.k8s_doc,
            tool_name="kubernetes",
            category="Container Orchestration",
            source="test"
        )
        
        # Test ECS-related query
        ecs_results = self.retriever.retrieve("How do I create an ECS cluster?")
        self.assertTrue(any("ecs" in chunk.content.lower() for chunk, _ in ecs_results))
        
        # Test K8s-related query
        k8s_results = self.retriever.retrieve("How do I create a Kubernetes deployment?")
        self.assertTrue(any("deployment" in chunk.content.lower() for chunk, _ in k8s_results))

    def test_save_load_index(self):
        """Test saving and loading the index"""
        # Add documentation
        self.retriever.add_documentation(
            content=self.terraform_doc,
            tool_name="terraform",
            category="IaC",
            source="test"
        )
        
        # Save index
        index_path = Path(self.temp_dir) / "test_index.json"
        self.retriever.save_index(str(index_path))
        
        # Create new retriever and load index
        new_retriever = DevOpsRetriever(docs_dir=self.temp_dir)
        new_retriever.load_index(str(index_path))
        
        # Verify loaded chunks match original
        self.assertEqual(len(new_retriever.doc_chunks), len(self.retriever.doc_chunks))
        for orig_chunk, loaded_chunk in zip(self.retriever.doc_chunks, new_retriever.doc_chunks):
            self.assertEqual(orig_chunk.content, loaded_chunk.content)
            self.assertEqual(orig_chunk.tool_name, loaded_chunk.tool_name)
            np.testing.assert_array_almost_equal(orig_chunk.embedding, loaded_chunk.embedding)

    def test_empty_retriever(self):
        """Test behavior with no documents"""
        results = self.retriever.retrieve("test query")
        self.assertEqual(len(results), 0)

    def test_chunk_overlap(self):
        """Test chunk overlapping"""
        long_doc = "\n".join(["Line " + str(i) for i in range(100)])
        chunks = self.retriever._chunk_text(long_doc)
        
        # Check that consecutive chunks have some overlap
        if len(chunks) > 1:
            chunk1_lines = set(chunks[0].split('\n'))
            chunk2_lines = set(chunks[1].split('\n'))
            overlap = chunk1_lines.intersection(chunk2_lines)
            self.assertTrue(len(overlap) > 0)

    def tearDown(self):
        # Cleanup temporary directory
        import shutil
        shutil.rmtree(self.temp_dir)

if __name__ == '__main__':
    unittest.main()
