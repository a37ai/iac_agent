import requests
import os
from utils.general_helper_functions import load_config

config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
load_config(config_path)

def test_github_api():

    # Get GitHub token
    github_token = os.getenv("GIT_TOKEN")
    if not github_token:
        print("No GITHUB_TOKEN found in environment variables")
        return

    # Test parameters
    owner = "rkalahasty"
    repo = "terraformtest1"
    
    # Setup headers
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Test URL
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    
    print(f"\nTesting GitHub API:")
    print(f"URL: {url}")
    print(f"Token (first 10 chars): {github_token[:10]}...")
    print(f"Headers: {headers}")
    
    try:
        response = requests.get(url, headers=headers)
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            print("Success! First commit info:")
            commits = response.json()
            if commits:
                print(f"Latest commit SHA: {commits[0]['sha']}")
                print(f"Author: {commits[0]['commit']['author']['name']}")
                print(f"Message: {commits[0]['commit']['message']}")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_github_api()