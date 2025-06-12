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

This document serves as a comprehensive guide for ongoing development, feature enhancement, testing, and maintenance, ensuring architectural integrity is preserved as the application evolves.

### 1.2 Scope
This TDS covers the following aspects of the SG Bookkeeper application:
-   System Architecture: The layered architecture, asynchronous processing model, and core design patterns.
-   Database Schema: Details and organization as defined in `scripts/schema.sql` (v1.0.7), including tables, views, custom functions, and triggers.
-   Key UI Implementation Patterns: `PySide6` interactions with the asynchronous backend, DTO usage, and the structure of key UI components like `MainWindow`, module widgets, and dialogs.
-   Core Business Logic: Component structures and interactions for all implemented modules, with a deep dive into the new `ForexManager` and the enhanced `PaymentManager`.
-   Data Models (SQLAlchemy ORM) and Data Transfer Objects (Pydantic DTOs).
-   Security Implementation: Authentication, Role-Based Access Control (RBAC), and comprehensive audit mechanisms.
-   Deployment and Initialization procedures.

### 1.3 Intended Audience
-   **Software Developers**: For implementation, feature development, and understanding system design.
-   **QA Engineers**: For comprehending system behavior, designing effective test cases, and validation.
-   **System Administrators**: For deployment strategies, database setup, and maintenance.
-   **Technical Project Managers**: For project oversight, planning, and resource allocation.

### 1.4 System Overview
SG Bookkeeper is a cross-platform desktop application engineered with Python, utilizing PySide6 for its GUI and PostgreSQL for robust data storage. It is designed to provide comprehensive accounting solutions for Singaporean Small to Medium-sized Businesses (SMBs). Key features include a full double-entry bookkeeping system, Singapore-specific GST management, interactive financial reporting, modules for managing essential business operations (Customers, Vendors, Invoicing, Payments), and a full bank reconciliation module.

The system is built on a multi-company architecture, where each company's data is securely isolated in its own dedicated PostgreSQL database. It natively handles multi-currency transactions, automatically calculating both realized and unrealized foreign exchange gains and losses. It also integrates Singapore-specific Withholding Tax (WHT) management directly into the payment workflow. The focus on user experience is evident in its interactive dashboard, a wizard-based company setup, and visual reconciliation aids. The application emphasizes data integrity, compliance with local accounting standards, user-friendliness, and robust auditability through a comprehensive, trigger-based audit logging system.

### 1.5 Current Implementation Status
As of version 17.0 (reflecting schema v1.0.7), the following key features are implemented:
*   **Core Accounting**: Chart of Accounts (CRUD UI), General Journal (CRUD UI, Posting, Reversal), Fiscal Year/Period Management.
*   **Tax Management**: GST F5 Return preparation with detailed Excel export, Withholding Tax application on payments.
*   **Multi-Currency**: Full lifecycle support for foreign currency invoices and payments, with automatic calculation of realized gains/losses. A period-end procedure for calculating unrealized gains/losses is also implemented.
*   **Business Operations**: Full CRUD and lifecycle management for Customers, Vendors, Products/Services, Sales & Purchase Invoicing, and Payments.
*   **Banking**: Bank Account Management (CRUD), Manual Transaction Entry, CSV Bank Statement Import with column mapping, and a full-featured Bank Reconciliation module with draft persistence and visual matching.
*   **Reporting**: Standard financial statements (Balance Sheet, P&L, Trial Balance, General Ledger), a new Statement of Cash Flows, and a preliminary Income Tax Computation report. All are exportable to PDF and Excel.
*   **System Administration**: Multi-company management via a guided wizard, User and Role-Based Access Control (RBAC) management, and a comprehensive Audit Log viewer.
*   **Dashboard**: Interactive dashboard displaying key financial indicators and ratios.
*   **Database**: Schema is at v1.0.7, supporting all current features, including the `cash_flow_category` column for the Cash Flow Statement.

## 2. System Architecture

### 2.1 High-Level Architecture
The application follows a layered architecture to promote separation of concerns, testability, and maintainability. This structure ensures that changes in one layer have a minimal and well-defined impact on others.

