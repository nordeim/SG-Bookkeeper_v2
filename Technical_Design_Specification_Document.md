# Technical Design Specification Document: SG Bookkeeper (v18)

**Version:** 18.0
**Date:** 2025-06-12

## 1. Introduction

### 1.1 Purpose
This Technical Design Specification (TDS) document, version **18.0**, provides a detailed and up-to-date overview of the SG Bookkeeper application's technical design and implementation. It reflects the current state of the project, incorporating the latest architectural decisions, component structures, and functionalities up to database schema version **1.0.8**.

This document details the complete, refactored architecture and major new features:
*   **Decoupled Architecture**: A full architectural refactoring to a lazy-loading, service-locator pattern centered on `ApplicationCore`.
*   **Multi-Company Management**: A complete workflow for creating and managing multiple, isolated company databases via a user-friendly wizard.
*   **Multi-Currency Accounting**: Full implementation of foreign currency transaction handling, including the calculation and automated posting of both realized and unrealized foreign exchange gains and losses.
*   **Withholding Tax (WHT) Management**: A complete workflow for applying WHT on vendor payments, including automated liability tracking and data generation for tax forms.
*   **Statement of Cash Flows Reporting**: A new, comprehensive Statement of Cash Flows generated using the indirect method, supported by a new account-tagging system.

This document serves as the single source of truth for ongoing development, feature enhancement, testing, and maintenance, ensuring architectural integrity is preserved as the application evolves.

### 1.2 Scope
This TDS covers the following aspects of the SG Bookkeeper application:
-   System Architecture: The layered architecture, asynchronous processing model, and the new lazy-loading dependency management pattern.
-   Database Schema: Details and organization as defined in `scripts/schema.sql` (v1.0.8), including tables, views, custom functions, and triggers.
-   Key UI Implementation Patterns: `PySide6` interactions with the asynchronous backend, DTO usage, and the structure of key UI components.
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
As of version 18.0 (reflecting schema v1.0.8), the following key features are implemented:
*   **Core Architecture**: A fully refactored, decoupled architecture based on a lazy-loading service locator pattern in `ApplicationCore`.
*   **Core Accounting**: Chart of Accounts (CRUD UI), General Journal (CRUD UI, Posting, Reversal), Fiscal Year/Period Management.
*   **Tax Management**: GST F5 Return preparation with detailed Excel export, Withholding Tax application on payments and certificate data generation.
*   **Multi-Currency**: Full lifecycle support for foreign currency transactions, with automatic calculation of realized gains/losses. A period-end procedure for calculating unrealized gains/losses is also implemented.
*   **Business Operations**: Full CRUD and lifecycle management for Customers, Vendors, Products/Services, Sales & Purchase Invoicing, and Payments.
*   **Banking**: Bank Account Management (CRUD), Manual Transaction Entry, CSV Bank Statement Import with column mapping, and a full-featured Bank Reconciliation module.
*   **Reporting**: Standard financial statements (Balance Sheet, P&L, Trial Balance, General Ledger), a new Statement of Cash Flows, and a preliminary Income Tax Computation report. All are exportable to PDF and Excel.
*   **System Administration**: Multi-company management via a guided wizard, User and Role-Based Access Control (RBAC) management, and a comprehensive Audit Log viewer.
*   **Dashboard**: Interactive dashboard displaying key financial indicators and ratios.
*   **Database**: Schema is at v1.0.8, supporting all current features, including the `withholding_tax_certificates` table.

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
        D{ApplicationCore <br/> (Service Locator)}
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
    C -- "Accesses Services via" --> D;
    D -- "Provides Access To" --> E;
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
-   **`ApplicationCore` (`app/core/application_core.py`)**: The central nervous system of the application. **It acts as a service locator and dependency injection container**. It is instantiated once at startup and passed throughout the application. It initializes all low-level **Service** classes during its `startup` method. All high-level **Manager** classes are instantiated on-demand using a **lazy-loading `@property` pattern**. This provides a single, consistent point of access to shared resources (`app_core.customer_manager`) while improving startup performance and decoupling `ApplicationCore` from the managers' specific dependencies.
-   **`CompanyManager` (`app/core/company_manager.py`)**: Manages the central registry of company databases, which is stored in a `companies.json` file in the user's config directory. It handles adding, removing, and listing available companies. It is initialized early and does not depend on a specific company database connection.
-   **`DatabaseManager` (`app/core/database_manager.py`)**: Abstracts all direct interaction with PostgreSQL. It uses settings from `ConfigManager` to create a SQLAlchemy `async_engine` and an `async_sessionmaker`. Its primary feature is the `session()` async context manager, which provides a transactional `AsyncSession` to the service layer. It is also responsible for setting the `app.current_user_id` session variable used by database audit triggers.
-   **`SecurityManager` (`app/core/security_manager.py`)**: Handles user authentication (password hashing with `bcrypt` and verification) and authorization (Role-Based Access Control). It tracks the `current_user` for the session and provides a `has_permission` method for RBAC checks throughout the UI.
-   **`db_initializer.py` (`app/core/`)**: A crucial utility, callable from the UI, that programmatically creates a new company database, connects to it, and executes the `schema.sql` and `initial_data.sql` scripts to set it up from scratch.

