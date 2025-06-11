Of course. This is an excellent and necessary step to ensure the project's documentation is as robust and up-to-date as its codebase. I will perform a deep, systematic analysis of the entire provided codebase, including the test suite, and then generate a new, substantially more detailed `README.md` as requested.

### **CodeNavigator Analysis Report: Test Suite Validation**

Before updating the documentation, I have performed a comprehensive review of the provided test suite (`tests/`) to ensure the "Testing" section of the new `README.md` is accurate and insightful.

**1. Test Structure and Organization:**
*   The test suite is well-organized into `unit/`, `integration/`, and `ui/` directories.
*   The `unit/` directory is further subdivided by application layer (e.g., `services/`, `tax/`, `reporting/`), which is an excellent practice that makes tests easy to locate and maintain.
*   The use of `__init__.py` files correctly establishes the package structure.
*   `conftest.py` is present, correctly positioned for project-wide pytest fixtures.

**2. Test Quality and Patterns:**
*   **Isolation**: The unit tests demonstrate a strong understanding of mocking and isolation.
    *   **Service-level tests** (e.g., `test_payment_service.py`, `test_sales_invoice_service.py`) correctly mock the `DatabaseManager` and its `session`, ensuring that only the service's logic (query construction, object handling) is being tested, not the database itself.
    *   **Manager-level tests** (e.g., `test_gst_manager.py`) correctly mock the *service* dependencies, properly testing the manager's orchestration logic in isolation.
*   **Fixtures**: `pytest` fixtures are used effectively to provide mocked objects and set up test preconditions, leading to cleaner and more readable test cases.
*   **Asynchronicity**: The tests correctly use `async def` and the `pytest-asyncio` marker, and dependencies like `AsyncMock` are used appropriately for testing asynchronous code.
*   **Validation Logic**: A key strength is the presence of tests for Pydantic models (`test_pydantic_models_journal_entry.py`), which validates the application's core data contracts.

**3. Test Coverage (Qualitative Assessment):**
*   **Strengths**: There is good foundational coverage for many of the data access services and some key business logic components like the `TaxCalculator` and `GSTManager`. The existing tests provide a solid safety net for those parts of the codebase.
*   **Gaps and Opportunities**:
    *   **New Features**: There are currently no tests for the new, complex `ForexManager`. This is a critical gap that should be addressed.
    *   **Manager Logic**: While `GSTManager` has tests, many other managers (`PaymentManager`, `SalesInvoiceManager`, etc.) lack dedicated unit tests for their orchestration logic.
    *   **Integration and UI**: The `integration/` and `ui/` directories are placeholders, indicating a lack of end-to-end and UI-level functional tests. This is a common progression for a project but represents the next frontier for quality assurance.
    *   **Obsolete Tests**: The file `test_sequence_generator.py` is now obsolete, as the `SequenceGenerator` class was refactored out in favor of using `SequenceService` directly. This test file should be removed in a future cleanup.

**Conclusion:** The existing unit test suite is of high quality and follows best practices. The primary need is to expand coverage to encompass the new, complex business logic in the managers and to begin building out the integration test suite.

---

### **Complete Updated File: `README.md`**

This `README.md` has been substantially expanded to reflect the latest state of the project, its new features, and its architecture, using the provided reference documents to ensure a high level of detail.