```mermaid
graph TD
    subgraph "Presentation Layer (app/ui)"
        A[UI Widgets & Dialogs <br/> e.g., SalesInvoicesWidget]
        B[Qt Models <br/> e.g., SalesInvoiceTableModel]
    end

    subgraph "Business Logic Layer"
        C[Managers <br/> e.g., SalesInvoiceManager, ForexManager]
    end
    
    subgraph "Central Orchestrator"
        D{ApplicationCore}
    end

    subgraph "Data Access Layer (app/services)"
        E[Services (Repositories) <br/> e.g., SalesInvoiceService, AccountService]
    end

    subgraph "Data Persistence Layer"
        F[Database Manager <br/> (SQLAlchemy Core/ORM)]
        G[(PostgreSQL Database <br/> with Schemas & Triggers)]
    end

    subgraph "Supporting Components"
        H[Utilities <br/> (DTOs, Result Class, Helpers)]
        I[AsyncIO Event Loop <br/> (Background Thread)]
    end

    A -- "User Interaction, DTOs" --> C;
    A -- "Displays Data From" --> B;
    C -- "Updates UI Model With" --> B;
    C -- "Calls Methods On" --> E;
    D -- "Provides Access To Managers & Services" --> C;
    A -- "Accesses Managers via" --> D;
    E -- "Uses" --> F;
    F -- "Manages Connections To" --> G;
    C -- "Uses" --> H;
    A -- "Schedules Async Task via Bridge" --> I;
    I -- "Runs DB Operations via" --> F;
    I -- "Returns Result To UI via Callback/Signal" --> A;
```

### 2.2 Component Architecture

#### 2.2.1 Core Components (`app/core/`)
-   **`Application` (`app/main.py`)**: The main entry point. It subclasses `QApplication` and is responsible for setting up the fundamental asynchronous architecture. It starts the `asyncio` event loop in a dedicated background thread and provides the `schedule_task_from_qt` bridge function for safe cross-thread communication. It manages the application's lifecycle, including the initialization sequence with a splash screen and a graceful shutdown procedure.
-   **`ApplicationCore` (`app/core/application_core.py`)**: The central nervous system of the application, acting as a service locator and dependency injection container. It is instantiated once at startup and passed throughout the application. It initializes all service and manager classes, making them available as properties (e.g., `app_core.customer_manager`, `app_core.forex_manager`). This provides a single, consistent point of access to shared resources and business logic, greatly simplifying dependency management. A `minimal_init` flag allows it to be created without a database connection, enabling the UI to prompt for company selection on first run.
-   **`CompanyManager` (`app/core/company_manager.py`)**: Manages the central registry of company databases, which is stored in a `companies.json` file in the user's config directory. It handles adding, removing, and listing available companies. It is initialized early and does not depend on a specific company database connection.
-   **`DatabaseManager` (`app/core/database_manager.py`)**: Abstracts all direct interaction with PostgreSQL. It uses settings from `ConfigManager` to create a SQLAlchemy `async_engine` and an `async_sessionmaker`. Its primary feature is the `session()` async context manager, which provides a transactional `AsyncSession` to the service layer. It is also responsible for setting the `app.current_user_id` session variable used by database audit triggers.
-   **`SecurityManager` (`app/core/security_manager.py`)**: Handles user authentication (password hashing with `bcrypt` and verification) and authorization (Role-Based Access Control). It tracks the `current_user` for the session and provides a `has_permission` method for RBAC checks throughout the UI.
-   **`DBInitializer` (`app/core/db_initializer.py`)**: A crucial utility, callable from the UI, that programmatically creates a new company database, connects to it, and executes the `schema.sql` and `initial_data.sql` scripts to set it up from scratch.

#### 2.2.2 Asynchronous Task Management (`app/main.py`)
-   A dedicated Python `threading.Thread` (`_ASYNC_LOOP_THREAD`) runs a persistent `asyncio` event loop. This ensures that all database I/O and other long-running tasks do not block the main Qt GUI thread.
-   The `schedule_task_from_qt(coroutine)` utility function is the vital bridge that allows the Qt thread to safely schedule a coroutine to run on the `asyncio` thread. It uses `asyncio.run_coroutine_threadsafe` and returns a `Future` object.
-   UI updates resulting from these asynchronous operations are marshaled back to the Qt main thread using `QMetaObject.invokeMethod` or by connecting callbacks to the `Future` object's `done_callback`. This pattern is used extensively to maintain a responsive UI.

