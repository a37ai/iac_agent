from typing import List
import tiktoken

class TokenCounter:
    def __init__(self):
        self.encoder = tiktoken.encoding_for_model("gpt-4o")
        
    def count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))
