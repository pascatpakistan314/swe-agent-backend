# Enhanced SWE Agent - Terminal Control Edition

🚀 **Enhanced Linear SWE Agent with Parallel Execution and Terminal Control**

This enhanced version of the SWE Agent addresses the critical issues with terminal setup and project control that were preventing proper dependency installation and project initialization.

## 🎯 Key Improvements

### ✅ **Fixed Issues**
- **Terminal Control**: Full terminal session management and command execution
- **Dependency Installation**: Automatic detection and installation of project dependencies
- **Environment Setup**: Proper workspace initialization and environment configuration
- **Linear Execution**: Predictable, step-by-step execution flow
- **Parallel Capabilities**: Optional parallel task execution for improved performance

### 🔧 **New Features**
- **Enhanced Terminal Integration**: Real terminal sessions with proper command execution
- **Multi-Language Support**: Python, Node.js, and generic project detection
- **Robust Error Handling**: Better error reporting and recovery
- **Execution Logging**: Detailed logs of all phases and operations
- **Flexible Execution Modes**: Sequential or parallel execution
- **Backward Compatibility**: Works with existing SWE components

## 📋 **Architecture Overview**

```
Enhanced SWE Agent Flow:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Initialization │ -> │ Environment      │ -> │ Dependencies    │
│  & Terminal     │    │ Setup            │    │ Installation    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                       │
         v                        v                       v
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Architecture   │ -> │ Implementation   │ -> │ Testing &       │
│  Planning       │    │ (Sequential/     │    │ Finalization    │
│                 │    │  Parallel)       │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 🚀 **Quick Start**

### 1. Basic Usage (CLI)

```bash
# Simple task execution
python enhanced_cli.py "Create a web scraper for quotes from quotes.toscrape.com"

# With parallel execution
python enhanced_cli.py "Build a REST API with FastAPI" --parallel

# Custom workspace
python enhanced_cli.py "Create data analysis tool" --workspace /path/to/project

# Debug mode
python enhanced_cli.py "Build a chatbot" --debug
```

### 2. Programmatic Usage

```python
from agent.integrated_graph import run_integrated_swe_agent, ExecutionMode

# Run with sequential execution
result = run_integrated_swe_agent(
    task_description="Create a simple web scraper",
    workspace_dir="./my_project",
    execution_mode=ExecutionMode.SEQUENTIAL
)

print(f"Status: {result['final_status']}")
```

### 3. Using Enhanced Graph API

```python
from agent.graph import run_enhanced_agent

# Convenient wrapper function
result = run_enhanced_agent(
    task_description="Build a calculator app",
    workspace_dir="./calculator_project",
    parallel=True
)
```

## 🔧 **Configuration Options**

### Execution Modes
- **Sequential**: Tasks executed one after another (safer, more predictable)
- **Parallel**: Tasks executed concurrently where possible (faster)

### Project Types Supported
- **Python Projects**: `requirements.txt`, `setup.py`, `pyproject.toml`
- **Node.js Projects**: `package.json`, `npm` dependencies
- **Generic Projects**: Automatic basic setup with common tools

### Terminal Features
- **Session Management**: Multiple terminal sessions
- **Command Execution**: Real command execution with output capture
- **Directory Navigation**: Proper working directory management
- **Cross-Platform**: Windows (PowerShell/CMD) and Unix (Bash) support

## 📊 **Execution Phases**

1. **Initialization**: Set up agent and validate inputs
2. **Environment Setup**: Create workspace and terminal sessions
3. **Dependency Management**: Install required dependencies
4. **Architecture Planning**: Research and create implementation plan
5. **Implementation**: Execute the plan (sequential or parallel)
6. **Testing**: Run available tests and verification
7. **Finalization**: Clean up and generate summary

## 🧪 **Testing**

Run the test suite to verify everything works:

```bash
python test_enhanced_agent.py
```

The test suite includes:
- Terminal integration testing
- Component import verification
- Workspace setup testing
- Basic agent execution testing

## 📁 **Project Structure**

```
swe-agent/
├── agent/
│   ├── enhanced_linear_agent.py      # Core enhanced agent
│   ├── integrated_graph.py           # Integration layer
│   ├── graph.py                      # Updated main graph
│   ├── tools/
│   │   └── terminal.py               # Terminal integration tools
│   ├── architect/                    # Existing architect component
│   ├── developer/                    # Existing developer component
│   └── common/                       # Shared entities
├── enhanced_cli.py                   # Command-line interface
├── test_enhanced_agent.py            # Test suite
└── README_ENHANCED.md                # This documentation
```

## 🔍 **Debugging**

### Enable Debug Mode
```bash
python enhanced_cli.py "your task" --debug
```

### Check Terminal Sessions
```python
from agent.tools.terminal import get_terminal_manager

