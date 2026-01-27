"""
Multi-language build, test, and package management tools
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_core.tools import tool
import platform

class MultiLanguageBuilder:
    """Build and test runner for multiple programming languages"""
    
    def __init__(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.is_windows = platform.system() == "Windows"
    
    def detect_build_system(self) -> Dict[str, Any]:
        """Detect available build systems and package managers"""
        
        build_systems = {
            'npm': self._check_file('package.json'),
            'yarn': self._check_file('yarn.lock'),
            'pnpm': self._check_file('pnpm-lock.yaml'),
            'pip': self._check_file('requirements.txt'),
            'poetry': self._check_file('pyproject.toml'),
            'maven': self._check_file('pom.xml'),
            'gradle': self._check_file('build.gradle') or self._check_file('build.gradle.kts'),
            'cargo': self._check_file('Cargo.toml'),
            'go_mod': self._check_file('go.mod'),
            'bundler': self._check_file('Gemfile'),
            'composer': self._check_file('composer.json'),
            'cmake': self._check_file('CMakeLists.txt'),
            'make': self._check_file('Makefile'),
        }
        
        detected = [name for name, found in build_systems.items() if found]
        
        return {
            'detected': detected,
            'primary': detected[0] if detected else None,
            'all_systems': build_systems
        }
    
    def _check_file(self, filename: str) -> bool:
        """Check if file exists in workspace"""
        return (self.workspace_dir / filename).exists()
    
    def _run_command(self, command: str, cwd: Optional[Path] = None) -> Dict[str, Any]:
        """Run a shell command and capture output"""
        
        if cwd is None:
            cwd = self.workspace_dir
        
        try:
            # Handle command as list or string
            if isinstance(command, str):
                # Use shell=True for string commands
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=str(cwd),
                    timeout=120
                )
            else:
                # Use shell=False for list commands
                result = subprocess.run(
                    command,
                    shell=False,
                    capture_output=True,
                    text=True,
                    cwd=str(cwd),
                    timeout=120
                )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'exit_code': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timed out after 120 seconds',
                'exit_code': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1
            }
    
    # JavaScript/TypeScript/Node.js
    def npm_install(self, packages: List[str] = None) -> Dict[str, Any]:
        """Install npm packages"""
        if packages:
            cmd = f"npm install {' '.join(packages)}"
        else:
            cmd = "npm install"
        return self._run_command(cmd)
    
    def npm_run(self, script: str) -> Dict[str, Any]:
        """Run npm script"""
        return self._run_command(f"npm run {script}")
    
    def npm_test(self) -> Dict[str, Any]:
        """Run npm tests"""
        return self._run_command("npm test")
    
    def npm_build(self) -> Dict[str, Any]:
        """Build Node.js project"""
        return self._run_command("npm run build")
    
    # Python
    def pip_install(self, packages: List[str] = None) -> Dict[str, Any]:
        """Install Python packages"""
        if packages:
            cmd = f"pip install {' '.join(packages)}"
        else:
            cmd = "pip install -r requirements.txt"
        return self._run_command(cmd)
    
    def pytest_run(self, test_file: str = None) -> Dict[str, Any]:
        """Run pytest"""
        if test_file:
            cmd = f"pytest {test_file} -v"
        else:
            cmd = "pytest -v"
        return self._run_command(cmd)
    
    def python_lint(self, file: str = None) -> Dict[str, Any]:
        """Run Python linters"""
        if file:
            return self._run_command(f"flake8 {file} && black --check {file}")
        else:
            return self._run_command("flake8 . && black --check .")
    
    # Java
    def maven_build(self) -> Dict[str, Any]:
        """Build Maven project"""
        return self._run_command("mvn clean install")
    
    def maven_test(self) -> Dict[str, Any]:
        """Run Maven tests"""
        return self._run_command("mvn test")
    
    def gradle_build(self) -> Dict[str, Any]:
        """Build Gradle project"""
        cmd = "gradlew build" if self.is_windows else "./gradlew build"
        return self._run_command(cmd)
    
    def gradle_test(self) -> Dict[str, Any]:
        """Run Gradle tests"""
        cmd = "gradlew test" if self.is_windows else "./gradlew test"
        return self._run_command(cmd)
    
    # Go
    def go_build(self, output: str = None) -> Dict[str, Any]:
        """Build Go project"""
        if output:
            cmd = f"go build -o {output}"
        else:
            cmd = "go build"
        return self._run_command(cmd)
    
    def go_test(self, package: str = "./...") -> Dict[str, Any]:
        """Run Go tests"""
        return self._run_command(f"go test {package}")
    
    def go_mod_tidy(self) -> Dict[str, Any]:
        """Tidy Go modules"""
        return self._run_command("go mod tidy")
    
    # Rust
    def cargo_build(self, release: bool = False) -> Dict[str, Any]:
        """Build Rust project"""
        cmd = "cargo build --release" if release else "cargo build"
        return self._run_command(cmd)
    
    def cargo_test(self) -> Dict[str, Any]:
        """Run Rust tests"""
        return self._run_command("cargo test")
    
    def cargo_fmt(self) -> Dict[str, Any]:
        """Format Rust code"""
        return self._run_command("cargo fmt")
    
    def cargo_clippy(self) -> Dict[str, Any]:
        """Run Rust linter"""
        return self._run_command("cargo clippy")
    
    # C/C++
    def cmake_build(self, build_dir: str = "build") -> Dict[str, Any]:
        """Build CMake project"""
        build_path = self.workspace_dir / build_dir
        build_path.mkdir(exist_ok=True)
        
        # Configure
        config_result = self._run_command("cmake ..", cwd=build_path)
        if not config_result['success']:
            return config_result
        
        # Build
        return self._run_command("cmake --build .", cwd=build_path)
    
    def make_build(self, target: str = None) -> Dict[str, Any]:
        """Build with Make"""
        if target:
            cmd = f"make {target}"
        else:
            cmd = "make"
        return self._run_command(cmd)
    
    # Ruby
    def bundle_install(self) -> Dict[str, Any]:
        """Install Ruby gems"""
        return self._run_command("bundle install")
    
    def rspec_run(self) -> Dict[str, Any]:
        """Run RSpec tests"""
        return self._run_command("rspec")
    
    # PHP
    def composer_install(self) -> Dict[str, Any]:
        """Install PHP packages"""
        return self._run_command("composer install")
    
    def phpunit_run(self) -> Dict[str, Any]:
        """Run PHPUnit tests"""
        return self._run_command("vendor/bin/phpunit")
    
    # Universal commands
    def install_dependencies(self) -> Dict[str, Any]:
        """Auto-detect and install dependencies"""
        
        build_systems = self.detect_build_system()
        
        if not build_systems['detected']:
            return {
                'success': False,
                'message': 'No build system detected',
                'systems_checked': build_systems['all_systems']
            }
        
        results = {}
        
        # Try each detected system
        for system in build_systems['detected']:
            if system == 'npm':
                results['npm'] = self.npm_install()
            elif system == 'pip':
                results['pip'] = self.pip_install()
            elif system == 'maven':
                results['maven'] = self.maven_build()
            elif system == 'gradle':
                results['gradle'] = self.gradle_build()
            elif system == 'cargo':
                results['cargo'] = self.cargo_build()
            elif system == 'go_mod':
                results['go'] = self.go_mod_tidy()
            elif system == 'bundler':
                results['bundler'] = self.bundle_install()
            elif system == 'composer':
                results['composer'] = self.composer_install()
        
        return {
            'success': any(r.get('success', False) for r in results.values()),
            'results': results,
            'detected_systems': build_systems['detected']
        }
    
    def run_tests(self) -> Dict[str, Any]:
        """Auto-detect and run tests"""
        
        results = {}
        
        # Check for test frameworks
        if self._check_file('package.json'):
            results['npm'] = self.npm_test()
        
        if self._check_file('pytest.ini') or Path(self.workspace_dir / 'tests').exists():
            results['pytest'] = self.pytest_run()
        
        if self._check_file('pom.xml'):
            results['maven'] = self.maven_test()
        
        if self._check_file('build.gradle') or self._check_file('build.gradle.kts'):
            results['gradle'] = self.gradle_test()
        
        if self._check_file('go.mod'):
            results['go'] = self.go_test()
        
        if self._check_file('Cargo.toml'):
            results['cargo'] = self.cargo_test()
        
        if self._check_file('Gemfile') and Path(self.workspace_dir / 'spec').exists():
            results['rspec'] = self.rspec_run()
        
        if self._check_file('phpunit.xml') or self._check_file('phpunit.xml.dist'):
            results['phpunit'] = self.phpunit_run()
        
        return {
            'success': any(r.get('success', False) for r in results.values()),
            'results': results,
            'tests_run': list(results.keys())
        }
    
    def build_project(self) -> Dict[str, Any]:
        """Auto-detect and build project"""
        
        results = {}
        
        if self._check_file('package.json'):
            # Check if build script exists
            with open(self.workspace_dir / 'package.json') as f:
                pkg = json.load(f)
                if 'scripts' in pkg and 'build' in pkg['scripts']:
                    results['npm'] = self.npm_build()
        
        if self._check_file('pom.xml'):
            results['maven'] = self.maven_build()
        
        if self._check_file('build.gradle') or self._check_file('build.gradle.kts'):
            results['gradle'] = self.gradle_build()
        
        if self._check_file('go.mod'):
            results['go'] = self.go_build()
        
        if self._check_file('Cargo.toml'):
            results['cargo'] = self.cargo_build()
        
        if self._check_file('CMakeLists.txt'):
            results['cmake'] = self.cmake_build()
        elif self._check_file('Makefile'):
            results['make'] = self.make_build()
        
        return {
            'success': any(r.get('success', False) for r in results.values()),
            'results': results,
            'build_systems': list(results.keys())
        }


# LangChain tools
@tool
def install_project_dependencies(workspace: str = "./workspace_repo") -> str:
    """
    Auto-detect and install project dependencies for any language.
    
    Args:
        workspace: Project directory
        
    Returns:
        Installation results
    """
    builder = MultiLanguageBuilder(workspace)
    result = builder.install_dependencies()
    
    if not result.get('detected_systems'):
        return "No build system detected. Please check your project configuration."
    
    output = [f"Detected build systems: {', '.join(result['detected_systems'])}"]
    
    for system, res in result.get('results', {}).items():
        output.append(f"\n{system}:")
        if res['success']:
            output.append(f"  ✅ Success")
            if res['stdout']:
                output.append(f"  {res['stdout'][:200]}...")
        else:
            output.append(f"  ❌ Failed")
            if res['stderr']:
                output.append(f"  Error: {res['stderr'][:200]}...")
    
    return '\n'.join(output)

@tool
def run_project_tests(workspace: str = "./workspace_repo", test_file: str = None) -> str:
    """
    Auto-detect and run tests for any language.
    
    Args:
        workspace: Project directory
        test_file: Specific test file to run (optional)
        
    Returns:
        Test results
    """
    builder = MultiLanguageBuilder(workspace)
    
    if test_file:
        # Determine test framework based on file
        if test_file.endswith('.py'):
            result = {'pytest': builder.pytest_run(test_file)}
        elif test_file.endswith('.js') or test_file.endswith('.ts'):
            result = {'npm': builder.npm_test()}
        elif test_file.endswith('.java'):
            result = {'junit': builder.maven_test()}
        elif test_file.endswith('.go'):
            result = {'go': builder.go_test(test_file)}
        else:
            result = builder.run_tests()
    else:
        result = builder.run_tests()
    
    if isinstance(result, dict) and 'results' in result:
        output = [f"Tests run: {', '.join(result.get('tests_run', []))}"]
        
        for framework, res in result['results'].items():
            output.append(f"\n{framework}:")
            if res['success']:
                output.append(f"  ✅ All tests passed")
                if res['stdout']:
                    # Extract test summary if available
                    lines = res['stdout'].split('\n')
                    for line in lines[-10:]:  # Last 10 lines usually have summary
                        if 'passed' in line.lower() or 'failed' in line.lower():
                            output.append(f"  {line}")
            else:
                output.append(f"  ❌ Tests failed")
                if res['stderr']:
                    output.append(f"  Error: {res['stderr'][:500]}...")
    else:
        output = ["Test execution completed"]
    
    return '\n'.join(output)

@tool
def build_project(workspace: str = "./workspace_repo", release: bool = False) -> str:
    """
    Auto-detect and build project for any language.
    
    Args:
        workspace: Project directory
        release: Build in release/production mode
        
    Returns:
        Build results
    """
    builder = MultiLanguageBuilder(workspace)
    result = builder.build_project()
    
    if not result.get('build_systems'):
        return "No build system detected. Please check your project configuration."
    
    output = [f"Build systems used: {', '.join(result['build_systems'])}"]
    
    for system, res in result.get('results', {}).items():
        output.append(f"\n{system}:")
        if res['success']:
            output.append(f"  ✅ Build successful")
            if 'BUILD SUCCESS' in res.get('stdout', ''):
                output.append("  Build completed successfully")
        else:
            output.append(f"  ❌ Build failed")
            if res['stderr']:
                output.append(f"  Error: {res['stderr'][:500]}...")
    
    return '\n'.join(output)

@tool
def run_custom_build_command(command: str, workspace: str = "./workspace_repo") -> str:
    """
    Run a custom build or test command.
    
    Args:
        command: Command to run (e.g., "npm run dev", "cargo test --release")
        workspace: Project directory
        
    Returns:
        Command output
    """
    builder = MultiLanguageBuilder(workspace)
    result = builder._run_command(command)
    
    output = [f"Command: {command}"]
    output.append(f"Success: {result['success']}")
    
    if result['stdout']:
        output.append(f"\nOutput:\n{result['stdout']}")
    
    if result['stderr'] and not result['success']:
        output.append(f"\nError:\n{result['stderr']}")
    
    return '\n'.join(output)

# Export build tools
multi_language_build_tools = [
    install_project_dependencies,
    run_project_tests,
    build_project,
    run_custom_build_command
]
