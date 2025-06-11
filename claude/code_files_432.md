Of course. Based on a deep and systematic analysis of the entire codebase, including all recent feature additions and architectural refinements, I will now generate the complete, updated project documentation.

These documents accurately reflect the current state of the SG Bookkeeper application, its architecture, and its capabilities as of schema version 1.0.7.

***

### **Complete Updated File: `README.md`**

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
```

***

### **Complete Updated File: `Technical_Design_Specification_Document.md`**

```markdown
# Technical Design Specification Document: SG Bookkeeper (v17)

**Version:** 17.0
**Date:** 2025-06-11

## 1. Introduction

### 1.1 Purpose
This Technical Design Specification (TDS) document, version **17.0**, provides a detailed and up-to-date overview of the SG Bookkeeper application's technical design and implementation. It reflects the current state of the project, incorporating architectural decisions, component structures, and functionalities up to schema version **1.0.7**.

This version specifically details major new features and enhancements:
*   **Multi-Currency Accounting**: Full implementation of foreign currency transaction handling, including the calculation and automated posting of realized foreign exchange gains and losses at the time of payment.
*   **Withholding Tax (WHT) Management**: A complete workflow for applying WHT on vendor payments, including automated liability tracking through the journal.
*   **Unrealized Forex Revaluation**: A period-end procedure to calculate and post reversing journal entries for unrealized gains/losses on open foreign currency balances.
*   **Cash Flow Statement Reporting**: A new, comprehensive Statement of Cash Flows generated using the indirect method, supported by a new account-tagging system.
*   **Enhanced User Experience**: Introduction of a `QWizard` for a more intuitive "New Company" creation process.

### 1.2 Scope
This TDS covers the following aspects of the SG Bookkeeper application:
-   **System Architecture**: The layered architecture and its support for advanced accounting workflows like multi-currency and WHT.
-   **Database Schema**: Details and organization as defined in `scripts/schema.sql` (v1.0.7), including the `cash_flow_category` field and new system accounts.
-   **Key UI Implementation Patterns**: Changes to the `PaymentDialog`, `AccountDialog`, `AccountingWidget`, and the new `CompanyCreationWizard`.
-   **Core Business Logic**: Detailed explanation of the logic within `PaymentManager`, the new `ForexManager`, and the `FinancialStatementGenerator`.
-   **Data Models & DTOs**: Structure and purpose of updated ORM models and Pydantic DTOs.
-   **Security & Data Isolation**: How the application ensures data separation between companies.

### 1.3 Intended Audience
-   **Software Developers**: For implementation, feature development, and understanding system design.
-   **QA Engineers**: For comprehending system behavior, designing effective test cases, and validation.
-   **System Administrators**: For deployment strategies, database setup, and maintenance.
-   **Technical Project Managers**: For project oversight, planning, and resource allocation.

### 1.4 System Overview
SG Bookkeeper is a cross-platform desktop application engineered with Python, utilizing PySide6 for its GUI and PostgreSQL for robust data storage. Its multi-company architecture allows users to manage multiple businesses, each with its data securely isolated in a dedicated database.

The application provides a full double-entry accounting core, Singapore-specific GST and Withholding Tax management, and a suite of interactive financial reports, including a Statement of Cash Flows. Core business operations are fully supported with multi-currency capabilities, including the automatic calculation of realized and unrealized foreign exchange gains and losses.

### 1.5 Current Implementation Status
As of version 17.0 (reflecting schema v1.0.7):
*   **Multi-Currency Support**: Fully implemented. The system correctly calculates and posts realized forex gains/losses on payments and has a period-end procedure for unrealized gains/losses.
*   **Withholding Tax Management**: Fully implemented. The `PaymentDialog` supports applying WHT for applicable vendors, automatically creating the correct JE to record the liability.
*   **Cash Flow Statement**: Implemented. A new report generates a Statement of Cash Flows using the indirect method, based on the `cash_flow_category` account tag.
*   **Company Creation Wizard**: The user experience for creating new companies has been enhanced with a multi-step wizard.
*   **Database**: Schema is at v1.0.7, supporting all current features.
*   All previously documented features (multi-company, bank reconciliation, dashboard, etc.) are stable and integrated with these new capabilities.

## 2. System Architecture

### 2.1 High-Level Architecture
The application maintains its robust layered architecture, now enhanced to support more complex financial transactions.

