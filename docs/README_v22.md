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

The application features a full **multi-company architecture**, a double-entry accounting core, GST management (including 9% rate calculations), **multi-currency accounting with automatic forex gain/loss settlement**, and integrated **Withholding Tax (WHT)** handling. Its reporting suite includes all standard financial statements plus a **Statement of Cash Flows** and preliminary tax computations. A key highlight is the advanced Bank Reconciliation module, which supports CSV imports with detailed error reporting, persistent draft reconciliations, and visual aids for complex transaction matching.

### Why SG Bookkeeper?

-   **Multi-Company Support**: Manage multiple distinct businesses from a single installation, with each company's data securely isolated in its own database.
-   **Singapore-Centric**: Designed with Singapore Financial Reporting Standards (SFRS), GST regulations (including the 9% rate), and IRAS compliance considerations at its core.
-   **Handles Complexity**: Natively supports multi-currency transactions, automatically calculating realized gains/losses on payments, and manages Withholding Tax (WHT) obligations during the vendor payment process.
-   **Professional Grade**: Implements a full double-entry system, detailed audit trails (via database triggers and viewable UI), and robust data validation using Pydantic DTOs.
-   **User-Friendly Interface**: Aims for an intuitive experience for users who may not be accounting experts, while providing depth for professionals. Features include an interactive dashboard, a wizard-based company setup, and visual reconciliation aids.
-   **Open Source & Local First**: Transparent development. Your financial data stays on your local machine or private server, ensuring privacy and control. No subscription fees.
-   **Modern & Performant**: Utilizes asynchronous operations for a responsive UI and efficient database interactions, with a dedicated asyncio event loop.

## Key Features

### Core Accounting & System
-   **Multi-Company Management**: Create new company databases via a guided wizard and switch between them seamlessly.
-   **Double-Entry Bookkeeping**: The core of the application, ensuring all transactions are properly accounted for.
-   **Customizable Hierarchical Chart of Accounts**: Full CRUD UI for managing accounts, including tagging for Cash Flow Statement categories.
-   **General Ledger**: Detailed transaction history with dimension filtering and export options.
-   **Journal Entry System**: UI for manual JEs (CRUD, post, reverse) and auto-generation from source documents.
-   **Multi-Currency Accounting**: Full support for transactions in foreign currencies, with automatic calculation and posting of realized foreign exchange gains and losses at the time of payment settlement.
-   **Unrealized Forex Gain/Loss Revaluation**: A period-end procedure to calculate and post unrealized gains or losses on open foreign currency balances.
-   **Fiscal Year and Period Management**: UI for creating fiscal years and auto-generating monthly or quarterly accounting periods.

### Singapore Tax Compliance
-   **GST Tracking and Calculation**: Based on configurable tax codes (SR, ZR, ES, TX, etc.).
-   **GST F5 Return Data Preparation**: UI to prepare, save drafts, and finalize GST F5 returns with settlement JEs. Includes detailed Excel export for all box lines.
-   **Withholding Tax (WHT) Management**: Apply WHT to vendor payments directly in the payment dialog, automatically creating the `WHT Payable` liability.
-   **Income Tax Computation Report**: Generates a preliminary tax computation based on P&L and accounts tagged as non-deductible or non-taxable.

### Business Operations
-   **Customer, Vendor, Product/Service Management**: Full CRUD and list views with filtering for all core business entities.
-   **Sales & Purchase Invoicing**: Full lifecycle from draft to posting, with inventory and financial JEs created automatically. Includes support for foreign currency invoices.
-   **Payment Processing**: Record customer receipts and vendor payments with allocation to multiple invoices. Natively handles multi-currency payments, Forex Gain/Loss, and WHT.
-   **Inventory Control (Weighted Average Cost)**: `InventoryMovement` records are created on posting documents for 'Inventory' type products.

### Banking
-   **Bank Account Management**: Full CRUD and listing UI, with linkage to a GL account.
-   **Bank Transaction Management**: Manual entry and CSV bank statement import with configurable column mapping and robust, row-level error reporting.
-   **Bank Reconciliation Module**:
    -   Persistent draft reconciliations that can be saved and resumed.
    -   Interactive, real-time feedback for matching transactions with live-updating selection totals.
    -   Visual grouping of provisionally matched items using background colors.
    -   Creation of adjustment Journal Entries directly from the reconciliation screen.

### Reporting & Analytics
-   **Standard Financial Statements**: Balance Sheet, Profit & Loss, Trial Balance, and a new Statement of Cash Flows (Indirect Method). All are viewable and exportable to PDF/Excel.
-   **Dashboard with KPIs**:
    -   Key metrics: YTD P&L, Cash Balance, AR/AP totals.
    -   Financial Ratios: Current Ratio, Quick Ratio, Debt-to-Equity Ratio.

### System & Security
-   **User Authentication & RBAC**: Full UI for managing users, roles, and granular permissions.
-   **Comprehensive Audit Trails**: Database triggers log all data changes. UI in the Settings tab provides a paginated and filterable view of both high-level actions and detailed field-level changes.

