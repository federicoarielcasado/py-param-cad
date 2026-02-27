"""
RevisionManager — ECO (Engineering Change Order) workflow management.

TODO Week 12: Implement ECO creation, status transitions, and delta export.
"""

from __future__ import annotations


class RevisionManager:
    """Manages revision lifecycle and ECO workflow. Stub for Week 12."""

    def issue_revision(self, revision_id: int, eco_number: str, eco_reason: str) -> bool:
        """Transition a revision from 'draft' to 'issued'."""
        raise NotImplementedError("ECO workflow — implementar en Semana 12.")

    def obsolete_revision(self, revision_id: int) -> bool:
        """Mark a revision as 'obsolete'."""
        raise NotImplementedError("ECO workflow — implementar en Semana 12.")

    def export_delta(self, revision_id_from: int, revision_id_to: int, output_path) -> bool:
        """Export parameter delta between two revisions."""
        raise NotImplementedError("Delta export — implementar en Semana 12.")
