from pathlib import Path
from typing import Dict

def _determine_file_type(file_path: Path) -> str:
    """Determine file type based on extension and name"""
    name = file_path.name.lower()
    ext = file_path.suffix.lower()
    
    # Infrastructure as Code
    if ext in ['.tf', '.tfvars']:
        return 'Terraform IaC'
    elif ext in ['.yaml', '.yml'] and any(x in name for x in ['kubernetes', 'k8s']):
        return 'Kubernetes Configuration'
    elif name == 'dockerfile' or ext == '.dockerfile':
        return 'Docker Configuration'
    elif ext in ['.yaml', '.yml'] and 'docker-compose' in name:
        return 'Docker Compose Configuration'
    
    # CI/CD
    elif ext in ['.yaml', '.yml'] and any(x in name for x in ['.github', 'gitlab-ci', 'azure-pipelines']):
        return 'CI/CD Pipeline Configuration'
    
    # Environment Configuration
    elif ext in ['.env', '.conf'] or 'config' in name:
        return 'Environment Configuration'
    
    # Standard Code Files
    elif ext == '.py':
        return 'Python Source'
    elif ext in ['.js', '.ts']:
        return 'JavaScript/TypeScript Source'
    elif ext == '.go':
        return 'Go Source'
    elif ext in ['.java', '.kt']:
        return 'Java/Kotlin Source'
    
    # Documentation
    elif ext in ['.md', '.rst']:
        return 'Documentation'
    
    return f'Generic {ext} file'

def _dict_to_tree_string(tree: Dict, prefix: str = "") -> str:
    """Convert dictionary tree to string representation"""
    result = []
    for key, value in tree.items():
        if isinstance(value, dict):
            result.append(f"{prefix}└── {key}/")
            result.append(_dict_to_tree_string(value, prefix + "    "))
        else:
            result.append(f"{prefix}└── {key}")
    return "\n".join(result)