"""Social features mixin (notifications, comments, votes, tags, reminders) for hybrid approval queue store."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from teaagent.subagents._approval_queue import (
    ApprovalRequestStatus,
)

logger = logging.getLogger(__name__)


class HybridStoreSocialMixin:
    """Mixin providing social operations for HybridApprovalQueueStore."""

    def _create_notification(
        self,
        notification_type: str,
        message: str,
        request_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        severity: str = 'info',
    ) -> None:
        """Create a notification.

        Args:
            notification_type: Type of notification
            message: Notification message
            request_id: Related request ID
            parent_run_id: Related parent run ID
            severity: Notification severity
        """
        if not self.config.enable_notifications:
            return

        self._ensure_notifications()

        with self._lock:
            notification = {
                'timestamp': time.time(),
                'type': notification_type,
                'message': message,
                'request_id': request_id,
                'parent_run_id': parent_run_id,
                'severity': severity,
            }
            self._notifications.append(notification)
        logger.info(f'Notification: {notification_type} - {message}')

    def get_notifications(
        self,
        limit: int = 100,
        notification_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get notifications.

        Args:
            limit: Maximum number of notifications to return
            notification_type: Filter by notification type
            severity: Filter by severity

        Returns:
            List of notifications
        """
        filtered = self._notifications

        if notification_type:
            filtered = [n for n in filtered if n['type'] == notification_type]

        if severity:
            filtered = [n for n in filtered if n['severity'] == severity]

        return filtered[-limit:]

    def clear_notifications(
        self,
        notification_type: Optional[str] = None,
        older_than_seconds: Optional[int] = None,
    ) -> int:
        """Clear notifications.

        Args:
            notification_type: Clear only specific type
            older_than_seconds: Clear only notifications older than this

        Returns:
            Number of notifications cleared
        """
        if not self._notifications:
            return 0

        cutoff_time = time.time() - (older_than_seconds or 0)

        if notification_type:
            original_count = len(self._notifications)
            self._notifications = [
                n
                for n in self._notifications
                if n['type'] != notification_type
                or (older_than_seconds and n['timestamp'] < cutoff_time)
            ]
            return original_count - len(self._notifications)
        elif older_than_seconds:
            original_count = len(self._notifications)
            self._notifications = [
                n for n in self._notifications if n['timestamp'] >= cutoff_time
            ]
            return original_count - len(self._notifications)
        else:
            count = len(self._notifications)
            self._notifications.clear()
            return count

    def add_comment(
        self,
        parent_run_id: str,
        request_id: str,
        comment: str,
        author: str,
    ) -> bool:
        """Add a comment to a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            comment: Comment text
            author: Comment author

        Returns:
            True if comment was added
        """
        if not self.config.enable_comments:
            return False

        try:
            self._ensure_comments()

            with self._lock:
                if request_id not in self._comments:
                    self._comments[request_id] = []

                self._comments[request_id].append(
                    {
                        'timestamp': time.time(),
                        'comment': comment,
                        'author': author,
                        'parent_run_id': parent_run_id,
                    }
                )

            self._create_notification(
                'comment_added',
                f'Comment added to request {request_id} by {author}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Comment added to request {request_id} by {author}')
            return True

        except Exception as e:
            logger.error(f'Failed to add comment to request {request_id}: {e}')
            return False

    def get_comments(self, request_id: str) -> list[dict[str, Any]]:
        """Get comments for a request.

        Args:
            request_id: Request ID

        Returns:
            List of comments
        """
        return self._comments.get(request_id, [])

    def delete_comment(self, request_id: str, comment_index: int) -> bool:
        """Delete a comment from a request.

        Args:
            request_id: Request ID
            comment_index: Index of comment to delete

        Returns:
            True if comment was deleted
        """
        if request_id in self._comments and 0 <= comment_index < len(
            self._comments[request_id]
        ):
            del self._comments[request_id][comment_index]
            logger.info(f'Deleted comment {comment_index} from request {request_id}')
            return True
        return False

    def cast_vote(
        self,
        parent_run_id: str,
        request_id: str,
        voter: str,
        vote: bool,  # True = approve, False = deny
    ) -> bool:
        """Cast a vote on a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            voter: Voter identifier
            vote: Vote (True=approve, False=deny)

        Returns:
            True if vote was cast
        """
        if not self.config.enable_voting:
            return False

        try:
            request = self.get_request(parent_run_id, request_id)
            if not request:
                logger.error(f'Request {request_id} not found for voting')
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(f'Cannot vote on non-pending request {request_id}')
                return False

            self._ensure_votes()

            with self._lock:
                if request_id not in self._votes:
                    self._votes[request_id] = {}

                self._votes[request_id][voter] = vote

            self._create_notification(
                'vote_cast',
                f'Vote cast by {voter} on request {request_id}: {"approve" if vote else "deny"}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(
                f'Vote cast by {voter} on request {request_id}: {"approve" if vote else "deny"}'
            )

            # Auto-approve if vote threshold reached (simple majority)
            vote_summary = self.get_vote_summary(request_id)
            if vote_summary.get('total_votes', 0) >= 2:  # Need at least 2 voters
                approve_count = vote_summary.get('approve_count', 0)
                total = vote_summary.get('total_votes', 0)
                if approve_count > total / 2:  # Majority approves
                    logger.info(
                        f'Auto-approving request {request_id} based on majority vote ({approve_count}/{total})'
                    )
                    self.update_request_status(
                        parent_run_id,
                        request_id,
                        ApprovalRequestStatus.APPROVED,
                        approved_by='auto-approval-vote',
                        reason=f'Auto-approved by majority vote ({approve_count}/{total})',
                    )

            return True

        except Exception as e:
            logger.error(f'Failed to cast vote on request {request_id}: {e}')
            return False

    def get_votes(self, request_id: str) -> dict[str, bool]:
        """Get votes for a request.

        Args:
            request_id: Request ID

        Returns:
            Dictionary of votes {voter: vote}
        """
        if self._votes is None:
            return {}
        return self._votes.get(request_id, {})

    def get_vote_summary(self, request_id: str) -> dict[str, Any]:
        """Get vote summary for a request.

        Args:
            request_id: Request ID

        Returns:
            Dictionary with vote summary
        """
        if self._votes is None:
            return {'total_votes': 0, 'approve_count': 0, 'deny_count': 0, 'votes': {}}

        votes = self._votes.get(request_id, {})
        approve_count = sum(1 for v in votes.values() if v)
        deny_count = sum(1 for v in votes.values() if not v)

        return {
            'total_votes': len(votes),
            'approve_count': approve_count,
            'deny_count': deny_count,
            'votes': votes,
        }

    def add_tag(self, parent_run_id: str, request_id: str, tag: str) -> bool:
        """Add a tag to a request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            tag: Tag to add

        Returns:
            True if tag was added
        """
        if not self.config.enable_tagging:
            return False

        try:
            if request_id not in self._request_tags:
                self._request_tags[request_id] = set()

            self._request_tags[request_id].add(tag)

            self._create_notification(
                'tag_added',
                f'Tag {tag} added to request {request_id}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Added tag {tag} to request {request_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to add tag to request {request_id}: {e}')
            return False

    def remove_tag(self, request_id: str, tag: str) -> bool:
        """Remove a tag from a request.

        Args:
            request_id: Request ID
            tag: Tag to remove

        Returns:
            True if tag was removed
        """
        if request_id in self._request_tags and tag in self._request_tags[request_id]:
            self._request_tags[request_id].remove(tag)
            logger.info(f'Removed tag {tag} from request {request_id}')
            return True
        return False

    def get_tags(self, request_id: str) -> set[str]:
        """Get tags for a request.

        Args:
            request_id: Request ID

        Returns:
            Set of tags
        """
        return self._request_tags.get(request_id, set())

    def search_by_tag(self, tag: str) -> list[str]:
        """Search for requests by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of request IDs with the tag
        """
        return [
            request_id for request_id, tags in self._request_tags.items() if tag in tags
        ]

    def send_reminder(
        self,
        parent_run_id: str,
        request_id: str,
        recipient: str,
    ) -> bool:
        """Send a reminder for a pending request.

        Args:
            parent_run_id: Parent run ID
            request_id: Request ID
            recipient: Recipient of the reminder

        Returns:
            True if reminder was sent
        """
        if not self.config.enable_reminders:
            return False

        try:
            request = self.get_request(parent_run_id, request_id)
            if not request:
                logger.error(f'Request {request_id} not found for reminder')
                return False

            if request.status != ApprovalRequestStatus.PENDING:
                logger.warning(
                    f'Cannot send reminder for non-pending request {request_id}'
                )
                return False

            if request_id not in self._reminders:
                self._reminders[request_id] = []

            self._reminders[request_id].append(time.time())

            self._create_notification(
                'reminder_sent',
                f'Reminder sent to {recipient} for request {request_id}',
                request_id=request_id,
                parent_run_id=parent_run_id,
                severity='info',
            )

            logger.info(f'Reminder sent to {recipient} for request {request_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to send reminder for request {request_id}: {e}')
            return False

    def get_reminders(self, request_id: str) -> list[float]:
        """Get reminder timestamps for a request.

        Args:
            request_id: Request ID

        Returns:
            List of reminder timestamps
        """
        return self._reminders.get(request_id, [])
