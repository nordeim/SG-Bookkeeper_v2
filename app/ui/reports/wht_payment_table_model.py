# File: app/ui/reports/wht_payment_table_model.py
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import date

from app.utils.pydantic_models import PaymentSummaryData

class WHTPaymentTableModel(QAbstractTableModel):
    def __init__(self, data: Optional[List[PaymentSummaryData]] = None, parent=None):
        super().__init__(parent)
        self._headers = ["ID", "Payment No", "Payment Date", "Vendor Name", "Gross Amount", "Currency", "WHT Applied?"]
        self._data: List[PaymentSummaryData] = data or []

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid(): return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole) -> Optional[str]:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid(): return None
        
        row, col = index.row(), index.column()
        if not (0 <= row < len(self._data)): return None
            
        payment = self._data[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0: return payment.id
            if col == 1: return payment.payment_no
            if col == 2: return payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else ""
            if col == 3: return payment.entity_name
            if col == 4: return f"{payment.amount:,.2f}"
            if col == 5: return payment.currency_code
            if col == 6: return "Yes" # This view only shows applicable payments
        
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 4: # Amount
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        
        elif role == Qt.ItemDataRole.UserRole:
            return payment

        return None

    def update_data(self, new_data: List[PaymentSummaryData]):
        self.beginResetModel()
        self._data = new_data or []
        self.endResetModel()