#### 2.2.3 Services (Data Access Layer - `app/services/`)
Services implement the repository pattern, abstracting direct ORM query logic. This is the only layer (besides `DatabaseManager`) that directly interacts with SQLAlchemy.
-   **`business_services.py`**: Contains services for all business-related entities, such as `CustomerService`, `SalesInvoiceService`, `PaymentService`, etc. The `get_all_summary` methods have been updated to accept a `status_list` for more flexible filtering. New methods like `get_all_open_invoices` have been added to support the `ForexManager`.
-   **`accounting_services.py`, `account_service.py`, etc.**: Contain services for core accounting entities like `AccountService`, `JournalService`, `FiscalPeriodService`, `ExchangeRateService`.
-   **`core_services.py`**: Contains services for system-level entities like `SequenceService` and `CompanySettingsService`. The `SequenceService` now encapsulates all interactions with the database sequence function.

#### 2.2.4 Managers (Business Logic Layer)
Managers encapsulate business rules and orchestrate services.
-   **`PaymentManager` (`app/business_logic/payment_manager.py`)**: Heavily refactored. Its `create_payment` method now contains complex logic to build a journal entry that correctly accounts for multi-currency settlements (realized gain/loss) and withholding tax liabilities, often in the same transaction.
-   **`ForexManager` (`app/accounting/forex_manager.py`) (New)**: A new manager dedicated to period-end procedures. Its `create_unrealized_gain_loss_je` method orchestrates the revaluation of all open foreign currency AR, AP, and bank balances.
-   **`FinancialStatementGenerator` & `GSTManager`**: Their `__init__` methods have been refactored to accept only `app_core`, from which they derive their service dependencies. This simplifies instantiation in `ApplicationCore`.

#### 2.2.5 User Interface (Presentation Layer - `app/ui/`)
-   **`MainWindow` (`app/ui/main_window.py`)**: Updated to use the new `CompanyCreationWizard`. Its `_handle_new_company_request` method now launches the wizard and processes the results from its registered fields to create the new company database.
-   **`CompanyCreationWizard` (`app/ui/company/company_creation_wizard.py`) (New)**: Replaces the old single dialog. Provides a guided, multi-step process with an intro, a details page with validation, and a final confirmation page.
-   **`AccountingWidget` (`app/ui/accounting/accounting_widget.py`)**: A new "Period-End Procedures" tab has been added, which hosts the UI for triggering the unrealized forex revaluation process.

### 2.3 Design Patterns
-   **Layered Architecture**: As described above.
-   **Model-View-Controller (MVC) / Model-View-Presenter (MVP)**: Guides the separation of UI (View), data (Model), and application logic (Controller/Presenter - Managers).
-   **Repository Pattern**: Implemented by Service classes in the Data Access Layer.
-   **Data Transfer Object (DTO)**: Pydantic models are used for structured data exchange between layers.
-   **Result Object Pattern**: A custom `Result` class is used to return operation outcomes from the business logic layer.
-   **Observer Pattern**: Qt's Signals and Slots mechanism is used for communication between UI components and handling asynchronous updates.
-   **Dependency Injection (via Service Locator)**: `ApplicationCore` acts as a central service locator, providing dependencies to components that require them.
-   **Facade Pattern**: The new `reverse_journal_entry` method in `JournalEntryManager` acts as a simple facade over the more descriptively named `create_reversing_entry` method, providing a stable public API.

## 3. Data Architecture (Schema v1.0.7)

### 3.1. Database Schema Overview
The schema is defined in `scripts/schema.sql` (v1.0.7) and organized into `core`, `accounting`, `business`, and `audit` schemas.
-   **`accounting.accounts` table**:
    *   A new `cash_flow_category VARCHAR(20)` column has been added. It is nullable and has a `CHECK` constraint for 'Operating', 'Investing', or 'Financing'. This field is the foundation for the automated Statement of Cash Flows.
-   **Triggers**:
    *   `update_timestamp_trigger_func`: Automatically updates `updated_at` on row updates.
    *   `log_data_change_trigger_func`: A powerful audit trigger that captures every `INSERT`, `UPDATE`, and `DELETE` on key tables, recording the user, the old/new data as JSONB, and a field-level breakdown of changes.
    *   `update_bank_account_balance_trigger_func`: Automatically maintains the `current_balance` on `bank_accounts`.
