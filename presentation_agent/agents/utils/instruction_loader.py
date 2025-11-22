"""
Helper function to load agent instructions from markdown files.
"""
from pathlib import Path


def load_instruction(agent_dir: Path, filename: str = "instructions.md") -> str:
    """
    Load agent instruction from a markdown file.
    
    Args:
        agent_dir: Path to the agent directory (e.g., Path(__file__).parent)
        filename: Name of the instruction file (default: "instructions.md")
    
    Returns:
        Instruction string from the file
    
    Raises:
        FileNotFoundError: If the instruction file doesn't exist
    """
    instruction_file = agent_dir / filename
    if not instruction_file.exists():
        raise FileNotFoundError(
            f"Instruction file not found: {instruction_file}\n"
            f"Expected location: {agent_dir}/{filename}"
        )
    
    with open(instruction_file, 'r', encoding='utf-8') as f:
        return f.read().strip()

