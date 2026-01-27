# AGENTS.md - Multi-Language SWE-Agent Configuration

## Project Overview
This is an AI-powered software engineering agent that supports multiple programming languages and frameworks. It automates the entire development lifecycle through orchestrated multi-agent workflows.

## Supported Languages & Frameworks
- **Python**: Django, Flask, FastAPI, pytest
- **JavaScript/TypeScript**: Node.js, React, Vue, Next.js, Express
- **Java**: Spring Boot, Maven, Gradle
- **Go**: gin, echo, standard library
- **Rust**: cargo, tokio, actix
- **C/C++**: CMake, Make, gcc/g++
- **Ruby**: Rails, RSpec, Bundler
- **PHP**: Laravel, Composer, PHPUnit

## Language-Specific Setup

### Python Projects
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pytest tests/
```

### Node.js/JavaScript Projects
```bash
npm install  # or: yarn install / pnpm install
npm test     # Run tests
npm run dev  # Development server
npm run build # Production build
```

### Java Projects
```bash
mvn clean install  # Maven
./gradlew build    # Gradle
mvn test          # Run tests
java -jar target/app.jar  # Run application
```

### Go Projects
```bash
go mod download    # Download dependencies
go build ./...     # Build all packages
go test ./...      # Run all tests
go run main.go     # Run application
```

### Rust Projects
```bash
cargo build        # Build project
cargo test         # Run tests
cargo run          # Run application
cargo fmt          # Format code
cargo clippy       # Lint code
```

### C/C++ Projects
```bash
mkdir build && cd build
cmake ..           # Configure with CMake
make              # Build project
make test         # Run tests
./app             # Run application
```

## Universal Commands
- **Install dependencies**: Check `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`, `composer.json`
- **Run tests**: Look for `test/`, `tests/`, `spec/`, `__tests__/` directories
- **Build project**: Check for build scripts in `package.json`, `Makefile`, `CMakeLists.txt`, etc.
- **Start dev server**: Look for dev scripts or `main` entry points

## File Patterns by Language
- **Python**: `*.py`, `requirements*.txt`, `setup.py`, `pyproject.toml`
- **JavaScript**: `*.js`, `*.jsx`, `*.mjs`, `package*.json`, `.eslintrc*`
- **TypeScript**: `*.ts`, `*.tsx`, `tsconfig*.json`, `.prettierrc*`
- **Java**: `*.java`, `pom.xml`, `build.gradle`, `*.gradle`
- **Go**: `*.go`, `go.mod`, `go.sum`
- **Rust**: `*.rs`, `Cargo.toml`, `Cargo.lock`
- **C/C++**: `*.c`, `*.cpp`, `*.h`, `*.hpp`, `CMakeLists.txt`, `Makefile`
- **Ruby**: `*.rb`, `Gemfile`, `Gemfile.lock`, `Rakefile`
- **PHP**: `*.php`, `composer.json`, `composer.lock`

## Testing Instructions
- **Python**: `pytest`, `python -m unittest`, `nose2`
- **JavaScript/Node**: `npm test`, `jest`, `mocha`, `vitest`
- **Java**: `mvn test`, `gradle test`, `junit`
- **Go**: `go test ./...`, `go test -v`
- **Rust**: `cargo test`, `cargo test --all`
- **C/C++**: `make test`, `ctest`, `gtest`
- **Ruby**: `rspec`, `rake test`, `minitest`
- **PHP**: `phpunit`, `pest`, `codeception`

## Build & Deployment
- **Docker**: `docker build -t app .` and `docker run app`
- **Node.js**: `npm run build` or `yarn build`
- **Java**: `mvn package` or `gradle build`
- **Go**: `go build -o app`
- **Rust**: `cargo build --release`
- **C/C++**: `make` or `cmake --build .`

## Code Style Guidelines

### JavaScript/TypeScript
- Use ESLint and Prettier
- Prefer const over let
- Use arrow functions for callbacks
- Follow Airbnb or Standard style guide

### Python
- Follow PEP 8
- Use type hints (Python 3.5+)
- Docstrings for all public functions
- Black for formatting

### Java
- Follow Oracle Java conventions
- Use meaningful variable names
- Javadoc for public APIs
- Use Optional instead of null

### Go
- Follow Go fmt standards
- Use gofmt and golint
- Prefer short variable names in small scopes
- Return errors, don't panic

### Rust
- Follow Rust formatting (rustfmt)
- Use Result and Option types
- Document with /// comments
- Follow ownership principles

## Environment Variables
- Check for `.env`, `.env.local`, `.env.development`, `.env.production`
- Never commit secrets or API keys
- Use language-specific env libraries:
  - Python: `python-dotenv`
  - Node: `dotenv`
  - Go: `godotenv`
  - Java: Spring Boot `application.properties`

## Package Management
- **Python**: pip, poetry, pipenv, conda
- **Node.js**: npm, yarn, pnpm
- **Java**: Maven, Gradle
- **Go**: go modules
- **Rust**: Cargo
- **Ruby**: Bundler, gem
- **PHP**: Composer
- **C/C++**: Conan, vcpkg

## CI/CD Configuration
- Check `.github/workflows/` for GitHub Actions
- Check `.gitlab-ci.yml` for GitLab CI
- Check `Jenkinsfile` for Jenkins
- Check `.circleci/config.yml` for CircleCI
- Check `azure-pipelines.yml` for Azure DevOps

## Common Directories
- Source code: `src/`, `lib/`, `app/`, `pkg/`
- Tests: `test/`, `tests/`, `spec/`, `__tests__/`
- Documentation: `docs/`, `doc/`
- Configuration: `config/`, `.config/`, `etc/`
- Scripts: `scripts/`, `bin/`, `tools/`
- Assets: `assets/`, `static/`, `public/`

## Debug Commands
- **Python**: `python -m pdb`, `ipdb`, `breakpoint()`
- **Node.js**: `node --inspect`, Chrome DevTools
- **Java**: `jdb`, IDE debuggers
- **Go**: `dlv debug`, `go run -gcflags="-N -l"`
- **Rust**: `rust-gdb`, `rust-lldb`
- **C/C++**: `gdb`, `lldb`, `valgrind`

## Performance Profiling
- **Python**: `cProfile`, `line_profiler`, `py-spy`
- **Node.js**: `clinic`, `0x`, Chrome DevTools
- **Java**: `jvisualvm`, `async-profiler`
- **Go**: `pprof`, `go test -bench`
- **Rust**: `cargo bench`, `perf`, `flamegraph`

## Security Considerations
- Run security scans: `npm audit`, `pip-audit`, `cargo audit`
- Check for vulnerable dependencies
- Use static analysis tools for each language
- Follow OWASP guidelines
- Sanitize user inputs
- Use prepared statements for SQL
- Validate and escape all external data