```markdown
# SG Bookkeeper

<div align="center">

<img src="https://raw.githubusercontent.com/nordeim/SG-Bookkeeper/refs/heads/main/home_screen.png" alt="SG Bookkeeper Logo" width="600"/>

**Singapore-Focused Small Business Accounting Software**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PySide6 6.9+](https://img.shields.io/badge/UI-PySide6_6.9-green.svg)](https://doc.qt.io/qtforpython/)
[![PostgreSQL 14+](https://img.shields.io/badge/DB-PostgreSQL_14+-blue.svg)](https://www.postgresql.org/)
[![SQLAlchemy 2.0+](https://img.shields.io/badge/ORM-SQLAlchemy_2.0-orange.svg)](https://www.sqlalchemy.org/)
[![Asyncpg](https://img.shields.io/badge/Async-Asyncpg-purple.svg)](https://github.com/MagicStack/asyncpg)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests: Pytest](https://img.shields.io/badge/tests-pytest-yellowgreen)](https://pytest.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

[Key Features](#key-features) • [Technology Stack](#technology-stack) • [Installation](#installation) • [Usage Guide](#usage-guide) • [Project Structure](#project-structure) • [Testing](#testing) • [Contributing](#contributing) • [Roadmap](#roadmap) • [License](#license)

</div>

## Overview

SG Bookkeeper is a comprehensive, cross-platform desktop application designed to meet the accounting and bookkeeping needs of small to medium-sized businesses (SMBs) in Singapore. Built with Python and leveraging the power of PySide6 for a modern user interface and PostgreSQL for robust data management, it offers professional-grade financial tools tailored to Singapore's regulatory environment.

The application is architected from the ground up to handle real-world business complexity. It features a full **multi-company architecture**, allowing users to manage multiple, completely isolated businesses from a single installation. At its heart is a robust **double-entry accounting core**, ensuring every transaction is properly balanced and accounted for. The system natively supports **multi-currency accounting**, automatically calculating and posting realized foreign exchange gains/losses at the time of payment settlement, and provides a period-end procedure for revaluing open balances to account for unrealized gains/losses.

Compliance with Singapore's regulatory landscape is a primary design goal. The application includes integrated **GST management** (including 9% rate calculations and detailed F5 return preparation) and handles **Withholding Tax (WHT)** obligations directly within the vendor payment workflow. Its advanced **Bank Reconciliation module** provides a powerful and intuitive interface for matching bank statements with system transactions, supporting CSV imports, persistent draft reconciliations, and visual aids for complex matching scenarios. A dynamic **Dashboard** provides at-a-glance KPIs, including graphical aging summaries and key financial ratios, calculated for any user-selected date.

## Why SG Bookkeeper?

-   **Multi-Company Support**: Manage multiple distinct businesses from a single installation. A guided wizard simplifies the creation of new company files, each with its own secure, isolated PostgreSQL database, ensuring complete data segregation and confidentiality between business entities.

-   **Singapore-Centric**: The application is designed with a deep understanding of the Singaporean business context. It correctly handles the 9% GST rate, facilitates the preparation of data for the GST F5 return, and integrates Withholding Tax (WHT) calculations into the payment workflow, aligning with local IRAS requirements.

-   **Handles Complexity with Ease**: SG Bookkeeper is built to manage the complexities of modern business. It features a full multi-currency engine that not only records transactions in their native currency but also automatically computes and posts realized foreign exchange gains or losses when payments are settled at a different exchange rate. A period-end revaluation tool further allows for the calculation of unrealized gains/losses on open AR, AP, and bank balances.

-   **Professional Grade & Audit-Ready**: Beyond basic bookkeeping, the application implements a full double-entry accounting system to ensure financial accuracy. Its database features a comprehensive, trigger-based audit trail that logs every data modification. This detailed history is fully accessible and filterable through the UI, providing unparalleled transparency and making the system audit-ready.

-   **User-Friendly and Intuitive Interface**: While powerful, the application is designed for usability. A modern Qt-based interface, a wizard-driven setup for new companies, and visual aids in complex modules like bank reconciliation make powerful features accessible to users who may not be accounting experts, without sacrificing the depth needed by professionals.

-   **Open Source & Local First**: As an open-source project, development is transparent and community-driven. Critically, your financial data is stored locally on your machine or on a private server of your choice. This "local-first" approach ensures complete data privacy, security, and control, with no recurring subscription fees.

-   **Modern & Performant**: The application's architecture leverages modern Python features and a dedicated `asyncio` event loop for all database and long-running operations. This ensures the user interface remains fluid, responsive, and free from freezing, even during complex calculations or data-intensive tasks.

## Key Features

### Core Accounting & System
-   **Multi-Company Management**: Create new, isolated company databases using a guided wizard. A central `CompanyManager` allows for seamless switching between different business entities via an application restart, updating the database connection accordingly.
-   **Double-Entry Bookkeeping**: The application is built on a strict double-entry accounting foundation, ensuring that for every transaction, debits equal credits, maintaining the integrity of the financial records at all times.
-   **Hierarchical Chart of Accounts**: A fully interactive UI allows for the creation, editing, and deactivation of accounts. The COA supports parent-child relationships, enabling a clear, hierarchical structure. Accounts can be tagged with a **Cash Flow Category** (`Operating`, `Investing`, `Financing`) to automate the generation of the Statement of Cash Flows.
-   **General Ledger**: Provides a detailed, filterable view of all transactions for any selected account within a given date range. The report can be exported to both PDF and Excel for further analysis.
-   **Journal Entry System**: A dedicated UI for creating, editing, and posting manual journal entries. The system also auto-generates and posts complex journal entries from source documents like invoices and payments, ensuring all business activities are reflected in the general ledger. Posted entries can be reversed with a single action, which creates and posts a corresponding reversing entry.
-   **Multi-Currency Accounting**:
    -   **Realized Gain/Loss**: When a foreign currency invoice is paid on a date with a different exchange rate, the `PaymentManager` automatically calculates the realized gain or loss on the settlement and includes it as a line item in the payment's journal entry.
    -   **Unrealized Gain/Loss**: A period-end procedure, available in the "Period-End Procedures" tab, allows users to revalue all open foreign currency AR, AP, and bank balances as of a specific date. The `ForexManager` calculates the unrealized gain or loss and posts a main adjustment JE for the period-end and an automatic reversing JE for the first day of the next period.
-   **Fiscal Year and Period Management**: A UI in the Settings module allows for the creation of fiscal years. Once a year is created, monthly or quarterly accounting periods can be automatically generated, providing the structure for financial reporting.

### Singapore Tax Compliance
-   **GST Tracking and Calculation**: The system uses configurable tax codes (e.g., SR for Standard Rate, ZR for Zero Rate, ES for Exempt, TX for Taxable Purchases) to track GST on transactions. The `TaxCalculator` service provides centralized logic for applying the correct tax rate (including the 9% GST rate) to line items.
-   **GST F5 Return Data Preparation**: The Reports module includes a feature to generate the data required for the IRAS GST F5 return for any given period. It calculates values for each box (e.g., Box 1: Standard-Rated Supplies, Box 5: Taxable Purchases) and allows for the finalization of the return, which automatically posts a settlement journal entry to clear the GST input and output tax accounts to a central GST control account. A detailed Excel export provides a full breakdown of the transactions contributing to each box.
-   **Withholding Tax (WHT) Management**: Vendors can be flagged as subject to withholding tax. When creating a payment for such a vendor, the `PaymentDialog` provides an option to apply WHT. If selected, the system automatically calculates the WHT amount and creates a journal entry that correctly clears the full Accounts Payable liability while crediting both the bank account (for the net payment) and a `WHT Payable` liability account.
-   **Income Tax Computation Report**: A preliminary tax computation report can be generated from the Reports module. It starts with the Profit & Loss statement's net profit and allows for adjustments based on accounts tagged with tax treatments like "Non-Deductible," providing an estimated chargeable income.

### Business Operations
-   **Customer, Vendor, Product/Service Management**: Comprehensive modules for managing core business entities with full Create, Read, Update, Delete (CRUD) functionality, list views with searching/filtering, and detailed data entry dialogs.
-   **Sales & Purchase Invoicing**: Full lifecycle management from draft to posting. When an invoice is posted, the system automatically generates the necessary financial journal entries and, for inventory items, creates `InventoryMovement` records based on a Weighted Average Cost (WAC) model.
-   **Payment Processing**: A dedicated module for recording customer receipts and vendor payments. The payment dialog allows for the allocation of a single payment across multiple outstanding invoices. The `PaymentManager` robustly handles the creation of complex journal entries that can include invoice settlement, bank transactions, realized forex gain/loss, and withholding tax liabilities all in a single, balanced transaction.
-   **Inventory Control (Weighted Average Cost)**: For products designated as 'Inventory' type, the system tracks stock movements. Posting a purchase invoice increases inventory quantity and updates the weighted average cost. Posting a sales invoice decreases quantity and generates a COGS journal entry based on the WAC at the time of sale.

### Banking & Reconciliation
-   **Bank Account Management**: A dedicated module for managing multiple bank accounts, each linked to a specific GL account in the Chart of Accounts.
-   **Bank Transaction Management**: Supports both manual entry of bank transactions and **CSV bank statement import**. The importer features a configurable column mapping dialog, allowing users to adapt to various bank statement formats, and provides detailed, row-level error reporting for any issues during the import process.
-   **Advanced Bank Reconciliation Module**:
    -   **Persistent Drafts**: Users can start a reconciliation, save their progress (including provisionally matched items), and resume later.
    -   **Interactive UI**: A two-table layout allows users to match imported statement items against system-generated bank transactions. The UI provides real-time updates of running totals and the outstanding difference.
    -   **Visual Matching**: Matched items are visually grouped using background colors, making it easy to see what has been reconciled in the current session.
    -   **Direct JE Creation**: Unmatched statement items like bank fees or interest can be accounted for by creating a journal entry directly from the reconciliation screen, which in turn generates a new system transaction ready for matching.
    -   **History**: A complete history of finalized reconciliations is maintained and viewable.

### Reporting & Analytics
-   **Standard Financial Statements**: The system generates a full suite of standard financial reports:
    *   Balance Sheet
    *   Profit & Loss Statement
    *   Trial Balance
    *   Statement of Cash Flows (using the indirect method, automated via account tagging)
    All reports are viewable on-screen and can be exported to professionally formatted PDF and Excel files.
-   **Dashboard with KPIs**: The main dashboard provides an interactive overview of the business's financial health.
    -   **Key Metrics**: Displays YTD Profit & Loss, Current Cash Balance, and Total Outstanding AR/AP.
    -   **Financial Ratios**: Calculates and displays the Current Ratio, Quick Ratio, and Debt-to-Equity Ratio.

### System & Security
-   **User Authentication & RBAC**: A complete security module handles user login with `bcrypt` password hashing. The system supports creating multiple roles with granular permissions, which are then assigned to users.
-   **Comprehensive Audit Trails**: A powerful, trigger-based audit system in the PostgreSQL database automatically logs every `INSERT`, `UPDATE`, and `DELETE` on key tables. The UI in the Settings module provides a filterable and paginated view of both high-level actions (`AuditLog`) and detailed field-level changes (`DataChangeHistory`), providing exceptional transparency and accountability.

## Technology Stack
-   **Programming Language**: Python 3.9+ (up to 3.12). Chosen for its extensive ecosystem, readability, and strong support for asynchronous programming.
-   **UI Framework**: PySide6 6.9.0+. The official Qt for Python bindings, providing access to the mature and powerful Qt framework for creating modern, cross-platform desktop applications.
-   **Database**: PostgreSQL 14+. Selected for its robustness, ACID compliance, and advanced features like triggers, custom functions, and JSONB support, which are heavily utilized for data integrity and auditing.
-   **ORM**: SQLAlchemy 2.0+. The de-facto standard for Python ORMs, providing a powerful and flexible way to interact with the database. The application leverages its modern asynchronous (asyncio) capabilities.
-   **Async DB Driver**: `asyncpg`. A high-performance, asyncio-native driver for PostgreSQL.
-   **Data Validation (DTOs)**: Pydantic V2. Used extensively for creating Data Transfer Objects, which enforce strict data contracts between application layers, provide automatic validation, and improve code clarity.
-   **Password Hashing**: `bcrypt`. A secure, industry-standard library for hashing user passwords.
-   **Reporting Libraries**: `reportlab` for generating professional PDF documents, and `openpyxl` for creating richly formatted Excel spreadsheets.
-   **Dependency Management**: Poetry. A modern Python packaging and dependency management tool that ensures reproducible builds.
-   **Date/Time Utilities**: `python-dateutil`. For robust handling of complex date calculations, such as in recurring entry generation.
-   **Testing**: Pytest, with `pytest-asyncio` for testing asynchronous code and `pytest-cov` for coverage analysis. `unittest.mock` is used for creating mock objects.

## Installation

This guide is for developers setting up the application from source.

### Prerequisites
-   Python 3.9 or higher
-   PostgreSQL Server 14 or higher (with admin/superuser access for initial setup)
-   Poetry
-   Git

### Developer Installation Steps
1.  **Clone Repository**: `git clone https://github.com/yourusername/sg_bookkeeper.git && cd sg_bookkeeper`
2.  **Install Dependencies**: `poetry install --with dev`
3.  **Configure `config.ini`**:
    *   The application looks for `config.ini` in a platform-specific user config directory (e.g., `~/.config/SGBookkeeper/` on Linux).
    *   Create this directory and a `config.ini` file inside it. Provide your PostgreSQL superuser credentials for the initial database creation. This allows the application to create new company databases on your behalf.
        ```ini
        [Database]
        username = YOUR_POSTGRES_ADMIN_USER
        password = YOUR_POSTGRES_ADMIN_PASSWORD
        host = localhost
        port = 5432
        database = sg_bookkeeper_default
        ```