## Technology Stack
-   **Programming Language**: Python 3.9+ (up to 3.12)
-   **UI Framework**: PySide6 6.9.0+
-   **Database**: PostgreSQL 14+
-   **ORM**: SQLAlchemy 2.0+ (Asynchronous ORM)
-   **Async DB Driver**: `asyncpg`
-   **Data Validation (DTOs)**: Pydantic V2
-   **Password Hashing**: `bcrypt`
-   **Reporting Libraries**: `reportlab` (PDF), `openpyxl` (Excel)
-   **Dependency Management**: Poetry
-   **Date/Time Utilities**: `python-dateutil`
-   **Testing**: Pytest, pytest-asyncio, pytest-cov, unittest.mock

## Installation

This guide is for developers setting up the application from source.

### Prerequisites
-   Python 3.9 or higher
-   PostgreSQL Server 14 or higher (with admin/superuser access for initial setup)
-   Poetry (Python packaging and dependency management tool)
-   Git

### Developer Installation Steps
1.  **Clone Repository**: `git clone https://github.com/yourusername/sg_bookkeeper.git && cd sg_bookkeeper`
2.  **Install Dependencies**: `poetry install --with dev`
3.  **Configure `config.ini`**:
    *   The application looks for `config.ini` in a platform-specific user config directory:
        *   Linux: `~/.config/SGBookkeeper/config.ini`
        *   macOS: `~/Library/Application Support/SGBookkeeper/config.ini`
        *   Windows: `%APPDATA%\SGBookkeeper\config.ini`
    *   Create the `SGBookkeeper` directory if it doesn't exist.
    *   Create `config.ini` in that directory. Start with the following content, **providing your PostgreSQL superuser credentials** (like `postgres`) for the initial setup. This is needed for creating new company databases.
        ```ini
        [Database]
        username = YOUR_POSTGRES_ADMIN_USER
        password = YOUR_POSTGRES_ADMIN_PASSWORD
        host = localhost
        port = 5432
        database = sg_bookkeeper_default
        echo_sql = False
        pool_min_size = 2
        pool_max_size = 10
        pool_recycle_seconds = 3600

        [Application]
        theme = light
        language = en
        last_opened_company_id = 
        ```
4.  **Run the Application**:
    ```bash
    poetry run sg_bookkeeper
    ```
5.  **Create Your First Company**:
    *   On first run, the application may prompt you to create or select a company.
    *   Go to **File > New Company...** to launch the **New Company Setup Wizard**.
    *   Follow the on-screen steps to provide a Company Name and a valid Database Name.
    *   On successful creation, the application will restart to open your new company file.
    *   The default login is `admin` / `password`. You will be prompted to change this password on first login.

## Usage Guide
-   **Switching Companies**: Go to **File > Open Company...** to launch the `Company Manager` dialog. You can select a different company to open (which will restart the app) or create another new company.
-   **Period-End Procedures**: The "Period-End Procedures" tab under "Accounting" now contains the tool for running the **Unrealized Forex Gain/Loss Revaluation**.
-   **Other Modules**: Explore the tabs for `Dashboard`, `Sales`, `Purchases`, `Payments`, `Banking`, and `Reports` to manage all aspects of your business.
-   **Settings Tab**: Configure Company Information, manage Fiscal Years/Periods, Users (CRUD, password changes, role assignment), Roles & Permissions, and view Audit Logs.

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
The PostgreSQL database schema is at version **1.0.7**. It includes tables for core system functions, detailed accounting, business operations, and comprehensive audit trails. A key feature is the `cash_flow_category` column in the `accounting.accounts` table, which enables automated generation of the Statement of Cash Flows. Refer to `scripts/schema.sql` for full details.

## Testing
Automated tests are implemented using Pytest to ensure code quality and prevent regressions.
-   **Running Tests**:
    *   To run all tests: `poetry run pytest`
    *   To generate a coverage report: `poetry run pytest --cov=app`

## Contributing
Contributions are welcome! Please fork the repository, create a feature branch, make your changes, add relevant tests, and submit a pull request. Adherence to the existing architecture and coding standards is required.

## Roadmap

### Recently Completed
-   **New Company Wizard**: Replaced the simple dialog with a multi-step `QWizard` for a better user experience.
-   **Multi-Currency Accounting**: Implemented calculation and posting of realized forex gains/losses on payments.
-   **Withholding Tax (WHT) Management**: Implemented WHT application on vendor payments with correct JE creation.
-   **Unrealized Forex Revaluation**: Implemented the period-end procedure to revalue open foreign currency balances.

### Current Focus / Next Steps
-   **WHT Reporting**: Create UI and reports for managing and filing withheld taxes (e.g., generating Form S45).
-   **Advanced Reporting**: Enhance the reporting engine with more customization options and financial analytics.
-   **Automated Testing**: Significantly expand unit and integration test coverage for all new and existing features.
-   **User Experience Refinements**: Polish existing UIs based on usability feedback, particularly in the invoicing and payment modules.

### Long-term
-   Inventory Control enhancements (e.g., stocktakes, multiple locations, FIFO/LIFO costing methods).
-   Cloud synchronization options (optional data backup/sync to a user-provided cloud storage).
-   Enhanced Tax Compliance features (e.g., preparation of IRAS Audit File (IAF)).
-   Full UI test suite using a suitable framework (e.g., `pytest-qt`).

## License
This project is licensed under the MIT License.
