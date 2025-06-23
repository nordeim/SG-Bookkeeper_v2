<think>
### **1. Task Intake & Understanding**

The user wants me to update the `pyproject.toml` file.
The goal is to change the version constraints of the Python packages listed in the `[tool.poetry.dependencies]` and `[tool.poetry.group.dev.dependencies]` sections to match the exact versions provided in a `pip list` output.

**Key Requirements:**
1.  **Input**: A `pip list` output and an existing `pyproject.toml` file.
2.  **Action**: Modify the version specifiers for dependencies in `pyproject.toml`.
3.  **Output**: A *complete* updated *replacement* file for `pyproject.toml`.
4.  **Constraint**: The versions must match the `pip list` output.
5.  **Implicit Constraint**: Adhere to my "CodeNavigator" persona: be meticulous, preserve all other parts of the file, and ensure correctness.

### **2. Systematic Diagnosis & Analysis**

First, I need to parse the `pip list` output to create a dictionary or a lookup table of `package_name -> version`. The package names in `pip list` are case-insensitive and often use hyphens, whereas `pyproject.toml` might use underscores or different capitalization. I need to handle this mapping carefully.

**`pip list` output parsing:**
I will iterate through the lines of the `pip list` output, skipping the header. For each line, I'll split it into the package name and version.

**Mapping `pyproject.toml` dependencies to `pip list` packages:**

*   **`[tool.poetry.dependencies]` (Main Dependencies):**
    *   `PySide6`: `pip list` shows `PySide6` version `6.9.1`. The current constraint is `^6.9.0`. The new constraint should be `^6.9.1`. Using a caret `^` is standard practice for Poetry to allow compatible updates, so updating the base version is the correct approach. I will use `^6.9.1`.
    *   `SQLAlchemy`: `pip list` shows `SQLAlchemy` version `2.0.41`. The current constraint is `version = ">=2.0.0"`. This is a complex object. I should update it to `version = "^2.0.41"`. This is more specific and aligns with the goal of pinning to current versions while allowing minor compatible updates.
    *   `asyncpg`: `pip list` shows `0.30.0`. Current is `>=0.25.0`. New should be `^0.30.0`.
    *   `alembic`: `pip list` shows `1.16.2`. Current is `>=1.7.5`. New should be `^1.16.2`.
    *   `pydantic`: `pip list` shows `2.11.7`. Current is `version = "^2.0", extras = ["email"]`. I'll update to `version = "^2.11.7"`. The `extras` part must be preserved.
    *   `reportlab`: `pip list` shows `4.4.2`. Current is `>=3.6.6`. New should be `^4.4.2`.
    *   `openpyxl`: `pip list` shows `3.1.5`. Current is `>=3.0.9`. New should be `^3.1.5`.
    *   `python-dateutil`: `pip list` shows `2.9.0.post0`. Current is `>=2.8.2`. New should be `^2.9.0.post0`.
    *   `bcrypt`: `pip list` shows `4.3.0`. Current is `>=3.2.0`. New should be `^4.3.0`.

*   **`[tool.poetry.group.dev.dependencies]` (Development Dependencies):**
    *   `pytest`: `pip list` shows `8.4.1`. Current is `^7.0`. New should be `^8.4.1`.
    *   `pytest-cov`: `pip list` shows `6.2.1`. Current is `^4.0`. New should be `^6.2.1`.
    *   `flake8`: `pip list` shows `7.3.0`. Current is `^6.0`. New should be `^7.3.0`.
    *   `black`: `pip list` shows `25.1.0`. Current is `^24.0`. New should be `^25.1.0`.
    *   `mypy`: `pip list` shows `1.16.1`. Current is `^1.0`. New should be `^1.16.1`.
    *   `pre-commit`: `pip list` shows `4.2.0`. Current is `^3.0`. New should be `^4.2.0`.
    *   `pytest-qt`: `pip list` shows `4.4.0`. Current is `^4.0`. New should be `^4.4.0`.
    *   `pytest-asyncio`: `pip list` shows `1.0.0`. Current is `^0.21.0`. New should be `^1.0.0`.

