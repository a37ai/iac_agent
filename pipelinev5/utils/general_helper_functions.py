import logging
import yaml
import os
from typing import Optional
from typing import Any, Dict, List
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage

# for loading configs to environment variables
def load_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
        for key, value in config.items():
            os.environ[key] = value


# for checking if an attribute of the state dict has content.
def check_for_content(var):
    if var:
        try:
            var = var.content
            return var.content
        except:
            return var
    else:
        var

def configure_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging with a predefined format and level, and return a logger instance.

    Args:
        name (Optional[str]): The name for the logger. Defaults to None, which uses the root logger.
        level (int): The logging level. Defaults to logging.INFO.

    Returns:
        logging.Logger: A configured logger instance.
    """
    # Apply basic configuration for the logging system
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # Get and return a logger with the specified name or root logger if name is None
    return logging.getLogger(name)

def serialize_message(message):
    """Convert a message to a JSON-serializable format."""
    if hasattr(message, 'to_dict'):
        return message.to_dict()
    elif isinstance(message, dict):
        return {k: serialize_message(v) for k, v in message.items()}
    elif isinstance(message, list):
        return [serialize_message(item) for item in message]
    elif hasattr(message, 'content'):
        return {
            "content": message.content,
            "type": message.__class__.__name__
        }
    return message
