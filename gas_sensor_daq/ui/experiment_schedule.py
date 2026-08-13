from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gas_sensor_daq.ui.widgets.cards import section_card


class ExperimentSchedulePanel:
    """Visual composition of the experiment schedule and mixture calculator."""

    def __init__(
        self,
        *,
        table,
        event_input,
        duration_input,
        rh_input,
        gas_inputs,
        dry_mfc5_input,
        mfc6_remainder_label,
        apply_mixture_button,
        target_total_label,
        target_total_input,
        target_total_unit_label,
        rate_control,
        issues_label,
        action_buttons,
        toggle_schedule,
        toggle_details,
    ):
        self.details_title = QLabel("Mixture Calculator")
        self.details_title.setObjectName("recipeDetailsTitle")
        self.details_step_label = QLabel("Selected: step 1")
        self.details_step_label.setObjectName("recipeDetailsStep")

        self.details_chevron = self._chevron(
            "Show or hide selected-step details", toggle_details
        )
        self.schedule_chevron = self._chevron(
            "Show or hide experiment schedule", toggle_schedule
        )

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 3, 0, 0)
        content_layout.setSpacing(8)
        content_layout.addWidget(table)
        content_layout.addWidget(self._event_actions(event_input, action_buttons))
        content_layout.addWidget(self._details_header())

        self.details_content = self._mixture_band(
            rh_input,
            gas_inputs,
            dry_mfc5_input,
            mfc6_remainder_label,
            duration_input,
            apply_mixture_button,
        )
        content_layout.addWidget(self.details_content)
        content_layout.insertWidget(
            0,
            self._schedule_settings(
                target_total_label,
                target_total_input,
                target_total_unit_label,
                rate_control,
            ),
        )

        self.header_controls = QWidget()
        header_controls_layout = QHBoxLayout(self.header_controls)
        header_controls_layout.setContentsMargins(0, 0, 0, 0)
        header_controls_layout.setSpacing(5)
        header_controls_layout.addWidget(issues_label)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)
        header_layout.addWidget(self.header_controls)
        header_layout.addWidget(self.schedule_chevron)

        self.card = section_card(
            "Experiment Schedule",
            None,
            content_layout,
            expanding=False,
            header_widget=header_widget,
        )
        self.content_frame = self.card.content_frame
        self.card.setMinimumHeight(488)

    @staticmethod
    def _chevron(tooltip, callback):
        button = QPushButton()
        button.setObjectName("logChevron")
        button.setFixedSize(24, 22)
        button.setCheckable(True)
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _event_actions(event_input, action_buttons):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(QLabel("Event"))
        layout.addWidget(event_input)
        layout.addStretch()
        for button in action_buttons:
            layout.addWidget(button)
        return row

    def _details_header(self):
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.details_title)
        layout.addWidget(self.details_step_label)
        layout.addStretch()
        layout.addWidget(self.details_chevron)
        return header

    @staticmethod
    def _schedule_settings(
        target_total_label,
        target_total_input,
        target_total_unit_label,
        rate_control,
    ):
        target_control = QWidget()
        target_layout = QHBoxLayout(target_control)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(4)
        target_layout.addWidget(target_total_input)
        target_layout.addWidget(target_total_unit_label)

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(target_total_label)
        layout.addWidget(target_control)
        layout.addSpacing(18)
        rate_label = QLabel("Sampling rate:")
        rate_label.setObjectName("recipeMixtureTitle")
        layout.addWidget(rate_label)
        layout.addWidget(rate_control)
        layout.addStretch()
        return row

    @staticmethod
    def _mixture_band(
        rh_input,
        gas_inputs,
        dry_mfc5_input,
        mfc6_remainder_label,
        duration_input,
        apply_mixture_button,
    ):
        band = QFrame()
        band.setObjectName("recipeMixtureBand")
        layout = QVBoxLayout(band)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        mixture_row = QHBoxLayout()
        mixture_row.setContentsMargins(0, 0, 0, 0)
        mixture_row.setSpacing(8)
        title = QLabel("Mixture:")
        title.setObjectName("recipeMixtureTitle")
        mixture_row.addWidget(title)
        for label, widget in (
            ("RH", rh_input),
            ("MFC 1", gas_inputs[1]),
            ("MFC 2", gas_inputs[2]),
            ("MFC 3", gas_inputs[3]),
        ):
            mixture_row.addWidget(QLabel(label))
            mixture_row.addWidget(widget)
        mixture_row.addStretch()

        dry_air_row = QHBoxLayout()
        dry_air_row.setContentsMargins(0, 0, 0, 0)
        dry_air_row.setSpacing(8)
        title = QLabel("Dry-air allocation:")
        title.setObjectName("recipeMixtureTitle")
        dry_air_row.addWidget(title)
        dry_air_row.addWidget(QLabel("MFC5 dry"))
        dry_air_row.addWidget(dry_mfc5_input)
        dry_air_row.addWidget(QLabel("MFC6 remainder"))
        dry_air_row.addWidget(mfc6_remainder_label)
        dry_air_row.addStretch()

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        duration_label = QLabel("Duration:")
        duration_label.setObjectName("recipeMixtureTitle")
        action_row.addWidget(duration_label)
        action_row.addWidget(duration_input)
        action_row.addStretch()
        action_row.addWidget(apply_mixture_button)

        formula = QLabel(
            "Formula: MFC4 = target x RH / 100; MFC6 = target - (MFC1 + MFC2 + MFC3 + MFC4 + MFC5). "
            "Enter RH, MFC1-3, and MFC5 manually; MFC4 and MFC6 are calculated automatically."
        )
        formula.setObjectName("recipeMixtureFormula")
        formula.setWordWrap(True)

        layout.addLayout(mixture_row)
        layout.addLayout(dry_air_row)
        layout.addLayout(action_row)
        layout.addWidget(formula)
        return band