**Versioning Strategy:**
The user just wants to update to the *currently installed* versions. A common practice with `poetry` is to use caret requirements (`^version`) which means "compatible with this version". For example, `^1.2.3` is equivalent to `>=1.2.3, <2.0.0`. This is a good balance between locking versions for reproducibility and allowing non-breaking updates. The existing file already uses a mix of `>=`, `^`, and complex objects. I'll standardize on `^` for simplicity and best practice, as it's what `poetry add` would do.

For example, for `SQLAlchemy` (current `>=2.0.0`, installed `2.0.41`), changing to `^2.0.41` is a sensible update.
For `pytest-asyncio` (current `^0.21.0`, installed `1.0.0`), the update to `^1.0.0` is a major version jump, which is exactly what the `pip list` indicates has happened.

I need to be careful to preserve the structure, especially for `SQLAlchemy` and `pydantic` which are defined as tables (inline blocks).

**Plan of Action:**
1.  Create a dictionary mapping of all packages from the `pip list` output. The keys should be normalized to lowercase for easy lookup. `package_name.lower() -> version`.
2.  Load the original `pyproject.toml` content.
3.  Go through each dependency in `[tool.poetry.dependencies]` and `[tool.poetry.group.dev.dependencies]`.
4.  For each dependency, find its corresponding version in my parsed `pip list` dictionary.
5.  Construct the new version string as `^<version>`.
6.  Replace the old version string with the new one.
7.  For dependencies with special formats (like SQLAlchemy and Pydantic), I will carefully edit only the `version` key within their respective tables.
8.  Ensure all other sections of the file (`[tool.poetry]`, `[tool.poetry.scripts]`, `[build-system]`, `[tool.black]`, `[tool.pytest.ini_options]`) are left completely untouched.
9.  Present the final, complete file.

### **3. Implementation Planning & Execution**

Let's do a dry run of the replacements.

**Original `[tool.poetry.dependencies]`:**
```toml
python = ">=3.9,<3.13" 
PySide6 = "^6.9.0"
SQLAlchemy = {extras = ["asyncio"], version = ">=2.0.0"}
asyncpg = ">=0.25.0"
alembic = ">=1.7.5"
pydantic = {version = "^2.0", extras = ["email"]}
reportlab = ">=3.6.6"
openpyxl = ">=3.0.9"
python-dateutil = ">=2.8.2"
bcrypt = ">=3.2.0"
```

**`pip list` lookup:**
*   `PySide6`: `6.9.1` -> `^6.9.1`
*   `SQLAlchemy`: `2.0.41` -> `^2.0.41`
*   `asyncpg`: `0.30.0` -> `^0.30.0`
*   `alembic`: `1.16.2` -> `^1.16.2`
*   `pydantic`: `2.11.7` -> `^2.11.7`
*   `reportlab`: `4.4.2` -> `^4.4.2`
*   `openpyxl`: `3.1.5` -> `^3.1.5`
*   `python-dateutil`: `2.9.0.post0` -> `^2.9.0.post0`
*   `bcrypt`: `4.3.0` -> `^4.3.0`

**Updated `[tool.poetry.dependencies]`:**
```toml
python = ">=3.9,<3.13" 
PySide6 = "^6.9.1"
SQLAlchemy = {extras = ["asyncio"], version = "^2.0.41"}
asyncpg = "^0.30.0"
alembic = "^1.16.2"
pydantic = {version = "^2.11.7", extras = ["email"]}
reportlab = "^4.4.2"
openpyxl = "^3.1.5"
python-dateutil = "^2.9.0.post0"
bcrypt = "^4.3.0"
```
Looks correct. I will also reorder the `pydantic` keys to match the original (`version` first), just to be minimally invasive.

**Original `[tool.poetry.group.dev.dependencies]`:**
```toml
pytest = "^7.0"
pytest-cov = "^4.0"
flake8 = "^6.0"
black = "^24.0" 
mypy = "^1.0" 
pre-commit = "^3.0"
pytest-qt = "^4.0"
pytest-asyncio = "^0.21.0"
```

