"""
Terminal integration for SWE-Agent - provides shell access like Devin
"""
import os
import subprocess
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
import time
from langchain_core.tools import tool
import platform

try:
    import pty
    import select
    import termios
    import tty
except ImportError:
    # These modules are not available on Windows
    pty = None
    select = None 
    termios = None
    tty = None

class TerminalSession:
    """Interactive terminal session manager"""
    
    def _init_(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.sessions = {}
        self.is_windows = platform.system() == "Windows"
    
    def create_session(self, session_id: str = "main") -> Dict[str, Any]:
        """Create a new terminal session"""
        
        # Ensure workspace exists to avoid FileNotFoundError in Popen(cwd=...)
        try:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Could not create workspace dir '{self.workspace_dir}': {e}")

        if self.is_windows:
            # Windows: Use subprocess with cmd or PowerShell
            try:
                process = subprocess.Popen(
                    ["powershell.exe", "-NoLogo", "-NoProfile"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(self.workspace_dir),
                    text=True,
                    shell=False
                )
            except Exception as e:
                raise RuntimeError(f"Failed to start PowerShell in '{self.workspace_dir}': {e}")
            master = None
        else:
            # Unix: Use pty for proper terminal emulation
            if pty is None:
                raise RuntimeError("pty module not available for Unix terminal emulation")
            master, slave = pty.openpty()
            process = subprocess.Popen(
                ["/bin/bash"],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                cwd=str(self.workspace_dir),
                preexec_fn=os.setsid
            )
            os.close(slave)
        
        self.sessions[session_id] = {
            "process": process,
            "master": master if not self.is_windows else None,
            "history": [],
            "cwd": str(self.workspace_dir)
        }
        
        return {
            "session_id": session_id,
            "status": "created",
            "pid": process.pid
        }
    
    def execute_command(self, command: str, session_id: str = "main", 
                       timeout: int = 30) -> Dict[str, Any]:
        """Execute a command in a terminal session"""
        
        if session_id not in self.sessions:
            self.create_session(session_id)
        
        session = self.sessions[session_id]
        process = session["process"]
        
        # Add to history
        session["history"].append(command)
        
        if self.is_windows:
            return self._execute_windows(process, command, timeout)
        else:
            return self._execute_unix(session, command, timeout)
    
    def _execute_windows(self, process, command: str, timeout: int) -> Dict[str, Any]:
        """Execute command on Windows"""
        try:
            # Append echo of the last exit code so we can parse it
            wrapped = f"{command}\n$code=$LASTEXITCODE; Write-Output \"_EXIT_CODE_=$code\"\n"
            process.stdin.write(wrapped)
            process.stdin.flush()
            
            # Read output with timeout
            import threading
            output = []
            error = []
            
            def read_output():
                line = process.stdout.readline()
                if line:
                    output.append(line)
            
            def read_error():
                line = process.stderr.readline()
                if line:
                    error.append(line)
            
            # Read with timeout
            timer = threading.Timer(timeout, lambda: None)
            timer.start()
            
            while timer.is_alive():
                read_output()
                read_error()
                if not process.poll() is None:
                    break
            
            timer.cancel()
            
            full_out = ''.join(output)
            full_err = ''.join(error)
            exit_code = 0
            for line in reversed(full_out.splitlines()):
                if line.strip().startswith("_EXIT_CODE_="):
                    try:
                        exit_code = int(line.strip().split("=", 1)[1])
                    except:
                        exit_code = 1
                    break
            success = (exit_code == 0)
            return {
                "success": success,
                "output": full_out,
                "error": full_err,
                "command": command,
                "exit_code": exit_code,
            }
            
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "command": command,
                "exit_code": 1,
            }
    
    def _execute_unix(self, session, command: str, timeout: int) -> Dict[str, Any]:
        """Execute command on Unix systems"""
        master = session["master"]
        
        try:
            # Send command
            os.write(master, (command + "\n").encode())
            
            # Read output with timeout
            output = []
            start_time = time.time()
            
            while True:
                # Check for timeout
                if (time.time() - start_time) > timeout:
                    break
                
                # Check if data is available (only if select is available)
                if select:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            data = os.read(master, 1024).decode('utf-8', errors='replace')
                            output.append(data)
                            
                            # Check for command prompt (indicates command finished)
                            if data.endswith('$ ') or data.endswith('# '):
                                break
                        except:
                            break
                else:
                    # Fallback without select
                    try:
                        data = os.read(master, 1024).decode('utf-8', errors='replace')
                        output.append(data)
                    except:
                        break
            
            return {
                "success": True,
                "output": ''.join(output),
                "error": "",
                "command": command
            }
            
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "command": command
            }
    
    def get_session_info(self, session_id: str = "main") -> Dict[str, Any]:
        """Get information about a session"""
        
        if session_id not in self.sessions:
            return {
                "exists": False,
                "session_id": session_id
            }
        
        session = self.sessions[session_id]
        process = session["process"]
        
        return {
            "exists": True,
            "session_id": session_id,
            "pid": process.pid,
            "alive": process.poll() is None,
            "cwd": session["cwd"],
            "history_length": len(session["history"])
        }
    
    def close_session(self, session_id: str = "main"):
        """Close a terminal session"""
        
        if session_id in self.sessions:
            session = self.sessions[session_id]
            process = session["process"]
            
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            
            if not self.is_windows and session["master"]:
                os.close(session["master"])
            
            del self.sessions[session_id]
            
            return {"status": "closed", "session_id": session_id}
        
        return {"status": "not_found", "session_id": session_id}
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions"""
        
        sessions = []
        for session_id in self.sessions:
            info = self.get_session_info(session_id)
            sessions.append(info)
        
        return sessions


# Global terminal manager
_terminal_manager = None

def get_terminal_manager() -> TerminalSession:
    """Get or create global terminal manager"""
    global _terminal_manager
    if _terminal_manager is None:
        _terminal_manager = TerminalSession()
    return _terminal_manager


# Helper function for cross-platform commands
def get_cross_platform_command(command: str) -> str:
    """Convert commands to work cross-platform"""
    is_windows = platform.system() == "Windows"
    
    # Handle ls command
    if command.startswith("ls "):
        if is_windows:
            # Convert ls flags to PowerShell Get-ChildItem
            if "-la" in command or "-al" in command:
                return command.replace("ls -la", "Get-ChildItem -Force").replace("ls -al", "Get-ChildItem -Force")
            elif "-l" in command:
                return command.replace("ls -l", "Get-ChildItem")
            else:
                return command.replace("ls", "Get-ChildItem")
    
    return command


# LangChain tools
@tool
def terminal_execute(command: str, session_id: str = "main") -> str:
    """
    Execute a command in an interactive terminal session.
    
    Args:
        command: The command to execute
        session_id: Terminal session ID (default: "main")
        
    Returns:
        Command output and status
    """
    try:
        # Convert command for cross-platform compatibility
        cross_platform_command = get_cross_platform_command(command)
        
        manager = get_terminal_manager()
        result = manager.execute_command(cross_platform_command, session_id)
        output = [f"$ {command}"]
        if result.get("output"):
            output.append(result["output"])
        if result.get("error"):
            output.append(f"Error: {result['error']}")
        # reflect success/exit code if present
        if "success" in result:
            output.append(f"(success={result['success']})")
        if "exit_code" in result:
            output.append(f"(exit_code={result['exit_code']})")
        output.append(f"(session={session_id})")
        return '\n'.join(output)
    except Exception as e:
        # Never let exceptions bubble to the tool node — return a readable error
        return f"$ {command}\nError running terminal tool: {e}\n(session={session_id})"

@tool
def terminal_new_session(session_id: str) -> str:
    """
    Create a new terminal session.
    
    Args:
        session_id: Unique ID for the session
        
    Returns:
        Session creation status
    """
    try:
        manager = get_terminal_manager()
        result = manager.create_session(session_id)
        return f"Terminal session '{session_id}' created with PID {result['pid']}"
    except Exception as e:
        return f"Error creating terminal session '{session_id}': {e}"

@tool
def terminal_list_sessions() -> str:
    """
    List all active terminal sessions.
    
    Returns:
        List of active sessions with their status
    """
    try:
        manager = get_terminal_manager()
        sessions = manager.list_sessions()
        
        if not sessions:
            return "No active terminal sessions"
        
        output = ["Active Terminal Sessions:"]
        for session in sessions:
            status = "alive" if session["alive"] else "dead"
            output.append(f"  - {session['session_id']}: PID {session['pid']} ({status})")
            output.append(f"    CWD: {session['cwd']}")
            output.append(f"    History: {session['history_length']} commands")
        
        return '\n'.join(output)
    except Exception as e:
        return f"Error listing terminal sessions: {e}"

@tool
def terminal_close_session(session_id: str = "main") -> str:
    """
    Close a terminal session.
    
    Args:
        session_id: Session ID to close
        
    Returns:
        Closure status
    """
    try:
        manager = get_terminal_manager()
        result = manager.close_session(session_id)
        
        if result["status"] == "closed":
            return f"Terminal session '{session_id}' closed"
        else:
            return f"Terminal session '{session_id}' not found"
    except Exception as e:
        return f"Error closing terminal session '{session_id}': {e}"

@tool
def terminal_change_directory(directory: str, session_id: str = "main") -> str:
    """
    Change working directory in a terminal session.
    
    Args:
        directory: Directory to change to
        session_id: Terminal session ID
        
    Returns:
        Result of cd command
    """
    try:
        manager = get_terminal_manager()
        
        # Use appropriate cd command for the platform
        is_windows = platform.system() == "Windows"
        cd_command = f"Set-Location {directory}" if is_windows else f"cd {directory}"
        
        # Execute cd command
        result = manager.execute_command(cd_command, session_id)
        
        # Update session's tracked cwd
        if session_id in manager.sessions and result["success"]:
            manager.sessions[session_id]["cwd"] = directory
        
        return f"Changed directory to: {directory}\n{result['output']}"
    except Exception as e:
        return f"Error changing directory to '{directory}': {e}"

@tool
def terminal_test() -> str:
    """
    Test terminal functionality with safe commands.
    
    Returns:
        Test results
    """
    try:
        results = []
        
        # Test 1: Create session and run pwd/Get-Location
        is_windows = platform.system() == "Windows"
        pwd_cmd = "Get-Location" if is_windows else "pwd"
        result1 = terminal_execute(pwd_cmd, "test")
        results.append(f"Test 1 - Current directory:\n{result1}\n")
        
        # Test 2: List directory contents
        ls_cmd = "Get-ChildItem" if is_windows else "ls"
        result2 = terminal_execute(ls_cmd, "test")
        results.append(f"Test 2 - Directory listing:\n{result2}\n")
        
        # Test 3: Test a command that should fail
        result3 = terminal_execute("nonexistent_command_12345", "test")
        results.append(f"Test 3 - Failure test:\n{result3}\n")
        
        # Clean up test session
        terminal_close_session("test")
        
        return "Terminal Test Results:\n" + "\n".join(results)
        
    except Exception as e:
        return f"Terminal test failed: {e}"

# Export terminal tools
terminal_tools = [
    terminal_execute,
    terminal_new_session,
    terminal_list_sessions,
    terminal_close_session,
    terminal_change_directory,
    terminal_test
]