#### 2.2.2 Asynchronous Task Management (`app/main.py`)
-   A dedicated Python `threading.Thread` (`_ASYNC_LOOP_THREAD`) runs a persistent `asyncio` event loop. This ensures that all database I/O and other long-running tasks do not block the main Qt GUI thread.
-   The `schedule_task_from_qt(coroutine)` utility function is the vital bridge that allows the Qt thread to safely schedule a coroutine to run on the `asyncio` thread. It uses `asyncio.run_coroutine_threadsafe` and returns a `Future` object.
-   UI updates resulting from these asynchronous operations are marshaled back to the Qt main thread using `QMetaObject.invokeMethod` or by connecting callbacks to the `Future` object's `done_callback`. This pattern is used extensively to maintain a responsive UI.

#### 2.2.3 Services (Data Access Layer - `app/services/`)
Services implement the repository pattern, abstracting direct ORM query logic. This is the only layer (besides `DatabaseManager`) that directly interacts with SQLAlchemy.
-   **`business_services.py`**: Contains services for all business-related entities, such as `CustomerService`, `SalesInvoiceService`, `PaymentService`, etc. The `PaymentService` has been enhanced with a `wht_applicable_only` filter and a `get_payment_with_vendor` method to support the WHT module.
-   **`accounting_services.py`, `account_service.py`, etc.**: Contain services for core accounting entities like `AccountService`, `JournalService`, `FiscalPeriodService`, `ExchangeRateService`.
-   **`tax_service.py`**: Contains the new `WHTCertificateService` alongside the existing `GSTReturnService` and `TaxCodeService`.

#### 2.2.4 Managers (Business Logic Layer)
Managers encapsulate business rules and orchestrate services. They now all follow a unified constructor pattern: `__init__(self, app_core: "ApplicationCore")`.
-   **`PaymentManager` (`app/business_logic/payment_manager.py`)**: Heavily refactored. Its `create_payment` method now contains complex logic to build a journal entry that correctly accounts for multi-currency settlements (realized gain/loss) and withholding tax liabilities, often in the same transaction.
-   **`ForexManager` (`app/accounting/forex_manager.py`)**: A new manager dedicated to period-end procedures. Its `create_unrealized_gain_loss_je` method orchestrates the revaluation of all open foreign currency AR, AP, and bank balances.
-   **`WithholdingTaxManager` (`app/tax/withholding_tax_manager.py`)**: A new manager responsible for the business logic related to WHT, including creating certificate records from payment data.
-   **Other Managers**: All other managers (`CustomerManager`, `SalesInvoiceManager`, `GSTManager`, etc.) have been refactored to use the new unified constructor, sourcing their dependencies directly from `app_core`.

#### 2.2.5 User Interface (Presentation Layer - `app/ui/`)
-   **`MainWindow` (`app/ui/main_window.py`)**: Updated to use the new `CompanyCreationWizard`. Its `_handle_new_company_request` method now launches the wizard and processes the results from its registered fields to create the new company database.
-   **`CompanyCreationWizard` (`app/ui/company/company_creation_wizard.py`)**: Replaces the old single dialog. Provides a guided, multi-step process with an intro, a details page with validation, and a final confirmation page.
-   **`AccountingWidget` (`app/ui/accounting/accounting_widget.py`)**: A new "Period-End Procedures" tab has been added, which hosts the UI for triggering the unrealized forex revaluation process.
-   **`ReportsWidget` (`app/ui/reports/reports_widget.py`)**: A new "Withholding Tax" tab has been added, hosting the new `WHTReportingWidget`.

### 2.3 Design Patterns
-   **Layered Architecture**: As described above.
-   **Model-View-Controller (MVC) / Model-View-Presenter (MVP)**: Guides the separation of UI (View), data (Model), and application logic (Controller/Presenter - Managers).
-   **Repository Pattern**: Implemented by Service classes in the Data Access Layer.
-   **Data Transfer Object (DTO)**: Pydantic models are used for structured data exchange between layers.
-   **Result Object Pattern**: A custom `Result` class is used to return operation outcomes from the business logic layer.
-   **Observer Pattern**: Qt's Signals and Slots mechanism is used for communication between UI components and handling asynchronous updates.
-   **Service Locator**: `ApplicationCore` acts as a central service locator, providing dependencies to components that require them.
-   **Lazy Initialization**: Used in `ApplicationCore` via `@property` decorators to instantiate managers on-demand.

## 3. Data Architecture (Schema v1.0.8)

