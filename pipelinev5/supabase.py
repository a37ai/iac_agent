import os
from supabase import create_client, Client
import traceback

class Supabase:
    def __init__(self, access_token: str = None, refresh_token: str = None, user_auth = False):
        url: str = os.getenv("SUPABASE_URL", "")
        key: str = os.getenv("SUPABASE_KEY", "")
        
        if not url or not key:
            raise ValueError("Supabase URL or Key is not set in the environment variables.")

        try:    
            if user_auth:
                self.supabase: Client = create_client(url, key)
                # self.supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
        except Exception as e:
            traceback.print_exc()
            raise ValueError(f"Failed to initialize Supabase client: {str(e)}")
        
    def get_project_data(self, project_id: str):
        response = self.supabase.table("projects").select("*").eq("id", project_id).execute()
        data = response.data
        if not data:
            raise ValueError(f"No project data found for project {project_id}")
        if type(data) is list:
            return data[0]
        elif type(data) is dict:
            return data
        else:
            raise ValueError(f"Unexpected data type: {type(data)}")

    def set_aws_credentials(access_token: str = "", refresh_token: str = "", project_id: str = ""):
        # Retrieve variables from .env
        url: str = os.getenv("SUPABASE_URL") 
        key: str = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("Supabase URL or Key is not set in the environment variables.")

        try:
            supabase: Client = create_client(url, key)
            supabase.auth.set_session(access_token=access_token, refresh_token=refresh_token)
            
            # Execute the query
            response = supabase.table("projects").select("aws_access_key_id, aws_secret_access_key").eq("id", project_id).execute()
            
            if not response.data:
                raise ValueError(f"No AWS credentials found for project {project_id}")
                
            return response
            
        except Exception as e:
            raise ValueError(f"Failed to retrieve AWS credentials: {str(e)}")

    def update_project_data(self, project_id: str, codebase_understanding: dict) -> None:
        """Update project's codebase understanding in Supabase."""
        try:
            self.supabase.table("projects").update({
                "codebase_understanding": codebase_understanding
            }).eq("id", project_id).execute()
        except Exception as e:
            raise ValueError(f"Failed to update project data: {str(e)}")

    def get_integration_raw_data(self, integration_name: str, project_id: str):
        """
        Get raw data for a specific integration from the projects table.
        
        Args:
            integration_name: Name of the integration tool
            project_id: ID of the project
            
        Returns:
            Response object containing the data
            
        Raises:
            ValueError: If the query fails or returns invalid data
        """
        try:
            integration_column = f"{integration_name}_raw"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            
            if not response:
                print(f"Failed to retrieve {integration_name} data")
                return None
                
            return str(response.data)
            
        except Exception as e:
            raise ValueError(f"Error retrieving integration data: {str(e)}")
    
    def get_integration_summarized_data(self, integration_name: str, project_id: str):
        """
        Get summarized data for a specific integration from the projects table.
        
        Args:
            integration_name: Name of the integration tool
            project_id: ID of the project
            
        Returns:
            Response object containing the data
            
        Raises:
            ValueError: If the query fails or returns invalid data
        """
        try:
            integration_column = f"{integration_name}_summary"
            response = self.supabase.table("projects").select(integration_column).eq("id", project_id).execute()
            
            if not response:
                print(f"Failed to retrieve {integration_name} data")
                return None
                
            return str(response.data)
            
        except Exception as e:
            raise ValueError(f"Error retrieving integration data: {str(e)}")