**`pip list` lookup:**
*   `pytest`: `8.4.1` -> `^8.4.1`
*   `pytest-cov`: `6.2.1` -> `^6.2.1`
*   `flake8`: `7.3.0` -> `^7.3.0`
*   `black`: `25.1.0` -> `^25.1.0`
*   `mypy`: `1.16.1` -> `^1.16.1`
*   `pre-commit`: `4.2.0` -> `^4.2.0`
*   `pytest-qt`: `4.4.0` -> `^4.4.0`
*   `pytest-asyncio`: `1.0.0` -> `^1.0.0`

**Updated `[tool.poetry.group.dev.dependencies]`:**
```toml
pytest = "^8.4.1"
pytest-cov = "^6.2.1"
flake8 = "^7.3.0"
black = "^25.1.0"
mypy = "^1.16.1"
pre-commit = "^4.2.0"
pytest-qt = "^4.4.0"
pytest-asyncio = "^1.0.0"
```
This also looks correct. The trailing whitespace on some lines should be preserved if possible, but it's not critical. TOML is not whitespace-sensitive in this way. I will clean it up slightly for consistency (remove trailing whitespace on `black` and `mypy` lines).

### **4. Final Validation (Internal `diff`)**

I will now construct the complete file in my mind and perform a `diff` against the original.

**Original:**
```toml
# File: pyproject.toml
[tool.poetry]
...
packages = [{include = "app", from = "."}]

[tool.poetry.dependencies]
python = ">=3.9,<3.13" 
PySide6 = "^6.9.0"   # The QtCharts module from this package is used for the dashboard
SQLAlchemy = {extras = ["asyncio"], version = ">=2.0.0"}
asyncpg = ">=0.25.0"
alembic = ">=1.7.5"
pydantic = {version = "^2.0", extras = ["email"]}
reportlab = ">=3.6.6"
openpyxl = ">=3.0.9"
python-dateutil = ">=2.8.2"
bcrypt = ">=3.2.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.0"
pytest-cov = "^4.0"
flake8 = "^6.0"
black = "^24.0" 
mypy = "^1.0" 
pre-commit = "^3.0"
pytest-qt = "^4.0"
pytest-asyncio = "^0.21.0" 

[tool.poetry.scripts]
...
```

**New:**
```toml
# File: pyproject.toml
[tool.poetry]
...
packages = [{include = "app", from = "."}]

[tool.poetry.dependencies]
python = ">=3.9,<3.13"
PySide6 = "^6.9.1"   # The QtCharts module from this package is used for the dashboard
SQLAlchemy = {extras = ["asyncio"], version = "^2.0.41"}
asyncpg = "^0.30.0"
alembic = "^1.16.2"
pydantic = {version = "^2.11.7", extras = ["email"]}
reportlab = "^4.4.2"
openpyxl = "^3.1.5"
python-dateutil = "^2.9.0.post0"
bcrypt = "^4.3.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.4.1"
pytest-cov = "^6.2.1"
flake8 = "^7.3.0"
black = "^25.1.0"
mypy = "^1.16.1"
pre-commit = "^4.2.0"
pytest-qt = "^4.4.0"
pytest-asyncio = "^1.0.0"

[tool.poetry.scripts]
...
```