4.  **Run the Application**: `poetry run sg_bookkeeper`
5.  **Create Your First Company**:
    *   On first run, the application will detect that no company is selected. It will likely prompt you to open the Company Manager.
    *   Alternatively, go to **File > New Company...**.
    *   The **New Company Setup Wizard** will launch. Follow the steps to provide a display name and a unique, valid database name.
    *   Upon clicking "Finish," the application will use the admin credentials from `config.ini` to create the new database, set up the entire schema, and populate it with initial data.
    *   You will be prompted to restart the application to connect to your new company file.
    *   The default login for a new company is `admin` / `password`. You will be required to change this password on first login.

## Usage Guide
-   **Switching Companies**: Go to **File > Open Company...** to launch the `Company Manager` dialog. You can select a different company to open (which will restart the app) or create another new company.
-   **Period-End Procedures**: Navigate to the **Accounting** tab, then the **Period-End Procedures** sub-tab to find the tool for running the **Unrealized Forex Gain/Loss Revaluation**.
-   **Main Modules**: Explore the main tabs for `Dashboard`, `Sales`, `Purchases`, `Payments`, `Banking`, and `Reports` to manage all aspects of your business operations.
-   **Settings**: The `Settings` tab is the central hub for configuring Company Information, managing Fiscal Years/Periods, Users, Roles & Permissions, and viewing the detailed Audit Logs.

