"""
AGENTS.md reader tool for providing context to AI agents
"""
import os
from typing import Dict, Optional, List
from pathlib import Path
from langchain_core.tools import tool
import re

class AgentsMDReader:
    """Reads and parses AGENTS.md files for agent context"""
    
    def __init__(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = Path(workspace_dir)
    
    def find_agents_md(self, directory: Optional[Path] = None) -> Optional[Path]:
        """Find the nearest AGENTS.md file in directory tree"""
        if directory is None:
            directory = self.workspace_dir
        
        current = Path(directory).resolve()
        
        # Check current directory and parents
        while current != current.parent:
            agents_md = current / "AGENTS.md"
            if agents_md.exists():
                return agents_md
            current = current.parent
        
        return None
    
    def parse_agents_md(self, content: str) -> Dict[str, str]:
        """Parse AGENTS.md content into sections"""
        sections = {}
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            # Check if line is a header
            if line.startswith('#'):
                # Save previous section if exists
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = line.lstrip('#').strip()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def get_context(self, task: str, directory: Optional[str] = None) -> Dict[str, any]:
        """Get relevant context for a task"""
        agents_md = self.find_agents_md(directory)
        
        if not agents_md:
            return {
                "found": False,
                "message": "No AGENTS.md file found in directory tree"
            }
        
        with open(agents_md, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sections = self.parse_agents_md(content)
        
        # Find relevant sections based on task keywords
        relevant_sections = self._find_relevant_sections(task, sections)
        
        return {
            "found": True,
            "file_path": str(agents_md),
            "all_sections": list(sections.keys()),
            "relevant_sections": relevant_sections,
            "full_content": sections
        }
    
    def _find_relevant_sections(self, task: str, sections: Dict[str, str]) -> Dict[str, str]:
        """Find sections relevant to the task"""
        task_lower = task.lower()
        relevant = {}
        
        # Keywords to section mapping
        keyword_map = {
            'test': ['Testing Instructions', 'Test', 'QA'],
            'deploy': ['Deployment', 'Deploy', 'CI/CD'],
            'review': ['Code Style Guidelines', 'PR Instructions', 'Review'],
            'setup': ['Dev Environment Setup', 'Setup', 'Installation'],
            'api': ['API', 'Endpoints', 'REST'],
            'security': ['Security', 'Auth', 'Permissions'],
            'debug': ['Error Handling', 'Debug', 'Troubleshooting']
        }
        
        for keyword, section_names in keyword_map.items():
            if keyword in task_lower:
                for section_name in section_names:
                    for key, value in sections.items():
                        if section_name.lower() in key.lower():
                            relevant[key] = value
        
        # Always include project overview if exists
        for key, value in sections.items():
            if 'overview' in key.lower() or 'about' in key.lower():
                relevant[key] = value
                
        return relevant

# Create tool functions for LangChain
@tool
def read_agents_md(directory: str = "./workspace_repo") -> str:
    """
    Read and parse AGENTS.md file from the specified directory or its parents.
    Returns structured information about project conventions and guidelines.
    
    Args:
        directory: Directory to start searching for AGENTS.md
        
    Returns:
        Parsed AGENTS.md content with sections
    """
    reader = AgentsMDReader()
    result = reader.get_context("", directory)
    
    if not result["found"]:
        return "No AGENTS.md file found. Consider creating one for better agent guidance."
    
    return f"""
AGENTS.md found at: {result['file_path']}

Available sections:
{', '.join(result['all_sections'])}

To get specific section, use get_agents_md_section tool.
"""

@tool
def get_agents_md_section(section_name: str, directory: str = "./workspace_repo") -> str:
    """
    Get a specific section from AGENTS.md file.
    
    Args:
        section_name: Name of the section to retrieve
        directory: Directory to start searching for AGENTS.md
        
    Returns:
        Content of the specified section
    """
    reader = AgentsMDReader()
    result = reader.get_context("", directory)
    
    if not result["found"]:
        return "No AGENTS.md file found."
    
    for key, value in result["full_content"].items():
        if section_name.lower() in key.lower():
            return f"Section: {key}\n\n{value}"
    
    return f"Section '{section_name}' not found. Available sections: {', '.join(result['all_sections'])}"

@tool
def get_task_context(task: str, directory: str = "./workspace_repo") -> str:
    """
    Get relevant AGENTS.md context for a specific task.
    
    Args:
        task: Description of the task to get context for
        directory: Directory to start searching for AGENTS.md
        
    Returns:
        Relevant sections from AGENTS.md for the task
    """
    reader = AgentsMDReader()
    result = reader.get_context(task, directory)
    
    if not result["found"]:
        return "No AGENTS.md file found. Working without additional context."
    
    output = [f"AGENTS.md Context for task: {task}\n"]
    
    if result["relevant_sections"]:
        for section, content in result["relevant_sections"].items():
            output.append(f"\n## {section}")
            output.append(content)
    else:
        output.append("\nNo specific sections found for this task.")
        output.append("Consider checking the full AGENTS.md file for guidance.")
    
    return '\n'.join(output)

# Export tools
agents_md_tools = [read_agents_md, get_agents_md_section, get_task_context]