**Mental `diff` results:**
*   `- PySide6 = "^6.9.0"`
*   `+ PySide6 = "^6.9.1"`
*   `- SQLAlchemy = {extras = ["asyncio"], version = ">=2.0.0"}`
*   `+ SQLAlchemy = {extras = ["asyncio"], version = "^2.0.41"}`
*   `- asyncpg = ">=0.25.0"`
*   `+ asyncpg = "^0.30.0"`
*   `- alembic = ">=1.7.5"`
*   `+ alembic = "^1.16.2"`
*   `- pydantic = {version = "^2.0", extras = ["email"]}`
*   `+ pydantic = {version = "^2.11.7", extras = ["email"]}`
*   `- reportlab = ">=3.6.6"`
*   `+ reportlab = "^4.4.2"`
*   `- openpyxl = ">=3.0.9"`
*   `+ openpyxl = "^3.1.5"`
*   `- python-dateutil = ">=2.8.2"`
*   `+ python-dateutil = "^2.9.0.post0"`
*   `- bcrypt = ">=3.2.0"`
*   `+ bcrypt = "^4.3.0"`
*   `- pytest = "^7.0"`
*   `+ pytest = "^8.4.1"`
*   `- pytest-cov = "^4.0"`
*   `+ pytest-cov = "^6.2.1"`
*   `- flake8 = "^6.0"`
*   `+ flake8 = "^7.3.0"`
*   `- black = "^24.0"`
*   `+ black = "^25.1.0"`
*   `- mypy = "^1.0"`
*   `+ mypy = "^1.16.1"`
*   `- pre-commit = "^3.0"`
*   `+ pre-commit = "^4.2.0"`
*   `- pytest-qt = "^4.0"`
*   `+ pytest-qt = "^4.4.0"`
*   `- pytest-asyncio = "^0.21.0"`
*   `+ pytest-asyncio = "^1.0.0"`

All other lines and sections are identical. The comment on the `PySide6` line is preserved. The structure of the `SQLAlchemy` and `pydantic` tables is preserved. The logic is sound. I am ready to generate the final response. I will introduce it with a brief explanation of the changes made, as per my communication protocol.Of course. I will help you create a *complete* updated *replacement* file for `pyproject.toml`.

Following my operational principles, I have carefully analyzed the provided `pip list` output and the original `pyproject.toml` file. My approach is to:
1.  Map every dependency in the `[tool.poetry.dependencies]` and `[tool.poetry.group.dev.dependencies]` sections to its corresponding version from your installed packages list.
2.  Update the version specifiers to use the caret (`^`) prefix (e.g., `^1.2.3`), which is a Poetry best practice. This locks the version for reproducibility while allowing non-breaking, compatible updates.
3.  Preserve the exact structure of the original file, including all metadata, scripts, comments, and tool configurations.
4.  Ensure that complex dependency definitions (like those for `SQLAlchemy` and `pydantic`) are updated correctly without altering their extra requirements.

Here is the complete and carefully updated `pyproject.toml` file.

***

```toml
# File: pyproject.toml
[tool.poetry]
name = "sg-bookkeeper"
version = "1.0.0"
description = "Singapore small business bookkeeping application"
authors = ["Your Name <your.email@example.com>"]
license = "MIT"
readme = "README.md"
homepage = "https://github.com/yourusername/sg_bookkeeper"
repository = "https://github.com/yourusername/sg_bookkeeper"
keywords = ["accounting", "bookkeeping", "singapore", "gst", "tax"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Financial and Insurance Industry",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12", 
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Topic :: Office/Business :: Financial :: Accounting",
]
packages = [{include = "app", from = "."}]

[tool.poetry.dependencies]
python = ">=3.9,<3.13" 
PySide6 = "^6.9.1"   # The QtCharts module from this package is used for the dashboard
SQLAlchemy = {extras = ["asyncio"], version = "^2.0.41"}
asyncpg = "^0.30.0"
alembic = "^1.16.2"
pydantic = {version = "^2.11.7", extras = ["email"]}
reportlab = "^4.4.2"
openpyxl = "^3.1.5"
python-dateutil = "^2.9.0.post0"
bcrypt = "^4.3.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.4.1"
pytest-cov = "^6.2.1"
flake8 = "^7.3.0"
black = "^25.1.0"
mypy = "^1.16.1"
pre-commit = "^4.2.0"
pytest-qt = "^4.4.0"
pytest-asyncio = "^1.0.0"

[tool.poetry.scripts]
sg_bookkeeper = "app.main:main"
sg_bookkeeper_db_init = "app.core.db_initializer:main"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 88
target-version = ['py39', 'py310', 'py311', 'py312']

[tool.pytest.ini_options]
python_files = "test_*.py tests.py" 
python_classes = "Test*"
python_functions = "test_*"
asyncio_mode = "auto"
```

---
https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221-gL5DsFqqJMZdqY4M7-HfAE2ikMQaMnV%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing

