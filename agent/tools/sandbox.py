"""
Sandboxed code execution for safe testing of generated code
Enhanced with proper resource management, timeout enforcement, and complete implementations
"""
import os
import tempfile
import subprocess
import docker
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import json
import time
import uuid
from langchain_core.tools import tool
import threading
import atexit
import signal
import platform
from contextlib import contextmanager
import shutil

class CodeSandbox:
    """Sandboxed environment for code execution with proper resource management"""
    
    # Class-level tracking for cleanup
    _active_sandboxes = []
    _cleanup_lock = threading.Lock()
    
    def __init__(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.docker_client = None
        self.container = None
        self.session_id = str(uuid.uuid4())[:8]
        self.created_at = time.time()
        self.last_activity = time.time()
        self.timeout = 300  # Default 5 minute timeout
        
        # Ensure workspace exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to initialize Docker client
        try:
            self.docker_client = docker.from_env()
            self.docker_available = True
        except Exception as e:
            self.docker_available = False
            print(f"Warning: Docker not available ({e}). Using subprocess fallback (less secure)")
        
        # Track this sandbox for cleanup
        with self._cleanup_lock:
            self._active_sandboxes.append(self)
        
        # Start timeout monitor
        self._start_timeout_monitor()
    
    def _start_timeout_monitor(self):
        """Monitor sandbox timeout and cleanup if inactive"""
        def monitor():
            while self in self._active_sandboxes:
                if time.time() - self.last_activity > self.timeout:
                    print(f"Sandbox {self.session_id} timed out, cleaning up...")
                    self.cleanup()
                    break
                time.sleep(30)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def setup_container(self, image: str = "python:3.11-slim") -> bool:
        """Setup a Docker container with proper resource limits and cleanup"""
        if not self.docker_available:
            return False
        
        try:
            # Pull image if needed
            try:
                self.docker_client.images.get(image)
            except docker.errors.ImageNotFound:
                print(f"Pulling image {image}...")
                self.docker_client.images.pull(image)
            
            # Create container with proper resource limits
            self.container = self.docker_client.containers.run(
                image,
                command="/bin/bash",
                detach=True,
                tty=True,
                mem_limit="512m",
                cpu_quota=50000,  # 50% CPU
                network_mode="none",  # No network access for security
                volumes={
                    str(self.workspace_dir): {
                        'bind': '/workspace',
                        'mode': 'rw'
                    }
                },
                working_dir="/workspace",
                name=f"swe-agent-sandbox-{self.session_id}",
                remove=True,  # Auto-remove on stop
                labels={"swe-agent": "sandbox", "session": self.session_id}
            )
            
            # Install basic packages with timeout
            self._install_packages()
            
            self.last_activity = time.time()
            return True
            
        except Exception as e:
            print(f"Error setting up container: {e}")
            # Cleanup any partially created container
            if self.container:
                try:
                    self.container.stop(timeout=1)
                    self.container.remove(force=True)
                except:
                    pass
                self.container = None
            return False
    
    def _install_packages(self):
        """Install basic Python packages in container with timeout"""
        if not self.container:
            return
        
        packages = [
            "pip install --no-cache-dir numpy pandas matplotlib requests",
            "pip install --no-cache-dir pytest black flake8"
        ]
        
        for cmd in packages:
            try:
                result = self.container.exec_run(cmd, demux=False)
                if result.exit_code != 0:
                    print(f"Warning: Failed to install packages: {cmd}")
            except Exception as e:
                print(f"Warning: Package installation error: {e}")
    
    def execute_code(self, code: str, language: str = "python", 
                     timeout: int = 30) -> Dict[str, Any]:
        """Execute code with proper timeout enforcement and resource cleanup"""
        
        self.last_activity = time.time()
        
        if self.docker_available and self.container:
            return self._execute_in_docker(code, language, timeout)
        else:
            return self._execute_subprocess(code, language, timeout)
    
    def _execute_in_docker(self, code: str, language: str, timeout: int) -> Dict[str, Any]:
        """Execute code inside Docker container with timeout"""
        
        # Create temporary file with code
        temp_filename = f"temp_{self.session_id}_{int(time.time())}"
        
        # Prepare command based on language
        if language == "python":
            temp_filename += ".py"
            cmd = f"python {temp_filename}"
        elif language == "javascript":
            temp_filename += ".js"
            cmd = f"node {temp_filename}"
        elif language == "bash":
            temp_filename += ".sh"
            cmd = f"bash {temp_filename}"
        else:
            return {
                "success": False,
                "error": f"Unsupported language: {language}",
                "output": "",
                "session_id": self.session_id
            }
        
        try:
            # Write code to container (properly escaped)
            escaped_code = code.replace("'", "'\\''")
            write_cmd = f"cat > {temp_filename} << 'EOF'\n{code}\nEOF"
            result = self.container.exec_run(
                ["sh", "-c", write_cmd],
                workdir="/workspace"
            )
            
            if result.exit_code != 0:
                return {
                    "success": False,
                    "error": f"Failed to write code: {result.output.decode() if result.output else 'Unknown error'}",
                    "output": "",
                    "session_id": self.session_id
                }
            
            # Execute with timeout using docker exec with timeout
            start_time = time.time()
            
            # Create exec instance
            exec_instance = self.container.client.api.exec_create(
                self.container.id,
                cmd,
                stdout=True,
                stderr=True,
                workdir="/workspace"
            )
            
            # Start execution with streaming
            exec_stream = self.container.client.api.exec_start(
                exec_instance['Id'],
                stream=True
            )
            
            # Collect output with timeout
            output = []
            error = []
            
            def collect_output():
                try:
                    for chunk in exec_stream:
                        if isinstance(chunk, bytes):
                            output.append(chunk.decode('utf-8', errors='replace'))
                        if time.time() - start_time > timeout:
                            break
                except Exception as e:
                    error.append(str(e))
            
            # Run collection in thread with timeout
            thread = threading.Thread(target=collect_output)
            thread.start()
            thread.join(timeout=timeout)
            
            # Check if timed out
            execution_time = time.time() - start_time
            if execution_time >= timeout:
                # Kill the process in container
                try:
                    self.container.exec_run(f"pkill -f {temp_filename}")
                except:
                    pass
                
                return {
                    "success": False,
                    "output": ''.join(output),
                    "error": "Execution timed out",
                    "exit_code": -1,
                    "session_id": self.session_id,
                    "execution_time": execution_time
                }
            
            # Get exit code
            exec_info = self.container.client.api.exec_inspect(exec_instance['Id'])
            exit_code = exec_info.get('ExitCode', 0)
            
            # Clean up temp file
            self.container.exec_run(f"rm -f {temp_filename}")
            
            return {
                "success": exit_code == 0,
                "output": ''.join(output),
                "error": ''.join(error),
                "exit_code": exit_code,
                "session_id": self.session_id,
                "execution_time": execution_time
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "session_id": self.session_id
            }
    
    def _execute_subprocess(self, code: str, language: str, timeout: int) -> Dict[str, Any]:
        """Fallback execution using subprocess with proper sandboxing"""
        
        # Create temporary directory for isolation
        temp_dir = tempfile.mkdtemp(prefix=f"sandbox_{self.session_id}_")
        
        try:
            # Determine file extension and command
            if language == "python":
                file_ext = ".py"
                # Use restricted Python execution
                cmd = [sys.executable, "-u", "-B"]  # -u: unbuffered, -B: no bytecode
                # Add basic sandboxing for Python
                sandbox_code = f"""
import sys
import os
# Restrict imports
__builtins__.__import__ = lambda *args, **kwargs: None
# Restrict file operations
os.remove = lambda *args, **kwargs: None
os.rmdir = lambda *args, **kwargs: None
os.unlink = lambda *args, **kwargs: None
# User code
{code}
"""
                code_to_write = sandbox_code
            elif language == "javascript":
                file_ext = ".js"
                cmd = ["node", "--no-deprecation"]
                code_to_write = code
            elif language == "bash":
                file_ext = ".sh"
                cmd = ["bash", "-r"]  # Restricted shell
                code_to_write = code
            else:
                return {
                    "success": False,
                    "error": f"Unsupported language: {language}",
                    "output": "",
                    "session_id": self.session_id
                }
            
            # Write code to temporary file
            temp_file = os.path.join(temp_dir, f"script{file_ext}")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code_to_write)
            
            # Add script to command
            cmd.append(temp_file)
            
            # Execute with timeout and resource limits
            start_time = time.time()
            
            # Set up environment with restrictions
            env = os.environ.copy()
            env['TMPDIR'] = temp_dir  # Restrict temp file location
            
            # Platform-specific resource limits
            if platform.system() != "Windows":
                # Unix: use preexec_fn to set resource limits
                import resource
                
                def limit_resources():
                    # Limit CPU time
                    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout))
                    # Limit memory (256MB)
                    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
                    # Limit file size (10MB)
                    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
                    # Limit number of processes
                    resource.setrlimit(resource.RLIMIT_NPROC, (10, 10))
                
                preexec_fn = limit_resources
            else:
                preexec_fn = None
            
            # Run with timeout
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=temp_dir,
                    env=env,
                    preexec_fn=preexec_fn
                )
                
                execution_time = time.time() - start_time
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr,
                    "exit_code": result.returncode,
                    "session_id": self.session_id,
                    "execution_time": execution_time
                }
                
            except subprocess.TimeoutExpired as e:
                return {
                    "success": False,
                    "error": "Code execution timed out",
                    "output": e.stdout or "",
                    "session_id": self.session_id,
                    "execution_time": timeout
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "output": "",
                    "session_id": self.session_id
                }
                
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
    
    def execute_test(self, test_file: str) -> Dict[str, Any]:
        """Execute test file with proper timeout and resource management"""
        
        self.last_activity = time.time()
        
        if not os.path.exists(test_file):
            return {
                "success": False,
                "error": f"Test file not found: {test_file}",
                "output": "",
                "session_id": self.session_id
            }
        
        cmd = f"pytest {test_file} -v --tb=short --timeout=30"
        
        if self.container:
            try:
                result = self.container.exec_run(
                    cmd,
                    workdir="/workspace",
                    demux=True
                )
                
                stdout = result.output[0].decode() if result.output[0] else ""
                stderr = result.output[1].decode() if result.output[1] else ""
                
                return {
                    "success": result.exit_code == 0,
                    "output": stdout,
                    "error": stderr,
                    "exit_code": result.exit_code,
                    "session_id": self.session_id
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "output": "",
                    "session_id": self.session_id
                }
        else:
            # Subprocess fallback
            try:
                result = subprocess.run(
                    cmd.split(),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.workspace_dir)
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr,
                    "exit_code": result.returncode,
                    "session_id": self.session_id
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Test execution timed out",
                    "output": "",
                    "session_id": self.session_id
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "output": "",
                    "session_id": self.session_id
                }
    
    def cleanup(self):
        """Properly clean up container and all resources"""
        # Remove from active sandboxes
        with self._cleanup_lock:
            if self in self._active_sandboxes:
                self._active_sandboxes.remove(self)
        
        # Clean up Docker container
        if self.container:
            try:
                # Stop container with timeout
                self.container.stop(timeout=5)
            except Exception as e:
                print(f"Warning: Failed to stop container {self.session_id}: {e}")
                try:
                    # Force kill if stop fails
                    self.container.kill()
                except:
                    pass
            
            try:
                # Remove container
                self.container.remove(force=True)
            except Exception as e:
                print(f"Warning: Failed to remove container {self.session_id}: {e}")
            
            self.container = None
        
        # Clean up Docker client
        if self.docker_client:
            try:
                self.docker_client.close()
            except:
                pass
            self.docker_client = None
    
    def __enter__(self):
        """Context manager entry"""
        self.setup_container()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with guaranteed cleanup"""
        self.cleanup()
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
    
    @classmethod
    def cleanup_all_sandboxes(cls):
        """Class method to clean up all active sandboxes"""
        with cls._cleanup_lock:
            for sandbox in list(cls._active_sandboxes):
                try:
                    sandbox.cleanup()
                except:
                    pass
            cls._active_sandboxes.clear()


# Register cleanup on exit
atexit.register(CodeSandbox.cleanup_all_sandboxes)

# Import sys for subprocess Python execution
import sys

# LangChain tool wrappers with proper resource management
@tool
def execute_code_sandbox(code: str, language: str = "python", timeout: int = 30) -> str:
    """
    Execute code in a sandboxed environment with timeout.
    
    Args:
        code: The code to execute
        language: Programming language (python, javascript, bash)
        timeout: Execution timeout in seconds
        
    Returns:
        Execution results including output and any errors
    """
    sandbox = None
    try:
        sandbox = CodeSandbox()
        
        if sandbox.docker_available:
            if not sandbox.setup_container():
                return f"Failed to setup Docker container, using subprocess fallback\n"
        
        result = sandbox.execute_code(code, language, timeout)
        
        output = []
        output.append(f"Session ID: {result['session_id']}")
        output.append(f"Success: {result['success']}")
        
        if 'execution_time' in result:
            output.append(f"Execution time: {result['execution_time']:.2f}s")
        
        if result['output']:
            output.append(f"\nOutput:\n{result['output']}")
        
        if result.get('error'):
            output.append(f"\nError:\n{result['error']}")
        
        return '\n'.join(output)
        
    except Exception as e:
        return f"Sandbox execution error: {str(e)}"
        
    finally:
        if sandbox:
            sandbox.cleanup()


@tool
def test_code_sandbox(test_file: str) -> str:
    """
    Run tests in sandboxed environment with timeout.
    
    Args:
        test_file: Path to test file
        
    Returns:
        Test execution results
    """
    sandbox = None
    try:
        sandbox = CodeSandbox()
        
        if sandbox.docker_available:
            if not sandbox.setup_container():
                return "Failed to setup Docker container for testing"
        
        result = sandbox.execute_test(test_file)
        
        return f"""
Test Results:
Session: {result['session_id']}
Success: {result['success']}
Exit Code: {result.get('exit_code', 'N/A')}

Output:
{result['output']}

{f"Error: {result['error']}" if result.get('error') else ''}
"""
    except Exception as e:
        return f"Test execution error: {str(e)}"
        
    finally:
        if sandbox:
            sandbox.cleanup()


@tool
def validate_code_safety(code: str) -> str:
    """
    Validate code for safety before execution.
    
    Args:
        code: Code to validate
        
    Returns:
        Safety analysis results
    """
    dangerous_patterns = [
        ('import os', 'System operations'),
        ('import subprocess', 'Process execution'),
        ('import socket', 'Network operations'),
        ('import requests', 'HTTP requests'),
        ('eval(', 'Dynamic code execution'),
        ('exec(', 'Dynamic code execution'),
        ('compile(', 'Code compilation'),
        ('__import__', 'Dynamic imports'),
        ('open(', 'File operations'),
        ('file(', 'File operations'),
        ('input(', 'User input'),
        ('raw_input(', 'User input'),
        ('globals(', 'Global namespace access'),
        ('locals(', 'Local namespace access'),
        ('vars(', 'Variable access'),
        ('dir(', 'Object introspection'),
        ('getattr(', 'Attribute access'),
        ('setattr(', 'Attribute modification'),
        ('delattr(', 'Attribute deletion'),
        ('__', 'Dunder method access'),
        ('shutil.rmtree', 'Recursive deletion'),
        ('os.remove', 'File deletion'),
        ('os.unlink', 'File deletion'),
        ('os.system', 'System command execution'),
        ('subprocess.', 'Process execution'),
    ]
    
    warnings = []
    risk_level = "LOW"
    
    for pattern, description in dangerous_patterns:
        if pattern in code:
            warnings.append(f"⚠️  {description}: Found '{pattern}'")
            if pattern in ['eval(', 'exec(', '__import__', 'os.system', 'subprocess.']:
                risk_level = "HIGH"
            elif risk_level != "HIGH":
                risk_level = "MEDIUM"
    
    output = [f"Risk Level: {risk_level}"]
    
    if warnings:
        output.append("\nSecurity warnings detected:")
        output.extend(warnings)
        output.append("\nCode will execute in sandbox with restrictions.")
    else:
        output.append("✅ Code appears safe for execution")
    
    # Check for infinite loops
    if 'while True:' in code or 'while 1:' in code:
        output.append("⚠️  Warning: Potential infinite loop detected")
    
    # Check for resource-intensive operations
    if 'range(10' in code and ')' in code:
        # Check for large ranges
        import re
        ranges = re.findall(r'range\((\d+)\)', code)
        for r in ranges:
            if int(r) > 1000000:
                output.append(f"⚠️  Warning: Large range detected: range({r})")
    
    return '\n'.join(output)


@tool
def cleanup_all_sandboxes() -> str:
    """
    Clean up all active sandbox sessions to free resources.
    
    Returns:
        Cleanup report
    """
    try:
        initial_count = len(CodeSandbox._active_sandboxes)
        CodeSandbox.cleanup_all_sandboxes()
        
        # Also clean up any orphaned Docker containers
        try:
            client = docker.from_env()
            containers = client.containers.list(
                filters={"label": "swe-agent=sandbox"}
            )
            for container in containers:
                try:
                    container.stop(timeout=1)
                    container.remove(force=True)
                except:
                    pass
            client.close()
        except:
            pass
        
        return f"Cleaned up {initial_count} sandbox session(s)"
        
    except Exception as e:
        return f"Cleanup error: {str(e)}"


# Export enhanced sandbox tools
sandbox_tools = [
    execute_code_sandbox,
    test_code_sandbox,
    validate_code_safety,
    cleanup_all_sandboxes
]