### 3.1. Database Schema Overview
The schema is defined in `scripts/schema.sql` (v1.0.8) and organized into `core`, `accounting`, `business`, and `audit` schemas.
-   **`accounting.withholding_tax_certificates` table (New)**: A new table added to store generated WHT certificates, linked one-to-one with the source `business.payments` record.
-   **`business.vendors` table**: Contains `withholding_tax_applicable` and `withholding_tax_rate` columns to flag vendors for WHT.
-   **Triggers**:
    *   `update_timestamp_trigger_func`: Automatically updates `updated_at` on row updates.
    *   `log_data_change_trigger_func`: A powerful audit trigger that captures every `INSERT`, `UPDATE`, and `DELETE` on key tables, recording the user, the old/new data as JSONB, and a field-level breakdown of changes.
    *   `update_bank_account_balance_trigger_func`: Automatically maintains the `current_balance` on `bank_accounts`.
-   **Functions**:
    *   `core.get_next_sequence_value`: A transaction-safe function for generating formatted sequential document numbers.

### 3.2. Data Initialization (`initial_data.sql`)
The initial data script has been updated to support the new features:
-   **New Sequence**: Added `wht_certificate` to `core.sequences`.
-   **New System Accounts**: Inserts records into `accounting.accounts` for WHT Payable (`2130`), Realized/Unrealized Forex Gains (`7200`/`7201`), and Realized/Unrealized Forex Losses (`8200`/`8201`).
-   **New Configuration**: Inserts keys into `core.configuration` to link these system account codes to their functions.

### 3.3. Data Models & DTOs
-   **`WithholdingTaxCertificate` ORM Model (`app/models/accounting/`)**: New model added.
-   **`Payment` & `Vendor` ORM Models**: Updated with the necessary back-populating relationships for the new WHT certificate table.
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
3.  **Manager Logic (`PaymentManager` & `WithholdingTaxManager`)**:
    *   The `PaymentManager` receives a DTO indicating WHT should be applied. It calculates the amounts and creates a single, balanced JE:
        *   `Dr Accounts Payable: 1000.00` (Clears the full invoice liability)
        *   `Cr Bank Account: 850.00` (Reflects actual cash outflow)
        *   `Cr WHT Payable: 150.00` (Recognizes the liability to the tax authority)
    *   After the payment is successfully created and posted, the `WHTReportingWidget` UI can be used to trigger the `WithholdingTaxManager`, which then creates a persistent `WithholdingTaxCertificate` record linked to that payment.

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
    4.  Initialize the application with `poetry run sg_bookkeeper`. On first run, use the "New Company" wizard to create the first company database. The `db_initializer.py` script will be called by the application to execute `schema.sql` (v1.0.8) and `initial_data.sql`.
-   **Execution**: `poetry run sg_bookkeeper`.

## 6. Conclusion
The SG Bookkeeper application is built upon a modern, robust, and well-structured architecture. The clear separation of layers, the asynchronous core, the lazy-loading dependency management pattern, and the consistent use of best practices make the codebase highly maintainable and extensible. The database schema is intelligently designed with data integrity and auditing as primary concerns. This architecture provides a solid foundation for future development, ensuring that the system can grow in complexity while remaining stable and easy to manage.

---
https://drive.google.com/file/d/13EJupZYgSuYhHd-nCAJPAHItjd3yVe1d/view?usp=sharing, https://drive.google.com/file/d/142Ul30zVomOXQHHZUXKIBriGf-4iskTr/view?usp=sharing, https://drive.google.com/file/d/18Z0ecA7eHWs5KQHIRp_e5Cx0bR5w17Hx/view?usp=sharing, https://drive.google.com/file/d/195-mFnZMB0mKKfPyPnqHG9ZuqeUxAMPi/view?usp=sharing, https://drive.google.com/file/d/1BF_WA-KObkI2YM4URjZNBbZmhY6R4hit/view?usp=sharing, https://drive.google.com/file/d/1RKlmfQy8FXvSbpe-e3kUptq_0J3JQQ95/view?usp=sharing, https://drive.google.com/file/d/1Tvzo3L_IWMP0x2wXfdUn3dlYkUtDJGOk/view?usp=sharing, https://drive.google.com/file/d/1X7x9jE-UbMPsSu-O9VySdtuXe2hmqvH2/view?usp=sharing, https://drive.google.com/file/d/1agA6VeYLn9QE-23X9Pm6V1dmS1S8N73h/view?usp=sharing, https://drive.google.com/file/d/1edgN1gfJM_wzBYck3O0bJA6h1LX9GPfb/view?usp=sharing, https://drive.google.com/file/d/1nbk8mJuNOo8KdzZkSK7bdHUqlFHvy6Mo/view?usp=sharing, https://drive.google.com/file/d/1olI_wf49v-tjth1Lj1O9kS16btfgxuxp/view?usp=sharing, https://drive.google.com/file/d/1rjwIcHEXP3KK-2ed9YDutoQ2TwpsUXWF/view?usp=sharing, https://drive.google.com/file/d/1ysMjG4SD27aPDAW8GzlKlc154pkNmStf/view?usp=sharing, https://aistudio.google.com/app/prompts?state=%7B%22ids%22:%5B%221zy43aW8S1WKru7zgPsmPuT_80lFMbPbj%22%5D,%22action%22:%22open%22,%22userId%22:%22103961307342447084491%22,%22resourceKeys%22:%7B%7D%7D&usp=sharing