-   **Functions**:
    *   `core.get_next_sequence_value`: A transaction-safe function for generating formatted sequential document numbers.

### 3.2. Data Initialization (`initial_data.sql`)
The initial data script has been updated to support the new features:
-   **New System Accounts**: Inserts records into `accounting.accounts` for:
    *   `2130 - Withholding Tax Payable`
    *   `7200 - Foreign Exchange Gain` (Realized)
    *   `8200 - Foreign Exchange Loss` (Realized)
    *   `7201 - Unrealized Forex Gain (P&L)`
    *   `8201 - Unrealized Forex Loss (P&L)`
-   **New Configuration**: Inserts keys into `core.configuration` to link these system account codes to their functions (e.g., `SysAcc_WHTPayable`, `SysAcc_UnrealizedForexGain`).

### 3.3. Data Models & DTOs
-   **`Account` ORM Model (`app/models/accounting/account.py`)**: Updated to include the `cash_flow_category` attribute.
-   **`AccountCreateData` / `AccountUpdateData` DTOs**: Updated to include the optional `cash_flow_category` field.
-   **`PaymentCreateData` DTO**: Extended with `apply_withholding_tax: bool` and `withholding_tax_amount: Optional[Decimal]` to transport WHT information from the UI.

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

## 5. Deployment and Installation
-   **Prerequisites**: Python 3.9+, PostgreSQL 14+, Poetry.
-   **Setup**:
    1.  Clone repository.
    2.  Install dependencies: `poetry install`.
    3.  Configure database admin connection in a platform-specific `config.ini`.
    4.  Initialize the application with `poetry run sg_bookkeeper`. On first run, use the "New Company" wizard to create the first company database. The `db_init.py` script will be called by the application to execute `schema.sql` (v1.0.7) and `initial_data.sql`.
-   **Execution**: `poetry run sg_bookkeeper`.

## 6. Conclusion
Version 17.0 of SG Bookkeeper introduces significant enhancements to its accounting capabilities, moving it closer to a professional-grade financial management tool. The implementation of full multi-currency transaction handling, integrated WHT management, an automated Statement of Cash Flows, and an improved company creation wizard provides immense value. These features are built upon a stable, layered, and multi-company architecture, ensuring that complexity is managed effectively and the system remains robust and maintainable.

---
https://drive.google.com/file/d/11X3f2mKRWl56NubmyAKo5dwck7p2JaLs/view?usp=sharing, https://drive.google.com/file/d/127qgzFTDe-WAnzFzOzBn2efixfG9w9YE/view?usp=sharing, https://drive.google.com/file/d/131RjCRl_kHc0XtnhCzDmf5bjgJX5iEww/view?usp=sharing, https://drive.google.com/file/d/13B_HcJmxgi3QGYHnj64s275QZN20pg3g/view?usp=sharing, https://drive.google.com/file/d/19n5zeGWlBAwCRFAXfbe4kY5xBK-uV-d7/view?usp=sharing, https://drive.google.com/file/d/1M5ybbmzIqj7IUo99Yle7xl_pkczow6Ci/view?usp=sharing, https://drive.google.com/file/d/1P4rxLCG8-5cJ2_vt2qKJqO2wxN26ro9T/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221Rh0wsFMlVjsOSccPUo5JJmfB6gof_tS2%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing, https://drive.google.com/file/d/1T1kVeTCKFOIzPckOmAarcwHC8x0yau1i/view?usp=sharing, https://drive.google.com/file/d/1dAgihzWoQ03fPAECRX4qUzJiiJppPgwz/view?usp=sharing, https://drive.google.com/file/d/1gM89F4jZMNsWNTd9bxJxPfRxY0Y2Vfof/view?usp=sharing, https://drive.google.com/file/d/1hAf_3y-ecY6gAU67N0KzgqGZz1XrDjed/view?usp=sharing, https://drive.google.com/file/d/1iLEa4z_1QZHLh5VEurZg7rUHZneQzsY8/view?usp=sharing, https://drive.google.com/file/d/1mO8_5fwtxIboAdjNo31vNNnNYbzI8-gq/view?usp=sharing, https://drive.google.com/file/d/1tbuyHau6G4TdCZ0v6u22_ePISFTSNU7r/view?usp=sharing, https://drive.google.com/file/d/1uC_hd3fJooXn4tQQsLJPU3mxW07hDGym/view?usp=sharing

