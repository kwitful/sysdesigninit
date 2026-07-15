import os
from typing import List, Dict, Any

def read_file(filepath:str, start_line: int = 1, limit: int = 5000)->Dict[str, Any]:
    """Reads the content of a file. Limit exists to prevent token loss.

    Args:
        filepath: Path to the file.
        start_limit: 1-indexed line to start from.
        limit: maximum lines to return
    
    """