## Project Structure
The project uses a layered architecture, with the source code organized as follows:
-   `app/`: Main application package.
    -   `core/`: Central components like `ApplicationCore`, `DatabaseManager`, and `CompanyManager`.
    -   `models/`: SQLAlchemy ORM classes, mirroring the DB schema.
    -   `services/`: The Data Access Layer, implementing the Repository pattern.
    -   `business_logic/`, `accounting/`, `tax/`, `reporting/`: The Business Logic Layer, containing "Manager" classes.
    -   `ui/`: All PySide6 GUI components, organized by feature module.
-   `scripts/`: Database setup scripts (`schema.sql`, `initial_data.sql`, `db_init.py`).
-   `tests/`: All automated tests.

## Database Schema
The PostgreSQL database schema is at version **1.0.7**. It includes tables for core system functions, detailed accounting, business operations, and comprehensive audit trails. Key features include the `cash_flow_category` column in `accounting.accounts` for the Cash Flow Statement, and powerful triggers for auditing and automatic balance updates. Refer to `scripts/schema.sql` for full details.

## Testing
The project emphasizes quality through automated testing using the Pytest framework.
-   **Strategy**: The focus is on comprehensive unit tests with strong isolation, achieved through extensive mocking of dependencies. This ensures that the logic of each component is verified independently. Integration and UI tests are planned for future development cycles.
-   **Current Coverage**: The test suite (`tests/unit/`) provides good coverage for many data access services (verifying query construction and object handling) and critical business logic components like the `TaxCalculator` and `GSTManager`.
-   **Running Tests**:
    *   Run all tests: `poetry run pytest`
    *   Generate a coverage report: `poetry run pytest --cov=app`

