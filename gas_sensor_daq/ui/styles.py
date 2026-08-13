"""Central Qt stylesheet for the Gas Sensor DAQ application."""

def application_style(chevron_down_path: str) -> str:
    return """
            QWidget#appBackground {
                background: #f6f8fb;
            }
            QFrame#toolbar {
                background: transparent;
                border: none;
            }
            QFrame#toolbarControls {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
            }
            QFrame#toolbarSection,
            QFrame#toolbarButtonSection {
                background: transparent;
                border: none;
            }
            QFrame#toolbarSection[separated="true"] {
                border-left: 1px solid #e5eaf0;
            }
            QWidget#toolbarInlineGroup {
                background: transparent;
                border: none;
            }
            QLabel#toolbarInlineLabel {
                color: #64748b;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#toolbarFilePath {
                color: #64748b;
                font-size: 12px;
                font-weight: 600;
                padding-left: 0;
            }
            QFrame#fileLocationControl {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 6px;
            }
            QLabel#fileLocationIcon {
                background: transparent;
                border: none;
            }
            QLineEdit#saveLocationInput {
                border: none;
                border-radius: 0;
                background: transparent;
                padding: 0;
                min-height: 0;
            }
            QLineEdit#saveLocationInput:focus {
                border: none;
                background: transparent;
            }
            QPushButton#fileLocationBrowseButton {
                min-height: 30px;
                max-height: 30px;
                min-width: 38px;
                max-width: 38px;
                padding: 0;
                background: #ffffff;
                border: none;
                border-left: 1px solid #e5eaf0;
                border-radius: 0;
                border-top-right-radius: 5px;
                border-bottom-right-radius: 5px;
            }
            QPushButton#fileLocationBrowseButton:hover {
                background: #f8fafc;
            }
            QFrame#formatControl {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 6px;
            }
            QLabel#formatControlIcon {
                background: transparent;
                border: none;
            }
            QFrame#toolbarDivider {
                background: #e5eaf0;
                border: none;
                min-width: 1px;
                max-width: 1px;
            }
            QFrame#systemMessageBar {
                background: #eff6ff;
                border: none;
                border-radius: 5px;
            }
            QFrame#systemMessageBar[state="running"] {
                background: #ecfdf3;
                border-color: #86efac;
            }
            QFrame#systemMessageBar[state="stopped"] {
                background: #f8fafc;
                border-color: #cbd5e1;
            }
            QFrame#systemMessageBar[state="error"] {
                background: #fef2f2;
                border-color: #fca5a5;
            }
            QFrame#systemMessageBar[state="warning"] {
                background: #fffbeb;
                border-color: #fcd34d;
            }
            QLabel#systemMessageIcon {
                color: #2563eb;
                background: #dbeafe;
                border-radius: 7px;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#systemMessageIcon[state="running"] {
                color: #15803d;
                background: #dcfce7;
            }
            QLabel#systemMessageIcon[state="stopped"] {
                color: #475569;
                background: #e2e8f0;
            }
            QLabel#systemMessageIcon[state="error"] {
                color: #dc2626;
                background: #fee2e2;
            }
            QLabel#systemMessageIcon[state="warning"] {
                color: #a16207;
                background: #fef3c7;
            }
            QLabel#systemMessageText {
                color: #2563eb;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#systemMessageText[state="running"] {
                color: #15803d;
            }
            QLabel#systemMessageText[state="stopped"] {
                color: #475569;
            }
            QLabel#systemMessageText[state="error"] {
                color: #dc2626;
            }
            QLabel#systemMessageText[state="warning"] {
                color: #a16207;
            }
            QPushButton#systemMessageDismissButton {
                min-height: 18px;
                max-height: 18px;
                min-width: 18px;
                max-width: 18px;
                padding: 0;
                border: none;
                border-radius: 4px;
                color: #475569;
                background: transparent;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton#systemMessageDismissButton:hover {
                color: #1e293b;
                background: #dbeafe;
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
                border-radius: 5px;
            }
            QFrame#compactSectionCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
            }
            QFrame#experimentStatusCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
            }
            QFrame#graphCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
            }
            QFrame#logCard {
                background: #ffffff;
                border: 1px solid #dce5ef;
                border-radius: 5px;
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
            QFrame#eventSummary {
                background: #eef2f7;
                border: none;
                border-radius: 0;
            }
            QLabel#eventSummaryLabel {
                color: #475569;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#graphAction {
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                min-width: 22px;
                max-width: 22px;
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
            QPushButton#sectionChevron,
            QPushButton#logChevron {
                background: transparent;
                border: none;
                color: #475569;
                font-size: 16px;
                font-weight: 700;
                padding: 0;
                min-height: 20px;
            }
            QPushButton#sectionChevron:hover,
            QPushButton#logChevron:hover {
                background: #eef2f7;
                border-radius: 4px;
            }
            QFrame#metricRow,
            QFrame#deviceStatusRow,
            QFrame#readingCard,
            QFrame#controlCard {
                background: #fbfcfe;
                border: 1px solid #e2e8f0;
                border-radius: 7px;
            }
            QFrame#deviceRow {
                background: #f7f9fc;
                border: none;
                border-radius: 0;
            }
            QFrame#mfcChannelMonitorRow {
                background: transparent;
                border: none;
                border-bottom: 1px solid #edf2f7;
            }
            QPushButton#mfcZeroButton {
                min-height: 28px;
                color: #b91c1c;
                background: #ffffff;
                border: 1px solid #fecaca;
                border-radius: 3px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton#mfcZeroButton:hover {
                background: #fff1f2;
                border-color: #fca5a5;
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
                border-bottom: 1px solid #f1f5f9;
                min-height: 44px;
                max-height: 44px;
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
            QLabel#compactReadingName {
                color: #52637a;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#compactReadingDescription {
                color: #94a3b8;
                font-size: 10px;
                font-weight: 500;
            }
            QLabel#toolbarSectionLabel {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#sectionLabel,
            QLabel#statusLineLabel {
                color: #0f172a;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#metricValue,
            QLabel#toolbarValue {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#experimentStatusValue {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#experimentTimeValue {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#experimentStatusName {
                color: #52637a;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#experimentStateBadge {
                color: #475569;
                background: #f1f5f9;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#experimentStateBadge[state="idle"],
            QLabel#experimentStateBadge[state="running"] {
                color: #15803d;
                background: #dcfce7;
            }
            QLabel#experimentStateBadge[state="completed"] {
                color: #15803d;
                background: #dcfce7;
            }
            QLabel#experimentStateBadge[state="stopped"],
            QLabel#experimentStateBadge[state="error"] {
                color: #dc2626;
                background: #fee2e2;
            }
            QLabel#experimentStatusCaption {
                color: #64748b;
                font-size: 11px;
                font-weight: 700;
                margin-top: 2px;
            }
            QLabel#experimentEventValue {
                color: #52637a;
                font-size: 12px;
                font-weight: 600;
            }
            QProgressBar#experimentProgress {
                background: #e8edf3;
                border: none;
                border-radius: 5px;
                min-height: 10px;
                max-height: 10px;
            }
            QProgressBar#experimentProgress::chunk {
                background: #35a06f;
                border-radius: 5px;
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
            QLabel#metricValue[readingColor="blue"] {
                color: #2563eb;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#metricValue[readingColor="slate"] {
                color: #64748b;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#metricValue[readingColor="teal"] {
                color: #0f9f9a;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#metricValue[readingColor="purple"] {
                color: #7c3aed;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#statusBadge {
                background: #dcfce7;
                color: #15803d;
                border: none;
                border-radius: 6px;
                padding: 3px 8px;
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
            QLabel#connectedLabel[state="verified"] {
                color: #b45309;
            }
            QLabel#mfcRackStatus {
                color: #2563eb;
                background: #eff6ff;
                border: none;
                border-radius: 0;
                padding: 8px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#mfcMonitorHeader {
                color: #64748b;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#mfcTotalFlow {
                color: #0f172a;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#rateUnitBox {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QDoubleSpinBox#rateInput {
                min-height: 0;
                max-height: 32px;
                padding: 0 4px;
            }
            QLabel#mfcChannelName {
                color: #0f172a;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#mfcChannelName[channel="1"] { color: #2563eb; }
            QLabel#mfcChannelName[channel="2"] { color: #f97316; }
            QLabel#mfcChannelName[channel="3"] { color: #16a34a; }
            QLabel#mfcChannelName[channel="4"] { color: #7c3aed; }
            QLabel#mfcChannelName[channel="5"] { color: #dc2626; }
            QLabel#mfcChannelName[channel="6"] { color: #0f9f9a; }
            QLabel#mfcChannelValue {
                color: #1e293b;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#mfcChannelStatus {
                color: #64748b;
                font-size: 10px;
                font-weight: 700;
            }
            QLabel#mfcChannelStatus[state="ok"] {
                color: #15803d;
            }
            QLabel#mfcChannelStatus[state="alarm"] {
                color: #dc2626;
            }
            QLabel#mfcChannelStatus[state="simulated"] {
                color: #64748b;
            }
            QLabel#mfcChannelSerial {
                color: #94a3b8;
                font-size: 9px;
                font-weight: 600;
            }
            QLabel#mfcChannelSerial[state="alarm"] {
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
            QLabel#deviceStatusDot[state="verified"] {
                background: #d97706;
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
            QDoubleSpinBox,
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
            QDoubleSpinBox:disabled,
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
            QPushButton#startButton {
                color: #15803d;
                border: 1px solid #bbf7d0;
                border-radius: 5px;
                background: transparent;
                padding: 0 6px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#startButton:hover {
                background: #dcfce7;
                border-color: #86efac;
            }
            QPushButton#startButton {
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#startButton:disabled {
                color: #94a3b8;
                border-color: #dbe3ee;
                background: #f1f5f9;
            }
            QPushButton#plotModeButton {
                min-width: 104px;
                color: #475569;
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0;
                font-size: 12px;
                font-weight: 600;
                padding: 2px 12px;
            }
            QPushButton#plotModeButton[position="start"] {
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
            }
            QPushButton#plotModeButton[position="end"] {
                border-left: none;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QPushButton#plotModeButton[active="true"] {
                color: #1d4ed8;
                background: #eff6ff;
                border-color: #60a5fa;
                font-weight: 700;
            }
            QLabel#flowLegendItem {
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox#toolbarFormatSelector {
                min-height: 0;
                max-height: 30px;
                border: none;
                border-radius: 0;
                background: transparent;
                color: #172033;
                padding-top: 0;
                padding-bottom: 0;
            }
            QComboBox#toolbarFormatSelector:on {
                background: #ffffff;
                color: #172033;
            }
            QComboBox#toolbarFormatSelector::drop-down {
                border: none;
                width: 22px;
            }
            QComboBox#toolbarFormatSelector::drop-down:hover {
                background: #f8fafc;
                border: none;
            }
            QListView#toolbarFormatPopup {
                background: #ffffff;
                color: #172033;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                outline: none;
                padding: 2px;
                selection-background-color: #dbeafe;
                selection-color: #0f172a;
            }
            QListView#toolbarFormatPopup::item {
                min-height: 24px;
                padding: 3px 8px;
                background: #ffffff;
                color: #172033;
            }
            QListView#toolbarFormatPopup::item:hover,
            QListView#toolbarFormatPopup::item:selected {
                background: #dbeafe;
                color: #0f172a;
            }
            QPushButton#rateStepButton {
                min-height: 0;
                max-height: 32px;
                min-width: 38px;
                max-width: 38px;
                border: none;
                background: transparent;
                padding: 0;
                text-align: center;
                font-size: 15px;
                font-weight: 700;
            }
            QPushButton#rateStepButton:hover {
                background: #eff6ff;
            }
            QPushButton#folderButton {
                min-height: 0;
                max-height: 32px;
                min-width: 32px;
                max-width: 32px;
                padding: 0;
                border-radius: 5px;
            }
            QPushButton#stopButton {
                color: #dc2626;
                border: 1px solid #fecaca;
                border-radius: 5px;
                background: transparent;
                padding: 0 6px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#stopButton:hover {
                background: #fee2e2;
                border-color: #fca5a5;
            }
            QPushButton#stopButton {
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#recipeDuplicateButton {
                color: #334155;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeDuplicateButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton#recipeAddButton {
                color: #1d4ed8;
                background: transparent;
                border: 1px solid #bfdbfe;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeAddButton:hover {
                background: #dbeafe;
                border-color: #93c5fd;
            }
            QPushButton#recipeRemoveButton {
                color: #dc2626;
                background: transparent;
                border: 1px solid #fecaca;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeRemoveButton:hover {
                background: #fee2e2;
                border-color: #fca5a5;
            }
            QPushButton#recipeClearButton {
                color: #334155;
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 0 9px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeClearButton:hover {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QLabel#recipeMaxTotal {
                color: #475569;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeTargetUnit {
                color: #475569;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeMixtureTitle {
                color: #334155;
                font-size: 11px;
                font-weight: 700;
            }
            QFrame#recipeMixtureBand {
                background: transparent;
                border: none;
                border-radius: 0;
            }
            QFrame#recipeMixtureDivider {
                background: #d6e2ef;
                border: none;
            }
            QLabel#recipeMixtureValue {
                color: #0f172a;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeMixtureFormula {
                color: #475569;
                background: #eef5fb;
                border-left: 3px solid #60a5fa;
                border-radius: 0;
                padding: 5px 7px;
                font-size: 10px;
            }
            QLabel#recipeDetailsTitle {
                color: #1e293b;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#recipeDetailsStep {
                color: #64748b;
                font-size: 11px;
            }
            QDoubleSpinBox#recipeMixtureInput {
                min-height: 0;
                max-height: 24px;
                padding: 0 4px;
                border-radius: 3px;
            }
            QLineEdit#recipeDurationInput {
                min-height: 24px;
                max-height: 24px;
                padding: 0 4px;
                border-radius: 3px;
            }
            QPushButton#recipeMixtureButton {
                color: #1d4ed8;
                background: #ffffff;
                border: 1px solid #bfdbfe;
                border-radius: 3px;
                padding: 0 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton#recipeMixtureButton:hover {
                background: #dbeafe;
                border-color: #93c5fd;
            }
            QDoubleSpinBox#recipeTargetTotal {
                min-height: 0;
                max-height: 22px;
                padding-top: 0;
                padding-bottom: 0;
                border-radius: 4px;
            }
            QLineEdit#recipeEventInput {
                min-height: 0;
                max-height: 28px;
                padding: 0 7px;
                border-radius: 4px;
            }
            QLabel#recipeIssues {
                color: #b91c1c;
                background: #fee2e2;
                border: 1px solid #fecaca;
                border-radius: 5px;
                padding: 3px 6px;
                font-size: 11px;
                font-weight: 700;
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
            QTableWidget#recipeTable::item {
                border: 0;
                border-radius: 0;
                padding: 0 4px;
            }
            QTableWidget#recipeTable {
                background: #ffffff;
                alternate-background-color: #fbfcfe;
                border: 1px solid #e4ebf3;
                border-radius: 0;
                gridline-color: #e7edf4;
            }
            QTableWidget#recipeTable QHeaderView::section {
                background: #ffffff;
                color: #334155;
                border: 0;
                border-right: 1px solid #edf1f5;
                border-bottom: 1px solid #dfe7f0;
                padding: 5px 4px;
                font-weight: 700;
                font-size: 11px;
            }
            QTableWidget#recipeTable::item:selected,
            QTableWidget#recipeTable::item:selected:!active {
                background: #fff8e7;
                color: #0f172a;
                border: 0;
                outline: none;
            }
            QTableWidget#recipeTable QLineEdit {
                min-height: 0;
                max-height: 20px;
                padding: 0 3px;
                border: 1px solid #d1dbe7;
                border-radius: 0;
                background: #ffffff;
            }
            QTableWidget#recipeTable QLineEdit:focus {
                border: 1px solid #2563eb;
                border-radius: 0;
                background: #ffffff;
            }
            QFrame#recipeMixtureBand {
                background: #f8fafc;
                border: 0;
                border-radius: 0;
            }
            QHeaderView::section {
                background: #eef2f7;
                color: #334155;
                border: 0;
                border-right: 1px solid #dbe3ee;
                border-bottom: 1px solid #dbe3ee;
                padding: 5px 4px;
                font-weight: 700;
                font-size: 11px;
            }
            QTableWidget#logPreviewTable {
                border: 1px solid #dbe3ee;
                border-radius: 0;
                gridline-color: #e2e8f0;
                background: #ffffff;
            }
            QTableWidget#logPreviewTable::item {
                border: none;
                border-right: 1px solid #e2e8f0;
                border-bottom: 1px solid #e2e8f0;
                padding: 2px 5px;
    """.replace("__CHEVRON_DOWN__", chevron_down_path)