```mermaid
graph TD
    subgraph UI Layer
        A[Presentation (app/ui)]
    end
    
    subgraph Logic Layer
        B[Business Logic (Managers)]
    end

    subgraph Data Layer
        C[Services / DAL (app/services)]
        E[Database (PostgreSQL)]
    end

    subgraph Core
        F[Application Core (app/core)]
        D[Database Manager (app/core)]
        G[Utilities & Common (app/utils, app/common)]
    end

    A -->|User Actions & DTOs| B;
    B -->|Service Calls| C;
    C -->|SQLAlchemy & asyncpg| D;
    D <--> E;

    B -->|Accesses shared services via| F;
    A -->|Schedules tasks via| F;
    C -->|Uses DB sessions from| F;
    B -->|Uses| G;
    A -->|Uses| G;
```

### 2.2 Component Architecture (Updates for New Features)

#### 2.2.1 Core Components (`app/core/`)
*   **`ApplicationCore`**: Refactored to simplify manager instantiation. It now passes itself (`self`) to managers, which then pull their specific service dependencies from the core instance. This improves modularity and cleans up the startup sequence. It also now includes the instantiation of the new `ForexManager`.

#### 2.2.2 Managers (Business Logic Layer)
*   **`PaymentManager` (`app/business_logic/payment_manager.py`)**: Its `create_payment` method is now a sophisticated transaction processor that correctly handles foreign currency payments, calculating and posting realized forex gain/loss, and vendor payments with withholding tax deductions.
*   **`ForexManager` (`app/accounting/forex_manager.py`) (New)**: A new manager dedicated to period-end procedures. Its `create_unrealized_gain_loss_je` method orchestrates the complex task of revaluing all open foreign currency AR, AP, and bank balances, and posting the necessary adjustment and reversal journal entries.
*   **`FinancialStatementGenerator`**: Its `__init__` method has been refactored to accept only `app_core`, from which it derives its service dependencies.
*   **`GSTManager`**: Its `__init__` method has been refactored similarly to `FinancialStatementGenerator`, and its dependency on the old `SequenceGenerator` has been replaced with the more direct `SequenceService`.

#### 2.2.3 User Interface (Presentation Layer - `app/ui/`)
*   **`CompanyCreationWizard` (`app/ui/company/company_creation_wizard.py`) (New)**: A new multi-page `QWizard` that replaces the old single dialog for creating a company, providing a more guided and robust user experience.
*   **`MainWindow` (`app/ui/main_window.py`)**: Updated to launch the new `CompanyCreationWizard` instead of the old dialog.
*   **`AccountingWidget` (`app/ui/accounting/accounting_widget.py`)**: A new "Period-End Procedures" tab has been added to host the UI for triggering the unrealized forex revaluation process.

## 3. Data Architecture

### 3.1. Database Schema (v1.0.7)
*   The master schema is now at version **1.0.7**.
*   **`accounting.accounts` table**: A new nullable column, `cash_flow_category VARCHAR(20)`, has been added with a `CHECK` constraint for 'Operating', 'Investing', or 'Financing'. This is the key change enabling the automated Statement of Cash Flows.
*   **`initial_data.sql`**: The script has been updated to add new system accounts required by the new features:
    *   `2130 - Withholding Tax Payable`
    *   `7200 - Foreign Exchange Gain`
    *   `8200 - Foreign Exchange Loss`
    *   `7201 - Unrealized Forex Gain (P&L)`
    *   `8201 - Unrealized Forex Loss (P&L)`
    The `core.configuration` table is also updated to reference these new accounts.

## 4. Detailed Feature Implementation

### 4.1. Unrealized Forex Gain/Loss Workflow
1.  **User Action**: The user navigates to the "Period-End Procedures" tab in the Accounting module and clicks "Run Forex Revaluation...".
2.  **UI Prompt**: A dialog appears, asking for the `revaluation_date`.
3.  **Manager Orchestration (`ForexManager`)**:
    *   Fetches all open foreign currency sales invoices, purchase invoices, and bank accounts.
    *   For each item, it calculates the difference between its currently booked value in the base currency and its new value when revalued at the exchange rate for the `revaluation_date`.
    *   These adjustments are aggregated by their respective GL control accounts (AR, AP, Bank GLs).
4.  **Journal Entry Creation**:
    *   If the net adjustment is material, a single journal entry is created.
    *   It includes debit/credit lines for each affected control account to bring its balance to the revalued amount.
    *   A final balancing line is created, debiting `Unrealized Forex Loss` or crediting `Unrealized Forex Gain`.
