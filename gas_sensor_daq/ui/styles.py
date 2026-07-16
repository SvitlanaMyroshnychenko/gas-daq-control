def build_styles(assets_dir):
    chevron_down_path = (assets_dir / "chevron_down.svg").as_posix()
    return """
            QWidget#appBackground {
                background: #f6f8fb;
            }
            QFrame#toolbar {
                background: #ffffff;
                border: 1px solid #d7e0eb;
                border-radius: 6px;
            }
            QFrame#toolbarDivider {
                background: #e5eaf0;
                border: none;
                min-width: 1px;
                max-width: 1px;
            }
            QFrame#bottomBar {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 7px;
            }
            QSplitter#bodySplitter::handle {
                background: #d7e0eb;
                width: 3px;
                margin: 0;
            }
            QSplitter#centerSplitter::handle {
                background: #d7e0eb;
                height: 3px;
                margin: 0;
            }
            QSplitter#centerSplitter::handle:hover {
                background: #cbd5e1;
            }
            QScrollArea#panelScroll {
                background: transparent;
                border: none;
            }
            QScrollArea#panelScroll > QWidget > QWidget {
                background: transparent;
            }
            QFrame#toolbarBlock {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QFrame#sectionCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#compactSectionCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#graphCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#logCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 8px;
            }
            QFrame#logContentFrame {
                border: none;
                background: transparent;
                padding-bottom: 8px;
            }
            QLabel#graphTitle {
                color: #0f172a;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#graphDot {
                min-width: 10px;
                max-width: 10px;
                min-height: 10px;
                max-height: 10px;
            }
            QLabel#graphAction {
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                min-width: 22px;
                max-width: 22px;
            }
            QLabel#logIcon {
                min-width: 16px;
                max-width: 16px;
            }
            QLabel#sectionTitle {
                color: #0f172a;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#sectionIcon {
                min-width: 16px;
                max-width: 16px;
            }
            QPushButton#sectionChevron {
                background: transparent;
                border: none;
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                min-height: 20px;
            }
            QPushButton#sectionChevron:hover {
                background: #eef2f7;
                border-radius: 4px;
            }
            QFrame#metricRow,
            QFrame#deviceRow,
            QFrame#deviceStatusRow,
            QFrame#readingCard,
            QFrame#controlCard,
            QFrame#gasChannelRow,
            QFrame#environmentChannelRow {
                background: #fbfcfe;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
            QFrame#deviceSetupPanel {
                background: transparent;
                border: none;
            }
            QFrame#metricRow {
                min-height: 34px;
                max-height: 38px;
            }
            QFrame#compactReadingRow,
            QFrame#compactStateRow {
                background: transparent;
                border: none;
                border-bottom: 1px solid #edf2f7;
                min-height: 36px;
                max-height: 40px;
            }
            QLabel#compactDot {
                min-width: 6px;
                max-width: 6px;
                min-height: 6px;
                max-height: 6px;
            }
            QLabel {
                color: #233244;
                font-size: 12px;
            }
            QLabel#caption,
            QLabel#metricName,
            QLabel#mutedLabel {
                color: #64748b;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel#toolbarSectionLabel {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#toolbarCaption {
                color: #475569;
                font-size: 11px;
                font-weight: 500;
            }
            QLabel#sectionLabel,
            QLabel#statusLineLabel {
                color: #0f172a;
                font-size: 12px;
                font-weight: 700;
            }
            QFrame#warningFrame {
                background: #fffbeb;
                border: 1px solid #facc15;
                border-radius: 7px;
                min-height: 34px;
            }
            QLabel#warningLabel {
                color: #92400e;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#warningIcon {
                min-width: 16px;
                max-width: 16px;
                min-height: 16px;
                max-height: 16px;
            }
            QLabel#envStatus {
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#envStatus[active="true"] {
                color: #15803d;
            }
            QLabel#metricValue,
            QLabel#toolbarValue {
                color: #0f172a;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#metricValue[metricColor="blue"] {
                color: #2563eb;
                font-size: 20px;
            }
            QLabel#metricValue[metricColor="orange"] {
                color: #f97316;
                font-size: 20px;
            }
            QLabel#metricValue[metricColor="purple"] {
                color: #7c3aed;
                font-size: 20px;
            }
            QLabel#metricValue[metricColor="teal"] {
                color: #0f9f9a;
                font-size: 20px;
            }
            QLabel#metricValue[compactMetric="true"] {
                color: #0f172a;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel#statusBadge {
                background: #dcfce7;
                color: #15803d;
                border: 1px solid #bbf7d0;
                border-radius: 5px;
                padding: 1px 7px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#statusBadge[state="running"] {
                background: #dcfce7;
                color: #15803d;
                border-color: #86efac;
            }
            QLabel#statusBadge[state="error"] {
                background: #fee2e2;
                color: #dc2626;
                border-color: #fca5a5;
            }
            QLabel#statusBadge[state="stopped"] {
                background: #fee2e2;
                color: #dc2626;
                border-color: #fca5a5;
            }
            QLabel#connectedLabel {
                color: #16a34a;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#connectedLabel[state="disconnected"] {
                color: #dc2626;
            }
            QLabel#deviceStatusDot {
                background: #16a34a;
                border-radius: 4px;
                min-width: 8px;
                max-width: 8px;
                min-height: 8px;
                max-height: 8px;
            }
            QLabel#deviceStatusDot[state="disconnected"] {
                background: #dc2626;
            }
            QLabel#readingIcon {
                color: #64748b;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 7px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 3px;
                min-height: 36px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
                background: transparent;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QComboBox,
            QSpinBox,
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 2px 7px;
                background: #ffffff;
                color: #172033;
                min-height: 26px;
            }
            QComboBox:disabled,
            QSpinBox:disabled,
            QLineEdit:disabled {
                color: #94a3b8;
                background: #f1f5f9;
            }
            QComboBox {
                padding-right: 28px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
                border-left: 1px solid transparent;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QComboBox::drop-down:hover {
                background: #f1f5f9;
                border-left-color: #e2e8f0;
            }
            QComboBox::down-arrow {
                image: url("__CHEVRON_DOWN__");
                width: 12px;
                height: 12px;
            }
            QComboBox#logRowsSelector {
                border: none;
                background: transparent;
                padding: 0 18px 0 0;
                min-height: 22px;
                color: #334155;
                font-weight: 600;
            }
            QComboBox#logRowsSelector::drop-down {
                width: 18px;
                border: none;
            }
            QComboBox#logRowsSelector::drop-down:hover {
                background: transparent;
                border: none;
            }
            QComboBox#logRowsSelector::down-arrow {
                image: url("__CHEVRON_DOWN__");
                width: 10px;
                height: 10px;
            }
            QListView#logRowsPopup {
                background: #ffffff;
                color: #172033;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                outline: none;
                padding: 2px;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
            }
            QListView#logRowsPopup::item {
                min-height: 22px;
                padding: 3px 8px;
                background: #ffffff;
            }
            QListView#logRowsPopup::item:hover,
            QListView#logRowsPopup::item:selected {
                background: #dbeafe;
                color: #0f172a;
            }
            QPushButton {
                min-height: 24px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                background: #ffffff;
                color: #172033;
            }
            QPushButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#logActionButton {
                min-height: 24px;
                padding: 2px 9px;
                border-radius: 6px;
                color: #172033;
                background: #ffffff;
            }
            QPushButton#logActionButton:disabled {
                color: #94a3b8;
                background: #f1f5f9;
                border-color: #dbe3ee;
            }
            QPushButton#stepButton {
                min-height: 24px;
                border-radius: 5px;
                padding: 0;
                font-size: 14px;
                font-weight: 700;
            }
            QPushButton#startButton,
            QPushButton#primaryButton {
                color: #15803d;
                border-color: #22c55e;
                background: #ecfdf3;
                font-weight: 700;
            }
            QPushButton#startButton:hover,
            QPushButton#primaryButton:hover {
                background: #dcfce7;
                border-color: #16a34a;
            }
            QPushButton#secondaryButton {
                color: #334155;
                border-color: #cbd5e1;
                background: #ffffff;
                font-weight: 600;
            }
            QPushButton#secondaryButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#toggleButton {
                min-height: 28px;
                font-weight: 600;
            }
            QPushButton#toggleButton[active="true"] {
                color: #15803d;
                border-color: #22c55e;
                background: #ecfdf3;
                font-weight: 700;
            }
            QPushButton#stopButton {
                color: #dc2626;
                border-color: #ef4444;
                background: #fef2f2;
                font-weight: 700;
            }
            QPushButton#stopButton:hover {
                background: #fee2e2;
                border-color: #dc2626;
            }
            QPushButton:disabled {
                color: #9ca3af;
                background: #eef2f7;
                border-color: #e5e7eb;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                gridline-color: #e2e8f0;
                color: #102033;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background: #eef2f7;
                color: #334155;
                border: 0;
                border-right: 1px solid #dbe3ee;
                border-bottom: 1px solid #dbe3ee;
                padding: 4px;
                font-weight: 700;
                font-size: 11px;
            }
            QPushButton#rateStepButton {
                min-width: 28px;
                max-width: 28px;
                min-height: 26px;
                max-height: 26px;
                border-radius: 0;
                padding: 0;
                color: #475569;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton#rateStepButton:first {
                border-top-left-radius: 5px;
                border-bottom-left-radius: 5px;
            }
            QDoubleSpinBox#rateSpinBox {
                min-height: 26px;
                max-height: 26px;
                border-radius: 0;
                border-left: none;
                border-right: none;
                padding: 0 4px;
                font-weight: 600;
            }
            QLabel#rateUnit {
                color: #475569;
                font-size: 11px;
            }
            QLabel#appTitle {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QFrame#toolbar {
                border-radius: 6px;
            }
            QLabel#caption {
                font-weight: 700;
            }
            QFrame#alertFrame {
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 5px;
            }
            QFrame#alertFrame[state="error"] {
                background: #fef2f2;
                border-color: #fecaca;
            }
            QLabel#alertIcon {
                background: #dbeafe;
                color: #2563eb;
                border-radius: 8px;
                font-weight: 800;
            }
            QLabel#alertLabel {
                color: #2563eb;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#alertLabel[state="error"] {
                color: #dc2626;
            }
            QPushButton#alertCloseButton {
                background: transparent;
                border: none;
                color: #2563eb;
                font-weight: 800;
                padding: 0;
            }
            QPushButton#folderButton {
                padding: 0;
                min-width: 30px;
                max-width: 30px;
                min-height: 26px;
                max-height: 26px;
            }
            QPushButton#configureButton {
                min-height: 28px;
                padding: 3px 9px;
                font-weight: 600;
            }
            QLineEdit#saveLocationInput {
                min-height: 26px;
                max-height: 26px;
            }
            QDoubleSpinBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 2px 7px;
                background: #ffffff;
                color: #172033;
                min-height: 26px;
                max-height: 26px;
                max-width: 62px;
            }
            QDoubleSpinBox:disabled {
                color: #94a3b8;
                background: #f1f5f9;
            }
            QLabel#rateUnit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background: #ffffff;
                color: #0f172a;
                font-weight: 700;
            }
        """.replace("__CHEVRON_DOWN__", chevron_down_path)
