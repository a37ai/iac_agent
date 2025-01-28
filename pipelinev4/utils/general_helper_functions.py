import logging
import yaml
import os
from typing import Optional

# for loading configs to environment variables
def load_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
        for key, value in config.items():
            os.environ[key] = value


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