5.  **Posting and Reversal**:
    *   The main adjustment journal entry is created and posted as of the `revaluation_date`.
    *   A second, perfect reversal of this entry is immediately created and posted for the following day (`revaluation_date + 1 day`). This ensures the unrealized adjustment does not permanently affect the books and is only reflected in the financial statements for the period ending on the revaluation date.

### 4.2. Withholding Tax Workflow
1.  **Setup**: A vendor is marked as `withholding_tax_applicable` with a rate (e.g., 15%).
2.  **Payment Creation (`PaymentDialog`)**: A user creates a payment for a $1,000 invoice from this vendor. The UI shows an "Apply Withholding Tax" option. When checked, it displays the calculated WHT amount ($150) and the net payment ($850).
3.  **Manager Logic (`PaymentManager`)**: The manager receives a DTO indicating WHT should be applied. It calculates the amounts and creates a single, balanced JE:
    *   `Dr Accounts Payable: 1000.00` (Clears the full invoice liability)
    *   `Cr Bank Account: 850.00` (Reflects actual cash outflow)
    *   `Cr WHT Payable: 150.00` (Recognizes the liability to the tax authority)

### 4.3. Cash Flow Statement Generation
1.  **User Setup (`AccountDialog`)**: The user tags balance sheet accounts with a `cash_flow_category` ('Operating', 'Investing', 'Financing').
2.  **Report Generation (`FinancialStatementGenerator`)**:
    *   **Start with Net Income**: Fetches the net profit for the period from the P&L.
    *   **Adjust for Non-Cash Items**: Adds back depreciation expense.
    *   **Adjust for Working Capital**: For each account tagged as `Operating`, it calculates the change in its balance. An increase in an operating asset (like AR) is a *use* of cash (subtracted), while an increase in an operating liability (like AP) is a *source* of cash (added).
    *   **Calculate CFI & CFF**: It calculates the change in balance for all accounts tagged as `Investing` or `Financing` and lists these changes directly in their respective sections.
    *   **Reconcile**: The net change in cash is calculated and reconciled against the actual change in the cash/bank account balances to ensure accuracy.

## 5. Conclusion
Version 17.0 of SG Bookkeeper introduces significant enhancements to its accounting capabilities, moving it closer to a professional-grade financial management tool. The implementation of full multi-currency transaction handling, integrated WHT management, and an automated Statement of Cash Flows provides immense value for businesses operating in a global and regulated environment like Singapore. These features are built upon a stable, layered, and multi-company architecture, ensuring that complexity is managed effectively and the system remains robust and maintainable.
```
---
https://drive.google.com/file/d/11X3f2mKRWl56NubmyAKo5dwck7p2JaLs/view?usp=sharing, https://drive.google.com/file/d/127qgzFTDe-WAnzFzOzBn2efixfG9w9YE/view?usp=sharing, https://drive.google.com/file/d/131RjCRl_kHc0XtnhCzDmf5bjgJX5iEww/view?usp=sharing, https://drive.google.com/file/d/13B_HcJmxgi3QGYHnj64s275QZN20pg3g/view?usp=sharing, https://drive.google.com/file/d/19n5zeGWlBAwCRFAXfbe4kY5xBK-uV-d7/view?usp=sharing, https://drive.google.com/file/d/1M5ybbmzIqj7IUo99Yle7xl_pkczow6Ci/view?usp=sharing, https://drive.google.com/file/d/1P4rxLCG8-5cJ2_vt2qKJqO2wxN26ro9T/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221Rh0wsFMlVjsOSccPUo5JJmfB6gof_tS2%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing, https://drive.google.com/file/d/1T1kVeTCKFOIzPckOmAarcwHC8x0yau1i/view?usp=sharing, https://drive.google.com/file/d/1dAgihzWoQ03fPAECRX4qUzJiiJppPgwz/view?usp=sharing, https://drive.google.com/file/d/1gM89F4jZMNsWNTd9bxJxPfRxY0Y2Vfof/view?usp=sharing, https://drive.google.com/file/d/1hAf_3y-ecY6gAU67N0KzgqGZz1XrDjed/view?usp=sharing, https://drive.google.com/file/d/1iLEa4z_1QZHLh5VEurZg7rUHZneQzsY8/view?usp=sharing, https://drive.google.com/file/d/1mO8_5fwtxIboAdjNo31vNNnNYbzI8-gq/view?usp=sharing, https://drive.google.com/file/d/1uC_hd3fJooXn4tQQsLJPU3mxW07hDGym/view?usp=sharing