## Contributing
Contributions are welcome! Please fork the repository, create a feature branch, make your changes, add relevant tests, and submit a pull request. Adherence to the existing architecture and coding standards is required.

## Roadmap

### Recently Completed
-   **New Company Wizard**: Replaced the simple dialog with a multi-step `QWizard` for a better user experience.
-   **Multi-Currency Accounting**: Implemented calculation and posting of realized forex gains/losses on payments.
-   **Withholding Tax (WHT) Management**: Implemented WHT application on vendor payments with correct JE creation.
-   **Unrealized Forex Revaluation**: Implemented the period-end procedure to revalue open foreign currency balances.
-   **Statement of Cash Flows**: Added a new report that generates a full Statement of Cash Flows using the indirect method.

### Current Focus / Next Steps
-   **WHT Reporting**: Create UI and reports for managing and filing withheld taxes (e.g., generating Form S45).
-   **Advanced Reporting**: Enhance the reporting engine with more customization options and financial analytics.
-   **Automated Testing**: Significantly expand unit test coverage for the new manager classes (`ForexManager`, `PaymentManager`) and begin implementing integration tests for key end-to-end workflows.
-   **User Experience Refinements**: Polish existing UIs based on usability feedback, particularly in the invoicing and payment modules.

### Long-term
-   Inventory Control enhancements (e.g., stocktakes, multiple locations, FIFO/LIFO costing methods).
-   Cloud synchronization options (optional data backup/sync to a user-provided cloud storage).
-   Enhanced Tax Compliance features (e.g., preparation of IRAS Audit File (IAF)).
-   Full UI test suite using a suitable framework (e.g., `pytest-qt`).

