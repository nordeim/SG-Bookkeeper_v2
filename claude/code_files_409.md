<think>
The user has confirmed the previous fix was successful by providing a clean run log and screenshots of the new company management dialogs. They are now asking me to proceed with the "next step" in my plan.

From my previous internal plan, I have completed the following:
1.  **Multi-Company Architecture**: Implemented and fixed.
2.  **Unrealized Forex Gain/Loss**: Planned.
3.  **WHT Reporting**: Planned.
4.  **Cash Flow Statement**: Implemented.
5.  ...and other features from the turn before that.

The next logical features to tackle from the roadmap are indeed the **Unrealized Forex Gain/Loss** calculation and the **WHT Reporting** functionality. These are distinct features. I will implement them one at a time to maintain focus and reduce the risk of complex, interacting bugs.

I will start with the **Unrealized Forex Gain/Loss** feature first, as it's a core accounting function that impacts period-end reporting. WHT reporting is a compliance feature that can be built on top of the already-implemented WHT logic.

---
### **Part 1: Unrealized Forex Gain/Loss - Deep Dive & Refined Plan**

#### **1.1. Goal & Requirements Analysis (Re-evaluation)**

**Goal:** Create a robust, user-initiated process to revalue open foreign currency monetary assets and liabilities at a specific date (e.g., month-end). This process must generate a reversing journal entry to record the resulting unrealized gains or losses.

**Refined Requirements:**
1.  **UI Trigger**: A new "Period-End Procedures" group box in the `AccountingWidget` will contain a "Run Forex Revaluation..." button.
2.  **User Input**: The UI will prompt the user for a single "Revaluation Date".
3.  **Manager Logic (`ForexManager`)**: A new `ForexManager` class will encapsulate the complex calculation and JE creation logic.
4.  **Scope of Revaluation**: The process must cover:
    *   Open foreign currency Sales Invoices (Accounts Receivable).
    *   Open foreign currency Purchase Invoices (Accounts Payable).
    *   Foreign currency Bank Account balances.
5.  **Calculation Method**:
    *   The manager will iterate through each open invoice and foreign currency bank account.
    *   For invoices, it will calculate the difference between the base currency value of the outstanding foreign amount at the *original invoice exchange rate* and the base currency value at the *new revaluation exchange rate*.
    *   For bank accounts, it will compare the current base currency GL balance with the revalued foreign currency balance.
    *   The net sum of all these adjustments will determine the total unrealized gain or loss.
6.  **Journal Entry Creation**:
    *   A single, consolidated journal entry will be created as of the `revaluation_date`.
    *   This JE will contain individual lines debiting/crediting each AR/AP control account and bank account GL to adjust their base currency value.
    *   A final line will post the net difference to the "Unrealized Foreign Exchange Gain/Loss" account.
    *   Crucially, a **reversing journal entry** must be created and posted for the *next day* (`revaluation_date + 1 day`). This nullifies the unrealized adjustment at the start of the new period, ensuring that the *realized* gain/loss calculated upon final payment will be correct.
7.  **System Accounts**: The system needs GL accounts for "Unrealized Forex Gain" and "Unrealized Forex Loss". I will use the P&L for these. The existing `initial_data.sql` and chart of accounts already have placeholders for `7200` and `8200`, which I previously designated for realized gains/losses. To distinguish, I will add new accounts:
    *   `7201 - Unrealized Forex Gain (P&L)`
    *   `8201 - Unrealized Forex Loss (P&L)`
    This provides better reporting granularity.

#### **1.2. Implementation Options (Re-evaluation)**

My previous analysis concluded that a "Cash Flow Tagging" style approach (Option B) for the Cash Flow Statement was correct. For Unrealized Forex, the "Automated JE Generation" approach is correct. The key challenge is the calculation logic.

**Refined Calculation Logic (Final Decision):**

The most robust method that avoids issues with partial payments is to revalue the outstanding foreign currency amount of each individual document/account.

1.  **Initialize**: `total_adjustment = Decimal(0)`; `je_lines = []`.
2.  **Process AR**:
    *   Fetch all open Sales Invoices in foreign currencies.
    *   For each invoice `inv`:
        *   `outstanding_fc = inv.total_amount - inv.amount_paid`.
        *   If `outstanding_fc == 0`, continue.
        *   `rate_invoice = inv.exchange_rate`.
        *   `rate_reval = get_rate(inv.currency_code, base_currency, revaluation_date)`.
        *   `adjustment = outstanding_fc * (rate_reval - rate_invoice)`.
        *   `total_adjustment += adjustment`.
        *   Add a JE line to `je_lines` for `adjustment` amount, debiting/crediting the customer's AR account.
