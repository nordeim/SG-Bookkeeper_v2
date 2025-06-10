# Project Test Guide: SG Bookkeeper

This guide provides instructions on how to set up the testing environment and run the automated tests for the SG Bookkeeper application. A comprehensive test suite is crucial for maintaining code quality, ensuring correctness of business logic, and preventing regressions.

## 1. Prerequisites

*   **Python Environment**: Ensure you have Python (version specified in `pyproject.toml`, e.g., 3.9+) and Poetry installed.
*   **Dependencies**: All development dependencies, including testing libraries (`pytest`, `pytest-asyncio`, `pytest-cov`, `unittest.mock`), should be installed. If you set up the project using `poetry install --with dev` (recommended) or `poetry install` (if dev dependencies are not in a separate group), these should already be available in your project's virtual environment.

## 2. Test Structure

The tests are organized within the `tests/` root directory, mirroring the application's structure to facilitate navigation and maintenance.

*   **`tests/conftest.py`**:
    *   This file is used for project-wide pytest fixtures and configuration. It might contain shared setup/teardown logic or helper fixtures accessible by all tests.

*   **`tests/unit/`**:
    *   Contains unit tests designed to test individual modules, classes, or functions in isolation. These tests heavily utilize mocks for external dependencies (like services or the database) to ensure the component's logic is tested independently.
    *   Subdirectories further organize these tests by application module:
        *   `core/`: Unit tests for critical core components, such as the `SecurityManager`.
        *   `accounting/`: Unit tests for accounting-related business logic managers, like the `JournalEntryManager`.
        *   `business_logic/`: Unit tests for core business process orchestrators, such as the `CustomerManager`.
        *   `tax/`: Unit tests for tax-related components (e.g., `TaxCalculator`, `GSTManager`).
        *   `utils/`: Unit tests for utility classes (e.g., `SequenceGenerator`) and validation rules in Pydantic models.
        *   `services/`: A comprehensive suite of tests for the data access layer classes (e.g., `AccountService`, `BankReconciliationService`, `CustomerService`, etc.).
        *   `reporting/`: Unit tests for reporting logic components (e.g., `DashboardManager`, `FinancialStatementGenerator`).

*   **`tests/integration/`**:
    *   Contains integration tests that verify interactions between multiple components. These tests might involve a real (test) database to ensure components work together correctly.
    *   Currently, a basic structure exists, with more comprehensive integration tests planned.

*   **`tests/ui/`**:
    *   Intended for UI-level functional tests, likely using frameworks like `pytest-qt`.
    *   Currently, a basic structure exists, with UI test implementation planned for the future.

## 3. Running Tests

All tests are run using `pytest` from the root directory of the project. Ensure your Poetry virtual environment is activated (e.g., by running `poetry shell` in the project root) or prepend commands with `poetry run`.

### 3.1. Running All Tests

To run all discovered tests (unit, integration, UI):

```bash
poetry run pytest
```

Or, if your Poetry shell is activated:

```bash
pytest
```

### 3.2. Running Specific Test Files or Directories

You can target specific parts of the test suite:

*   Run all tests in a directory (e.g., `tests/unit/services/`):
    ```bash
    poetry run pytest tests/unit/services/
    ```
*   Run a specific test file (e.g., `tests/unit/tax/test_tax_calculator.py`):
    ```bash
    poetry run pytest tests/unit/tax/test_tax_calculator.py
    ```
*   Run a specific test function within a file using `::test_function_name`:
    ```bash
    poetry run pytest tests/unit/core/test_security_manager.py::test_authenticate_user_success
    ```
*   Run tests based on markers (if defined in tests, e.g., `@pytest.mark.slow`):
    ```bash
    poetry run pytest -m slow
    ```

### 3.3. Test Verbosity

For more detailed output from pytest:

*   Show individual test names as they run:
    ```bash
    poetry run pytest -v
    ```
*   Show even more verbose output, including captured standard output from tests:
    ```bash
    poetry run pytest -vv
    ```

### 3.4. Test Coverage

To generate a test coverage report (requires the `pytest-cov` plugin, which is included in dev dependencies):

*   Print a coverage summary to the console for the `app` directory:
    ```bash
    poetry run pytest --cov=app tests/
    ```
*   Generate an HTML coverage report for a more detailed, browsable view:
    ```bash
    poetry run pytest --cov=app --cov-report=html tests/
    ```
    This will create an `htmlcov/` directory in your project root. Open `htmlcov/index.html` in a web browser to view the report.

### 3.5. Running Asynchronous Tests

Tests involving `async def` functions are automatically discovered and run by `pytest` when `pytest-asyncio` is installed (it is a dev dependency). `pytest-asyncio` is configured with `asyncio_mode = auto` in `pyproject.toml`, which handles most asynchronous test cases seamlessly.

## 4. Viewing Test Results

Pytest provides immediate feedback in the console:
*   `.` (dot): Indicates a passed test.
*   `F`: Indicates a test that failed an assertion.
*   `E`: Indicates an error occurred during test setup or execution (not an assertion failure).
*   `s`: Indicates a skipped test (e.g., marked with `@pytest.mark.skip` or `pytest.skip()`).
*   `x`: Indicates an "expected failure" (marked with `@pytest.mark.xfail`).

For `F` and `E` results, pytest will print detailed information, including tracebacks and assertion differences, to help diagnose the issue.

## 5. Writing New Tests

When adding new tests, adhere to the following conventions to maintain consistency and quality.

*   **Location**:
    *   Place new unit tests in the appropriate subdirectory under `tests/unit/`.
    *   Integration tests go into `tests/integration/`.
    *   UI tests go into `tests/ui/`.
*   **File Naming**: Test files must start with `test_` (e.g., `test_my_new_feature.py`).
*   **Function Naming**: Test functions must start with `test_` (e.g., `def test_specific_behavior():`).
*   **Class Naming**: If using classes to group tests, class names must start with `Test` (e.g., `class TestMyComponent:`).
*   **Fixtures**: Utilize `pytest` fixtures (defined in `conftest.py` or locally in test files) for setting up test preconditions and managing resources. This is the preferred way to provide mocked objects to tests.
*   **Mocking Strategy**:
    *   For **Service Layer** tests, mock the database session (`AsyncSession`) and its methods (`get`, `execute`, etc.).
    *   For **Manager Layer** tests, mock the *Service Layer* dependencies. Do not mock the database directly. The goal is to test the manager's orchestration and business logic in isolation from the data access implementation.
*   **Assertions**: Use standard Python `assert` statements for checks.
*   **Expected Exceptions**: To test for expected exceptions, use `with pytest.raises(ExceptionType):`.
*   **Asynchronous Tests**: For testing asynchronous code, define test functions with `async def`. Use `AsyncMock` from `unittest.mock` for mocking coroutines.

By following these guidelines, we aim to build and maintain a comprehensive and robust suite of automated tests, ensuring the quality and stability of the SG Bookkeeper application.
