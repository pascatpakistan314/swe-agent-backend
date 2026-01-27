"""
Multi-language sandboxed code execution with complete language support
Enhanced with proper environment setup, resource management, and timeout enforcement
"""
import os
import tempfile
import subprocess
import docker
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from langchain_core.tools import tool
import threading
import atexit
import platform
import shutil
from contextlib import contextmanager
import sys
import re

class MultiLanguageSandbox:
    """Enhanced sandboxed environment supporting multiple programming languages"""
    
    # Complete language configurations with proper setup
    LANGUAGE_CONFIGS = {
        'python': {
            'image': 'python:3.11-slim',
            'extension': '.py',
            'run_command': 'python {file}',
            'packages_command': 'pip install --no-cache-dir',
            'test_command': 'pytest {file}',
            'repl_command': 'python -i',
            'setup_commands': [],
            'compile_required': False
        },
        'javascript': {
            'image': 'node:20-slim',
            'extension': '.js',
            'run_command': 'node {file}',
            'packages_command': 'npm install',
            'test_command': 'npm test',
            'repl_command': 'node',
            'setup_commands': [],
            'compile_required': False
        },
        'typescript': {
            'image': 'node:20-slim',
            'extension': '.ts',
            'run_command': 'npx tsx {file}',
            'packages_command': 'npm install',
            'compile_command': 'npx tsc {file} --outDir /tmp',
            'test_command': 'npm test',
            'repl_command': 'npx ts-node',
            'setup_commands': [
                'npm install -g typescript tsx ts-node @types/node',
                'npm init -y'
            ],
            'compile_required': False  # tsx can run directly
        },
        'java': {
            'image': 'openjdk:17-slim',
            'extension': '.java',
            'compile_command': 'javac -d /tmp {file}',
            'run_command': 'java -cp /tmp {class_name}',
            'packages_command': 'echo "Use Maven or Gradle for Java dependencies"',
            'test_command': 'java -jar junit.jar {class_name}',
            'setup_commands': [],
            'compile_required': True,
            'class_extraction': True  # Need to extract class name
        },
        'go': {
            'image': 'golang:1.21-alpine',
            'extension': '.go',
            'run_command': 'go run {file}',
            'packages_command': 'go get',
            'test_command': 'go test',
            'build_command': 'go build -o /tmp/main {file}',
            'repl_command': 'echo "No REPL for Go"',
            'setup_commands': [
                'go mod init sandbox',
                'apk add --no-cache gcc musl-dev'
            ],
            'compile_required': False  # go run works directly
        },
        'rust': {
            'image': 'rust:1.75-slim',
            'extension': '.rs',
            'compile_command': 'rustc -o /tmp/main {file}',
            'run_command': '/tmp/main',
            'packages_command': 'cargo add',
            'test_command': 'cargo test',
            'repl_command': 'echo "Use cargo for Rust REPL"',
            'setup_commands': [
                'cargo init --name sandbox',
                'apt-get update && apt-get install -y gcc'
            ],
            'compile_required': True
        },
        'cpp': {
            'image': 'gcc:13',
            'extension': '.cpp',
            'compile_command': 'g++ -std=c++17 -Wall -o /tmp/main {file}',
            'run_command': '/tmp/main',
            'packages_command': 'echo "Use package manager for C++ libs"',
            'test_command': './test',
            'setup_commands': [],
            'compile_required': True
        },
        'c': {
            'image': 'gcc:13',
            'extension': '.c',
            'compile_command': 'gcc -std=c11 -Wall -o /tmp/main {file}',
            'run_command': '/tmp/main',
            'packages_command': 'echo "Use package manager for C libs"',
            'test_command': './test',
            'setup_commands': [],
            'compile_required': True
        },
        'ruby': {
            'image': 'ruby:3.2-slim',
            'extension': '.rb',
            'run_command': 'ruby {file}',
            'packages_command': 'gem install',
            'test_command': 'rspec {file}',
            'repl_command': 'irb',
            'setup_commands': [],
            'compile_required': False
        },
        'php': {
            'image': 'php:8.2-cli',
            'extension': '.php',
            'run_command': 'php {file}',
            'packages_command': 'composer require',
            'test_command': 'phpunit {file}',
            'repl_command': 'php -a',
            'setup_commands': [
                'apt-get update && apt-get install -y git unzip',
                'curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer'
            ],
            'compile_required': False
        },
        'bash': {
            'image': 'ubuntu:22.04',
            'extension': '.sh',
            'run_command': 'bash {file}',
            'packages_command': 'apt-get install -y',
            'test_command': 'bash {file}',
            'repl_command': 'bash',
            'setup_commands': [
                'apt-get update',
                'apt-get install -y curl wget git'
            ],
            'compile_required': False
        }
    }
    
    # Track active containers for cleanup
    _active_containers = {}
    _cleanup_lock = threading.Lock()
    
    def __init__(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.docker_client = None
        self.containers = {}  # language -> container mapping
        self.session_id = str(uuid.uuid4())[:8]
        self.created_at = time.time()
        self.last_activity = time.time()
        self.timeout = 600  # 10 minute timeout for language containers
        
        # Ensure workspace exists
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to initialize Docker
        try:
            self.docker_client = docker.from_env()
            self.docker_available = True
        except Exception as e:
            self.docker_available = False
            print(f"Docker not available: {e}. Using subprocess fallback.")
        
        # Start timeout monitor
        self._start_timeout_monitor()
    
    def _start_timeout_monitor(self):
        """Monitor container timeouts"""
        def monitor():
            while self.containers:
                if time.time() - self.last_activity > self.timeout:
                    print(f"MultiLanguage sandbox {self.session_id} timed out")
                    self.cleanup()
                    break
                time.sleep(60)
        
        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
    
    def detect_language(self, file_path: str = None, code: str = None) -> str:
        """Intelligently detect programming language from file or code"""
        
        # Check file extension first
        if file_path:
            ext = Path(file_path).suffix.lower()
            ext_map = {
                '.py': 'python',
                '.js': 'javascript',
                '.ts': 'typescript',
                '.java': 'java',
                '.go': 'go',
                '.rs': 'rust',
                '.rb': 'ruby',
                '.php': 'php',
                '.cpp': 'cpp',
                '.c': 'c',
                '.sh': 'bash'
            }
            if ext in ext_map:
                return ext_map[ext]
        
        # Analyze code patterns
        if code:
            patterns = {
                'python': ['import ', 'from ', 'def ', 'class ', 'print('],
                'javascript': ['const ', 'let ', 'var ', 'function ', 'console.log'],
                'java': ['public class', 'public static', 'System.out.'],
                'go': ['package main', 'func main()', 'import "'],
                'rust': ['fn main()', 'let mut ', 'println!'],
                'ruby': ['puts ', 'def ', 'end\n', 'require '],
                'php': ['<?php', 'echo ', '$_'],
                'cpp': ['#include <', 'std::', 'cout <<'],
                'c': ['#include <stdio.h>', 'printf('],
                'bash': ['#!/bin/bash', 'echo ', 'if [']
            }
            
            scores = {}
            for lang, markers in patterns.items():
                score = sum(1 for marker in markers if marker in code)
                if score > 0:
                    scores[lang] = score
            
            if scores:
                return max(scores, key=scores.get)
        
        return 'python'  # Default
    
    def setup_language_container(self, language: str) -> bool:
        """Setup a container for a specific language with complete environment"""
        
        if not self.docker_available:
            return False
        
        if language in self.containers:
            # Check if container is still running
            try:
                self.containers[language].reload()
                if self.containers[language].status == 'running':
                    return True
            except:
                pass
        
        config = self.LANGUAGE_CONFIGS.get(language)
        if not config:
            print(f"Unsupported language: {language}")
            return False
        
        try:
            # Pull image if needed
            try:
                self.docker_client.images.get(config['image'])
            except docker.errors.ImageNotFound:
                print(f"Pulling {config['image']}...")
                self.docker_client.images.pull(config['image'])
            
            # Create container with proper configuration
            container = self.docker_client.containers.run(
                config['image'],
                command="/bin/sh" if 'alpine' in config['image'] else "/bin/bash",
                detach=True,
                tty=True,
                stdin_open=True,
                mem_limit="1g",  # More memory for compilation
                cpu_quota=75000,  # 75% CPU
                network_mode="bridge",  # Allow package downloads
                volumes={
                    str(self.workspace_dir): {
                        'bind': '/workspace',
                        'mode': 'rw'
                    }
                },
                working_dir="/workspace",
                name=f"swe-multilang-{language}-{self.session_id}",
                remove=True,
                labels={
                    "swe-agent": "multilang",
                    "language": language,
                    "session": self.session_id
                }
            )
            
            # Run setup commands
            for setup_cmd in config.get('setup_commands', []):
                print(f"Running setup for {language}: {setup_cmd}")
                result = container.exec_run(setup_cmd, demux=False)
                if result.exit_code != 0:
                    print(f"Setup command failed: {setup_cmd}")
            
            self.containers[language] = container
            
            # Track globally for cleanup
            with self._cleanup_lock:
                self._active_containers[f"{language}-{self.session_id}"] = container
            
            self.last_activity = time.time()
            return True
            
        except Exception as e:
            print(f"Failed to setup {language} container: {e}")
            return False
    
    def _extract_class_name(self, code: str, language: str) -> str:
        """Extract class name for languages that need it"""
        if language == 'java':
            match = re.search(r'public\s+class\s+(\w+)', code)
            if match:
                return match.group(1)
        elif language == 'kotlin':
            match = re.search(r'class\s+(\w+)', code)
            if match:
                return match.group(1)
        return "Main"
    
    def execute_code(self, code: str, language: str = None, 
                    packages: List[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Execute code in the appropriate language environment"""
        
        self.last_activity = time.time()
        
        # Auto-detect language if not provided
        if not language:
            language = self.detect_language(code=code)
        
        # Docker execution
        if self.docker_available:
            if not self.setup_language_container(language):
                return {
                    "success": False,
                    "error": f"Failed to setup {language} container",
                    "output": "",
                    "language": language
                }
            
            return self._execute_in_docker(code, language, packages, timeout)
        else:
            # Subprocess fallback
            return self._execute_subprocess(code, language, timeout)
    
    def _execute_in_docker(self, code: str, language: str, 
                          packages: List[str], timeout: int) -> Dict[str, Any]:
        """Execute code in Docker container with proper environment"""
        
        container = self.containers[language]
        config = self.LANGUAGE_CONFIGS[language]
        
        # Install packages if needed
        if packages and config.get('packages_command'):
            for package in packages:
                cmd = f"{config['packages_command']} {package}"
                result = container.exec_run(cmd)
                if result.exit_code != 0:
                    print(f"Failed to install {package}")
        
        # Create temporary file
        temp_filename = f"temp_{self.session_id}{config['extension']}"
        temp_path = f"/workspace/{temp_filename}"
        
        # Write code to file
        escaped_code = code.replace("'", "'\\''")
        write_cmd = f"cat > {temp_path} << 'EOF'\n{code}\nEOF"
        result = container.exec_run(["sh", "-c", write_cmd])
        
        if result.exit_code != 0:
            return {
                "success": False,
                "error": "Failed to write code",
                "output": "",
                "language": language
            }
        
        # Compile if required
        if config.get('compile_required'):
            compile_cmd = config['compile_command'].format(file=temp_path)
            
            # Extract class name if needed
            if config.get('class_extraction'):
                class_name = self._extract_class_name(code, language)
                compile_cmd = compile_cmd.replace('{class_name}', class_name)
            
            result = container.exec_run(compile_cmd, demux=True)
            if result.exit_code != 0:
                stderr = result.output[1].decode() if result.output[1] else ""
                return {
                    "success": False,
                    "error": f"Compilation failed: {stderr}",
                    "output": "",
                    "language": language
                }
        
        # Run the code
        if config.get('compile_required'):
            if config.get('class_extraction'):
                class_name = self._extract_class_name(code, language)
                run_cmd = config['run_command'].format(class_name=class_name)
            else:
                run_cmd = config['run_command']
        else:
            run_cmd = config['run_command'].format(file=temp_path)
        
        # Execute with timeout
        start_time = time.time()
        
        try:
            # Create exec instance
            exec_instance = container.client.api.exec_create(
                container.id,
                run_cmd,
                stdout=True,
                stderr=True,
                workdir="/workspace"
            )
            
            # Start execution
            exec_stream = container.client.api.exec_start(
                exec_instance['Id'],
                stream=True
            )
            
            # Collect output with timeout
            output = []
            
            def collect():
                for chunk in exec_stream:
                    if isinstance(chunk, bytes):
                        output.append(chunk.decode('utf-8', errors='replace'))
                    if time.time() - start_time > timeout:
                        break
            
            thread = threading.Thread(target=collect)
            thread.start()
            thread.join(timeout=timeout)
            
            execution_time = time.time() - start_time
            
            # Clean up temp file
            container.exec_run(f"rm -f {temp_path}")
            
            # Check if timed out
            if execution_time >= timeout:
                return {
                    "success": False,
                    "error": "Execution timed out",
                    "output": ''.join(output),
                    "language": language,
                    "execution_time": execution_time
                }
            
            # Get exit code
            exec_info = container.client.api.exec_inspect(exec_instance['Id'])
            exit_code = exec_info.get('ExitCode', 0)
            
            return {
                "success": exit_code == 0,
                "output": ''.join(output),
                "error": "",
                "language": language,
                "execution_time": execution_time,
                "exit_code": exit_code
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "language": language
            }
    
    def _execute_subprocess(self, code: str, language: str, timeout: int) -> Dict[str, Any]:
        """Fallback execution using subprocess"""
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"multilang_{self.session_id}_")
        
        try:
            config = self.LANGUAGE_CONFIGS.get(language, self.LANGUAGE_CONFIGS['python'])
            
            # Write code to file
            temp_file = os.path.join(temp_dir, f"script{config['extension']}")
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # Prepare command
            if config.get('compile_required'):
                # Compile first
                compile_cmd = config['compile_command'].format(file=temp_file)
                result = subprocess.run(
                    compile_cmd.split(),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=temp_dir
                )
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": f"Compilation failed: {result.stderr}",
                        "output": "",
                        "language": language
                    }
                
                # Run compiled output
                run_cmd = config['run_command']
                if '{class_name}' in run_cmd:
                    class_name = self._extract_class_name(code, language)
                    run_cmd = run_cmd.format(class_name=class_name)
            else:
                run_cmd = config['run_command'].format(file=temp_file)
            
            # Execute
            start_time = time.time()
            result = subprocess.run(
                run_cmd.split(),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=temp_dir
            )
            
            execution_time = time.time() - start_time
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "language": language,
                "execution_time": execution_time,
                "exit_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Execution timed out",
                "output": "",
                "language": language
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "language": language
            }
        finally:
            # Clean up
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def cleanup(self):
        """Clean up all containers and resources"""
        for language, container in self.containers.items():
            try:
                container.stop(timeout=5)
                container.remove(force=True)
            except:
                pass
        
        self.containers.clear()
        
        # Remove from global tracking
        with self._cleanup_lock:
            for key in list(self._active_containers.keys()):
                if self.session_id in key:
                    del self._active_containers[key]
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
    
    @classmethod
    def cleanup_all_containers(cls):
        """Clean up all active containers across all sessions"""
        with cls._cleanup_lock:
            for container in cls._active_containers.values():
                try:
                    container.stop(timeout=1)
                    container.remove(force=True)
                except:
                    pass
            cls._active_containers.clear()


# Register cleanup on exit
atexit.register(MultiLanguageSandbox.cleanup_all_containers)


# LangChain tool wrappers
@tool
def execute_multi_language_code(code: str, language: str = None, 
                               packages: List[str] = None, timeout: int = 30) -> str:
    """
    Execute code in any supported programming language.
    
    Args:
        code: The code to execute
        language: Programming language (auto-detected if not specified)
        packages: Optional list of packages to install
        timeout: Execution timeout in seconds
        
    Supported languages:
        python, javascript, typescript, java, go, rust, cpp, c, ruby, php, bash
        
    Returns:
        Execution results including output and any errors
    """
    sandbox = None
    try:
        sandbox = MultiLanguageSandbox()
        
        # Auto-detect language if not provided
        if not language:
            language = sandbox.detect_language(code=code)
            print(f"Auto-detected language: {language}")
        
        result = sandbox.execute_code(code, language, packages, timeout)
        
        output = [f"Language: {result['language']}"]
        output.append(f"Success: {result['success']}")
        
        if 'execution_time' in result:
            output.append(f"Execution time: {result['execution_time']:.2f}s")
        
        if result['output']:
            output.append(f"\nOutput:\n{result['output']}")
        
        if result.get('error'):
            output.append(f"\nError:\n{result['error']}")
        
        return '\n'.join(output)
        
    except Exception as e:
        return f"Multi-language execution error: {str(e)}"
        
    finally:
        if sandbox:
            sandbox.cleanup()


@tool
def detect_project_language(directory: str = "./workspace_repo") -> str:
    """
    Detect the primary programming language of a project.
    
    Args:
        directory: Project directory to analyze
        
    Returns:
        Detected language and project structure information
    """
    project_path = Path(directory)
    
    # File patterns to check
    language_files = {
        'python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
        'javascript': ['package.json', '.eslintrc', '.prettierrc'],
        'typescript': ['tsconfig.json'],
        'java': ['pom.xml', 'build.gradle'],
        'go': ['go.mod', 'go.sum'],
        'rust': ['Cargo.toml', 'Cargo.lock'],
        'ruby': ['Gemfile', 'Gemfile.lock'],
        'php': ['composer.json', 'composer.lock'],
        'cpp': ['CMakeLists.txt', 'Makefile'],
    }
    
    detected = []
    
    for language, markers in language_files.items():
        for marker in markers:
            if (project_path / marker).exists():
                detected.append(language)
                break
    
    # Count file extensions
    extensions = {}
    for file in project_path.rglob('*'):
        if file.is_file():
            ext = file.suffix.lower()
            if ext:
                extensions[ext] = extensions.get(ext, 0) + 1
    
    output = [f"Project Analysis for: {directory}"]
    
    if detected:
        output.append(f"\nDetected languages: {', '.join(set(detected))}")
    
    output.append(f"\nFile distribution:")
    for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]:
        output.append(f"  {ext}: {count} files")
    
    return '\n'.join(output)


# Export enhanced multi-language sandbox tools
multi_language_sandbox_tools = [
    execute_multi_language_code,
    detect_project_language
]
