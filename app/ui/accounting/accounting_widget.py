# File: app/ui/accounting/accounting_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QGroupBox, QHBoxLayout, QPushButton, QDateEdit, QMessageBox, QDialog, QDialogButtonBox
from PySide6.QtGui import QIcon
from PySide6.QtCore import Slot, QDate, QTimer, QMetaObject, Q_ARG, Qt

from app.ui.accounting.chart_of_accounts_widget import ChartOfAccountsWidget
from app.ui.accounting.journal_entries_widget import JournalEntriesWidget
from app.core.application_core import ApplicationCore 
from app.main import schedule_task_from_qt
from app.utils.result import Result
from app.models.accounting.journal_entry import JournalEntry
from datetime import date

class AccountingWidget(QWidget):
    def __init__(self, app_core: ApplicationCore, parent=None): 
        super().__init__(parent)
        self.app_core = app_core
        
        self.layout = QVBoxLayout(self)
        
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        
        self.coa_widget = ChartOfAccountsWidget(self.app_core)
        self.tab_widget.addTab(self.coa_widget, "Chart of Accounts")
        
        self.journal_entries_widget = JournalEntriesWidget(self.app_core)
        self.tab_widget.addTab(self.journal_entries_widget, "Journal Entries")
        
        self.period_end_widget = self._create_period_end_widget()
        self.tab_widget.addTab(self.period_end_widget, "Period-End Procedures")
        
        self.setLayout(self.layout)
    
    def _create_period_end_widget(self) -> QWidget:
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon_path_prefix = "" 
        try: import app.resources_rc; icon_path_prefix = ":/icons/"
        except ImportError: icon_path_prefix = "resources/icons/"

        forex_group = QGroupBox("Foreign Currency Revaluation")
        forex_layout = QHBoxLayout(forex_group)
        forex_layout.addWidget(QLabel("This process calculates and posts reversing journal entries for unrealized gains or losses on open foreign currency balances."))
        forex_layout.addStretch()
        self.run_forex_button = QPushButton(QIcon(icon_path_prefix + "accounting.svg"), "Run Forex Revaluation...")
        self.run_forex_button.clicked.connect(self._on_run_forex_revaluation)
        forex_layout.addWidget(self.run_forex_button)
        main_layout.addWidget(forex_group)

        # Placeholder for other period-end procedures
        main_layout.addStretch()

        return widget

    @Slot()
    def _on_run_forex_revaluation(self):
        if not self.app_core.current_user:
            QMessageBox.warning(self, "Authentication Error", "Please log in to perform this action.")
            return

        today = QDate.currentDate()
        last_day_prev_month = today.addDays(-today.day())
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Forex Revaluation")
        layout = QVBoxLayout(dialog)
        
        label = QLabel("Select the date as of which to revalue foreign currency balances.\nThis is typically a month-end, quarter-end, or year-end date.")
        layout.addWidget(label)
        
        date_edit = QDateEdit(last_day_prev_month)
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd/MM/yyyy")
        layout.addWidget(date_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            reval_date = date_edit.date().toPython()
            confirm_msg = (f"This will calculate and post unrealized foreign exchange gains/losses for all open items as of {reval_date.strftime('%Y-%m-%d')}.\n\n"
                           "A reversing journal entry will also be posted for the following day.\n\n"
                           "Do you want to continue?")
            reply = QMessageBox.question(self, "Confirm Forex Revaluation", confirm_msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                if not hasattr(self.app_core, "forex_manager"):
                    QMessageBox.critical(self, "Error", "Forex Manager component is not available.")
                    return
                self.run_forex_button.setEnabled(False)
                self.run_forex_button.setText("Processing...")
                future = schedule_task_from_qt(self.app_core.forex_manager.create_unrealized_gain_loss_je(reval_date, self.app_core.current_user.id))
                if future:
                    future.add_done_callback(self._handle_forex_revaluation_result)
                else:
                    self.run_forex_button.setEnabled(True)
                    self.run_forex_button.setText("Run Forex Revaluation...")
                    QMessageBox.critical(self, "Error", "Failed to schedule the forex revaluation task.")

    def _handle_forex_revaluation_result(self, future):
        self.run_forex_button.setEnabled(True)
        self.run_forex_button.setText("Run Forex Revaluation...")
        try:
            result: Result[JournalEntry] = future.result()
            if result.is_success:
                if result.value:
                    QMessageBox.information(self, "Success", f"Foreign currency revaluation complete.\nJournal Entry '{result.value.entry_no}' and its reversal have been created and posted.")
                else:
                    QMessageBox.information(self, "Completed", "Foreign currency revaluation run successfully. No significant adjustments were needed.")
            else:
                QMessageBox.critical(self, "Error", f"Forex revaluation failed:\n{', '.join(result.errors)}")
        except Exception as e:
            self.app_core.logger.error(f"An unexpected error occurred during forex revaluation callback: {e}", exc_info=True)
            QMessageBox.critical(self, "Fatal Error", f"An unexpected error occurred: {str(e)}")