3.  **Process AP**:
    *   Fetch all open Purchase Invoices in foreign currencies.
    *   For each invoice `pi`:
        *   `outstanding_fc = pi.total_amount - pi.amount_paid`.
        *   `rate_invoice = pi.exchange_rate`.
        *   `rate_reval = get_rate(...)`.
        *   `adjustment = outstanding_fc * (rate_invoice - rate_reval)`. (Note the inverted rate subtraction for liabilities).
        *   `total_adjustment += adjustment`.
        *   Add a JE line for `adjustment` to the vendor's AP account.
4.  **Process Bank Accounts**:
    *   Fetch all foreign currency bank accounts.
    *   For each bank account `ba`:
        *   `balance_fc = ba.current_balance`.
        *   `current_base_balance = get_gl_balance(ba.gl_account_id, revaluation_date)`.
        *   `rate_reval = get_rate(...)`.
        *   `revalued_base_balance = balance_fc * rate_reval`.
        *   `adjustment = revalued_base_balance - current_base_balance`.
        *   `total_adjustment += adjustment`.
        *   Add a JE line for `adjustment` to the bank's GL account.
5.  **Finalize JE**:
    *   If `total_adjustment > 0`, it's a net gain. Post `total_adjustment` as a credit to the "Unrealized Forex Gain" account.
    *   If `total_adjustment < 0`, it's a net loss. Post `abs(total_adjustment)` as a debit to the "Unrealized Forex Loss" account.
    *   Create the JE. Post it.
    *   Create and post the reversing entry for the next day.

This logic is sound and covers all necessary aspects.

#### **1.3. Execution Plan**

I will now execute the plan, which involves creating a new manager and a new UI workflow, and updating related configuration and service files.

**Step 1: Database & Configuration**
-   [ ] **Files:** `scripts/initial_data.sql`, `data/chart_of_accounts/general_template.csv`
    -   [ ] Add accounts `7201` and `8201` for Unrealized Gain/Loss.
    -   [ ] Add `SysAcc_UnrealizedForexGain` and `SysAcc_UnrealizedForexLoss` to `core.configuration`.
-   [ ] **File:** `app/utils/pydantic_models.py`
    -   [ ] No immediate changes seem necessary, but I will double-check as I implement the manager.

**Step 2: Core Logic Implementation**
-   [ ] **File:** `app/accounting/forex_manager.py` (New File)
    -   [ ] Create the `ForexManager` class.
    -   [ ] Implement the `create_unrealized_gain_loss_je` method using the detailed logic defined above.
-   [ ] **File:** `app/accounting/journal_entry_manager.py`
    -   [ ] Add a new method: `async def create_reversing_entry(self, original_entry_id: int, reversal_date: date, user_id: int) -> Result[JournalEntry]:`. This will be a more generic version of the existing `reverse_journal_entry` method.
-   [ ] **File:** `app/core/application_core.py`
    -   [ ] Register and instantiate the new `ForexManager`.

**Step 3: UI Implementation**
-   [ ] **File:** `app/ui/accounting/accounting_widget.py`
    -   [ ] Add a new `QGroupBox("Period-End Procedures")`.
    -   [ ] Add a `QPushButton("Run Forex Revaluation...")` inside it.
    -   [ ] Implement the slot for this button to prompt for a date and trigger the `ForexManager` method.

**Step 4: WHT Reporting (Stub Implementation)**
-   While focusing on Forex, I will also flesh out the `WithholdingTaxManager` to be more complete, as the groundwork is already laid.
-   [ ] **File:** `app/tax/withholding_tax_manager.py`
    -   [ ] Enhance `generate_s45_form_data`. Instead of a generic payment, it should take a specific `WithholdingTaxCertificate` ID. It will fetch the certificate and its related payment/vendor data to populate a dictionary ready for PDF generation.
    -   [ ] This makes the feature more concrete and ready for a future UI element to trigger it.

**Step 5: Rigorous Validation**
-   [ ] After each file is modified or created, I will perform a diff against the previous version to ensure precision and prevent regressions.
-   [ ] I will mentally trace the full workflow from the UI click to the JE creation to ensure all dependencies are met and the logic flows correctly.

This plan is comprehensive and addresses the next logical steps in the application's development. I will now generate the necessary files.
