# Copy to config.py and fill in your values
# cp config.example.py config.py

OLLAMA_NODES = {
    'Node1': {'url': 'http://192.168.1.X:11434', 'ssh': 'user@192.168.1.X'},
    'Node2': {'url': 'http://192.168.1.Y:11434', 'ssh': 'user@192.168.1.Y'},
}

# For dashboard.py
OLLAMA_DASHBOARD_NODES = {
    'Node1 (.X)': 'http://192.168.1.X:11434',
    'Node2 (.Y)': 'http://192.168.1.Y:11434',
}

# For orchestrator.py
OLLAMA_URL = "http://192.168.1.X:11434/v1"

# For vision_rename.py
VISION_OLLAMA_URL = "http://192.168.1.X:11434/api/generate"
