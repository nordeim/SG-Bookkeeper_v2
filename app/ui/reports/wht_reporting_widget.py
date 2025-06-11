# File: app/ui/reports/wht_reporting_widget.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QTableView, QPushButton,
    QMessageBox, QLabel, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, Slot, QTimer, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon
from typing import Optional, TYPE_CHECKING

from app.core.application_core import ApplicationCore
from app.main import schedule_task_from_qt
from app.utils.result import Result
from app.common.enums import PaymentTypeEnum, PaymentEntityTypeEnum
from app.ui.reports.wht_payment_table_model import WHTPaymentTableModel
from app.models.accounting.withholding_tax_certificate import WithholdingTaxCertificate
from app.models.business.payment import Payment

if TYPE_CHECKING:
    from PySide6.QtGui import QPaintDevice

class WHTReportingWidget(QWidget):
    def __init__(self, app_core: ApplicationCore, parent: Optional["QWidget"] = None):
        super().__init__(parent)
        self.app_core = app_core
        self._init_ui()
        QTimer.singleShot(0, self._on_refresh_clicked)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        controls_group = QGroupBox("Withholding Tax Payments")
        controls_layout = QHBoxLayout(controls_group)
        controls_layout.addWidget(QLabel("This lists all vendor payments where Withholding Tax was applicable."))
        controls_layout.addStretch()
        self.refresh_button = QPushButton(QIcon(":/icons/refresh.svg"), "Refresh List")
        controls_layout.addWidget(self.refresh_button)
        main_layout.addWidget(controls_group)

        self.payments_table = QTableView()
        self.payments_table.setAlternatingRowColors(True)
        self.payments_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.payments_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.payments_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.payments_table.setSortingEnabled(True)
        
        self.table_model = WHTPaymentTableModel()
        self.payments_table.setModel(self.table_model)
        header = self.payments_table.horizontalHeader()
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Vendor Name
        self.payments_table.setColumnHidden(0, True) # Hide ID column
        main_layout.addWidget(self.payments_table)

        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.generate_cert_button = QPushButton(QIcon(":/icons/reports.svg"), "Generate S45 Certificate")
        self.generate_cert_button.setEnabled(False)
        action_layout.addWidget(self.generate_cert_button)
        main_layout.addLayout(action_layout)

        self.setLayout(main_layout)
        self._connect_signals()

    def _connect_signals(self):
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        self.payments_table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.generate_cert_button.clicked.connect(self._on_generate_certificate_clicked)

    @Slot()
    def _on_refresh_clicked(self):
        if not self.app_core.current_user:
            QMessageBox.warning(self, "Authentication Error", "No user logged in.")
            return
        
        self.refresh_button.setEnabled(False)
        self.generate_cert_button.setEnabled(False)
        # We need a way to filter payments where WHT was applied. For now, we list all vendor payments.
        # A future enhancement would be a flag on the Payment model or a lookup via WHT certificates.
        future = schedule_task_from_qt(self.app_core.payment_manager.get_payments_for_listing(
            entity_type=PaymentEntityTypeEnum.VENDOR,
            page_size=-1 # Get all
        ))
        if future:
            future.add_done_callback(self._handle_load_payments_result)

    def _handle_load_payments_result(self, future):
        self.refresh_button.setEnabled(True)
        try:
            result = future.result()
            if result.is_success:
                self.table_model.update_data(result.value or [])
            else:
                QMessageBox.warning(self, "Error", f"Failed to load payments:\n{', '.join(result.errors)}")
        except Exception as e:
            self.app_core.logger.error(f"Error handling WHT payment list result: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"An unexpected error occurred while loading payments: {e}")

    @Slot()
    def _on_selection_changed(self):
        self.generate_cert_button.setEnabled(bool(self.payments_table.selectionModel().hasSelection()))

    @Slot()
    def _on_generate_certificate_clicked(self):
        selected_indexes = self.payments_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        selected_payment_summary = self.table_model.data(selected_indexes[0], Qt.ItemDataRole.UserRole)
        if not selected_payment_summary:
            return
            
        self.generate_cert_button.setEnabled(False)
        future = schedule_task_from_qt(self._fetch_payment_and_generate_cert(selected_payment_summary.id))
        if future:
            future.add_done_callback(self._handle_generate_cert_result)

    async def _fetch_payment_and_generate_cert(self, payment_id: int):
        # We need the full Payment ORM object with its vendor relationship loaded.
        payment_orm = await self.app_core.payment_manager.payment_service.get_payment_with_vendor(payment_id)
        if not payment_orm:
            return Result.failure([f"Payment with ID {payment_id} not found or vendor details could not be loaded."])
        
        return await self.app_core.withholding_tax_manager.create_wht_certificate_from_payment(
            payment=payment_orm,
            user_id=self.app_core.current_user.id
        )

    def _handle_generate_cert_result(self, future):
        self.generate_cert_button.setEnabled(bool(self.payments_table.selectionModel().hasSelection()))
        try:
            result: Result[WithholdingTaxCertificate] = future.result()
            if result.is_success and result.value:
                cert = result.value
                QMessageBox.information(self, "Success", 
                    f"Successfully created Withholding Tax Certificate.\n\n"
                    f"Certificate No: {cert.certificate_no}\n"
                    f"Vendor: {cert.vendor.name}\n"
                    f"Tax Amount: {cert.tax_amount:,.2f}"
                )
            else:
                QMessageBox.warning(self, "Generation Failed", f"Could not generate certificate:\n{', '.join(result.errors)}")
        except Exception as e:
            self.app_core.logger.error(f"Error handling WHT certificate generation result: {e}", exc_info=True)
            QMessageBox.critical(self, "Fatal Error", f"An unexpected error occurred: {e}")