## License
This project is licensed under the MIT License.
```

---
https://drive.google.com/file/d/11X3f2mKRWl56NubmyAKo5dwck7p2JaLs/view?usp=sharing, https://drive.google.com/file/d/127qgzFTDe-WAnzFzOzBn2efixfG9w9YE/view?usp=sharing, https://drive.google.com/file/d/131RjCRl_kHc0XtnhCzDmf5bjgJX5iEww/view?usp=sharing, https://drive.google.com/file/d/13B_HcJmxgi3QGYHnj64s275QZN20pg3g/view?usp=sharing, https://drive.google.com/file/d/19n5zeGWlBAwCRFAXfbe4kY5xBK-uV-d7/view?usp=sharing, https://drive.google.com/file/d/1KHIzrVj6ijdFoVTVLa-lfyyVzwf5IYwp/view?usp=sharing, https://drive.google.com/file/d/1M5ybbmzIqj7IUo99Yle7xl_pkczow6Ci/view?usp=sharing, https://drive.google.com/file/d/1P4rxLCG8-5cJ2_vt2qKJqO2wxN26ro9T/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221Rh0wsFMlVjsOSccPUo5JJmfB6gof_tS2%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing, https://drive.google.com/file/d/1T1kVeTCKFOIzPckOmAarcwHC8x0yau1i/view?usp=sharing, https://drive.google.com/file/d/1dAgihzWoQ03fPAECRX4qUzJiiJppPgwz/view?usp=sharing, https://drive.google.com/file/d/1gM89F4jZMNsWNTd9bxJxPfRxY0Y2Vfof/view?usp=sharing, https://drive.google.com/file/d/1hAf_3y-ecY6gAU67N0KzgqGZz1XrDjed/view?usp=sharing, https://drive.google.com/file/d/1iLEa4z_1QZHLh5VEurZg7rUHZneQzsY8/view?usp=sharing, https://drive.google.com/file/d/1jigzShY696C9WmGqx1js_OPVEWWBnXeg/view?usp=sharing, https://drive.google.com/file/d/1mO8_5fwtxIboAdjNo31vNNnNYbzI8-gq/view?usp=sharing, https://drive.google.com/file/d/1pswWDECjQfPpG_vPcb2bGTynwme8P6nA/view?usp=sharing, https://drive.google.com/file/d/1tbuyHau6G4TdCZ0v6u22_ePISFTSNU7r/view?usp=sharing, https://drive.google.com/file/d/1uC_hd3fJooXn4tQQsLJPU3mxW07hDGym/view?usp=sharing, https://drive.google.com/file/d/1yVM3DBOfyPfYckF4q1C8S0ce_9pMnUvz/view?usp=sharing

