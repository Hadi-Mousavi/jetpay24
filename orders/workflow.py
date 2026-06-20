"""
Order status workflow engine.

Defines the allowed transitions between order statuses and provides
validation helpers used by the admin and (optionally) API views.

Workflow diagram:
  submitted ─────────────────→ waiting_customer_payment
       │                              │
       └──────────────────────→ under_review ←──── cancelled (recovery)
                                      │
                                in_progress ←────── completed (recovery)
                               /    │    \
                              /     │     \
                  waiting_customer  │    cancelled
                       │            │
                    in_progress  completed

Full edges:
  submitted            → waiting_customer_payment, under_review
  under_review         → in_progress, cancelled
  waiting_customer_payment → payment_rejected, under_review
  payment_rejected     → waiting_customer_payment
  in_progress          → waiting_customer, completed, cancelled
  waiting_customer     → in_progress, cancelled
  completed            → in_progress            (recovery / reopen only)
  cancelled            → under_review           (recovery / reopen only)
  draft                → submitted
  rejected             → (terminal)             (legacy)
"""

from __future__ import annotations


class InvalidTransition(Exception):
    """Raised when a requested status transition is not in TRANSITIONS."""

    def __init__(
        self,
        from_status: str,
        to_status: str,
        from_label: str = '',
        to_label: str = '',
    ):
        self.from_status = from_status
        self.to_status   = to_status
        self.from_label  = from_label
        self.to_label    = to_label
        super().__init__(
            f'Transition {from_status!r} → {to_status!r} is not allowed.'
        )

    def persian_message(self) -> str:
        src = self.from_label or self.from_status
        dst = self.to_label   or self.to_status
        return f'تغییر وضعیت از «{src}» به «{dst}» در این گردش‌کار مجاز نیست.'


# ---------------------------------------------------------------------------
# Transition table
# ---------------------------------------------------------------------------
# Key   = current status  (str constant, must match Order.STATUS_* values)
# Value = list of statuses that can follow
# ---------------------------------------------------------------------------

TRANSITIONS: dict[str, list[str]] = {
    'draft':                    ['submitted'],
    'submitted':                ['waiting_customer_payment', 'under_review'],
    'under_review':             ['in_progress', 'cancelled'],
    'waiting_customer_payment': ['payment_rejected', 'under_review'],
    'payment_rejected':         ['waiting_customer_payment'],
    'in_progress':              ['waiting_customer', 'completed', 'cancelled'],
    'waiting_customer':         ['in_progress', 'cancelled'],
    'completed':                ['in_progress'],    # recovery path only
    'cancelled':                ['under_review'],   # recovery path only
    'rejected':                 [],   # legacy terminal state
}

# Persian labels for error messages
STATUS_LABELS: dict[str, str] = {
    'draft':                    'پیش‌نویس',
    'submitted':                'ثبت شده',
    'under_review':             'در حال بررسی',
    'waiting_customer_payment': 'در انتظار پرداخت',
    'payment_rejected':         'پرداخت رد شده',
    'in_progress':              'در حال انجام',
    'waiting_customer':         'منتظر اقدام مشتری',
    'completed':                'تکمیل شده',
    'cancelled':                'لغو شده',
    'rejected':                 'رد شده',
}


# ---------------------------------------------------------------------------
# Recovery (reopen) edge detection
# ---------------------------------------------------------------------------
# These transitions reverse a terminal state.  They are allowed by TRANSITIONS
# but should be clearly labelled as "reopen" actions in admin UI and timeline.
# ---------------------------------------------------------------------------

RECOVERY_TRANSITIONS: set[tuple[str, str]] = {
    ('completed', 'in_progress'),
    ('cancelled', 'under_review'),
}


def is_recovery_transition(from_status: str, to_status: str) -> bool:
    """Return True if from_status → to_status is a recovery / reopen edge."""
    return (from_status, to_status) in RECOVERY_TRANSITIONS


def get_allowed_transitions(current_status: str) -> list[str]:
    """Return the list of statuses reachable from *current_status*."""
    return list(TRANSITIONS.get(current_status, []))


def is_valid_transition(from_status: str, to_status: str) -> bool:
    """Return True iff *from_status* → *to_status* is a valid workflow edge."""
    return to_status in TRANSITIONS.get(from_status, [])


def validate_transition(from_status: str, to_status: str) -> None:
    """
    Raise InvalidTransition if *from_status* → *to_status* is not allowed.

    No-op when from_status == to_status (no change has occurred).
    """
    if from_status == to_status:
        return
    if not is_valid_transition(from_status, to_status):
        raise InvalidTransition(
            from_status, to_status,
            STATUS_LABELS.get(from_status, from_status),
            STATUS_LABELS.get(to_status, to_status),
        )
