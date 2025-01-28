from states.state import EditRequest

def get_edit_request_from_cli() -> EditRequest:
    """Get edit request details from CLI interaction."""
    print("\nWhat changes would you like to make to the plan?")
    print("(Type 'done' to finish replanning)")
    request = input("Enter your edit request: ").strip()
    
    if request.lower() == 'done':
        return None
        
    print("\nWould you like to provide a rationale for this edit? (optional, press Enter to skip)")
    rationale = input("Enter rationale: ").strip() or None
    
    return EditRequest(
        request=request,
        rationale=rationale
    )