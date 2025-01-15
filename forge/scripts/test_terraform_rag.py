"""
Simple script to test Terraform RAG enhancement.
"""
from forge.rag_llm import AiderEnhancer

def main():
    print("Terraform Documentation Enhancement Test")
    print("-" * 50)
    
    enhancer = AiderEnhancer()
    
    while True:
        print("\nEnter a query about Terraform (or 'quit' to exit)")
        query = input("> ")
        
        if query.lower() == 'quit':
            break
        
        print("\nOptional: Enter any error message (or press Enter to skip)")
        error = input("> ")
        error_context = error if error.strip() else None
        
        print("\nGenerating enhanced prompt...")
        enhanced_prompt = enhancer.enhance_prompt(query, error_context)
        
        print("\nEnhanced Prompt:")
        print("-" * 50)
        print(enhanced_prompt)
        print("-" * 50)

if __name__ == '__main__':
    main()
