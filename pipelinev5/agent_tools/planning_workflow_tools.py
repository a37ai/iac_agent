import json
import datetime
import os
from states.state import Question

def get_answer_from_cli(question: Question) -> str:
    """Prompt the user for an answer via CLI."""
    print(f"\nQuestion: {question.question}")
    print(f"Context: {question.context}")
    print(f"Default: {question.default_answer}")
    user_input = input("\nYour answer (press Enter to use default): ").strip()
    return user_input if user_input else question.default_answer
