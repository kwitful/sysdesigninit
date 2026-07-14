import os

def read_file(filepath:str)->str:
    """Reads and returns the content of a file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError("The file {filepath}does not exist")
    
    with open(filepath,'r',encoding='utf-8') as file:
        return file.read()