manager = get_terminal_manager()
sessions = manager.list_sessions()
print(sessions)
```

### View Execution Log
```python
# After running the agent
result = run_integrated_swe_agent("task description")
for log_entry in result.get('execution_log', []):
    print(f"{log_entry['phase']}: {log_entry['status']}")
```

## 🚨 **Troubleshooting**

### Common Issues

1. **"Terminal not working"**
   - Ensure you have proper shell access (PowerShell on Windows, Bash on Unix)
   - Check that the workspace directory is accessible

2. **"Dependencies not installing"**
   - Verify you have pip/npm installed and accessible
   - Check network connectivity
   - Look at the execution log for detailed error messages

3. **"Agent not responding"**
   - Check your ANTHROPIC_API_KEY environment variable
   - Ensure you have sufficient API credits
   - Try with debug mode enabled

4. **"Import errors"**
   - Ensure all required dependencies are installed: `pip install -r requirements.txt`
   - Check Python path configuration

### Environment Variables Required

```bash
# Required
ANTHROPIC_API_KEY=your_api_key_here

# Optional
LANGSMITH_API_KEY=your_langsmith_key_here  # For tracing
LANGSMITH_TRACING=true                     # Enable LangSmith
```

## 📈 **Performance Tips**

1. **Use Sequential Mode** for complex tasks requiring careful coordination
2. **Use Parallel Mode** for independent tasks that can run simultaneously  
3. **Specify Workspace** to avoid conflicts with existing projects
4. **Monitor Terminal Sessions** in debug mode to see real-time execution
5. **Check Execution Logs** to understand performance bottlenecks

## 🔄 **Migration from Original SWE Agent**

### Backward Compatibility
The enhanced agent maintains full backward compatibility:

```python
# Old way (still works)
from agent.graph import swe_agent
result = swe_agent.invoke({"task_description": "your task"})

# New enhanced way (recommended)
from agent.graph import run_enhanced_agent
result = run_enhanced_agent("your task", parallel=True)
```

### Key Differences
- **Terminal Control**: Enhanced version has real terminal access
- **Dependency Management**: Automatic detection and installation
- **Linear Flow**: Predictable execution phases
- **Better Logging**: Detailed execution tracking
- **Error Handling**: More robust error recovery

## 🎉 **Example Usage**

### Web Scraper Example
```bash
python enhanced_cli.py "Create a web scraper that extracts quotes from quotes.toscrape.com and saves them to CSV with proper error handling and rate limiting"
```

### API Development Example  
```bash
python enhanced_cli.py "Build a FastAPI REST API for managing a todo list with CRUD operations, SQLite database, and proper documentation" --parallel --workspace ./todo_api
```

### Data Analysis Example
```bash
python enhanced_cli.py "Create a data analysis tool that reads CSV files, performs statistical analysis, and generates visualizations using matplotlib and pandas" --workspace ./data_tool
```

## 📝 **License**

This enhanced version maintains the same license as the original SWE Agent project.

## 🤝 **Contributing**

1. Test your changes with `python test_enhanced_agent.py`
2. Ensure backward compatibility is maintained
3. Add tests for new functionality
4. Update documentation as needed

---

**🚀 Enhanced SWE Agent - Now with proper terminal control and linear execution!**

*No more embarrassing failures with dependency installation or project setup.*
