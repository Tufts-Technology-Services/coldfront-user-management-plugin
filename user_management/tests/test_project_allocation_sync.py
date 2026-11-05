"""Each user activation on an allocation is signalled once, so whatever reacts to it runs once.

Allocation.add_user() signals allocation_activate_user even for a user already Active, when nothing
changes. ColdFront's own views signal when they activate a user, so this plugin adding the same user
again signalled twice: on production that ran the storage plugin's folder creation twice for every
new allocation and every new project member.
"""

from unittest.mock import call, patch

from coldfront.core.allocation.models import Allocation
from coldfront.core.allocation.signals import allocation_activate_user, allocation_remove_user
from coldfront.core.test_helpers.factories import (
    AllocationFactory,
    AllocationStatusChoiceFactory,
    AllocationUserFactory,
    AllocationUserStatusChoiceFactory,
    ProjectFactory,
    ProjectUserFactory,
)
from django.test import TestCase

from user_management.signals import init_signal_receivers
from user_management.tasks import add_project_user_to_allocations, sync_project_users_to_allocations


def allocations_added_to(mock_add_user):
    """The pks of the allocations Allocation.add_user() was called on, in order."""
    return [c.args[0].pk for c in mock_add_user.call_args_list]


@patch.object(Allocation, "add_user", autospec=True)
class AddProjectUserToAllocationsTests(TestCase):
    def setUp(self):
        self.project = ProjectFactory()
        self.project_user = ProjectUserFactory(project=self.project)
        self.user = self.project_user.user
        self.first = AllocationFactory(project=self.project)
        self.second = AllocationFactory(project=self.project)

    def test_the_user_is_added_to_each_active_allocation(self, mock_add_user):
        AllocationFactory(project=self.project, status=AllocationStatusChoiceFactory(name="New"))

        add_project_user_to_allocations(self.project_user.pk)

        self.assertEqual(allocations_added_to(mock_add_user), [self.first.pk, self.second.pk])

    def test_an_allocation_the_user_is_already_active_on_is_skipped(self, mock_add_user):
        AllocationUserFactory(allocation=self.first, user=self.user)

        result = add_project_user_to_allocations(self.project_user.pk)

        self.assertEqual(allocations_added_to(mock_add_user), [self.second.pk])
        self.assertEqual(
            result["message"],
            f"Added {self.user.username} to allocations [{self.second.pk}]; already active on [{self.first.pk}].",
        )

    def test_a_user_removed_from_an_allocation_is_added_again(self, mock_add_user):
        AllocationUserFactory(
            allocation=self.first, user=self.user, status=AllocationUserStatusChoiceFactory(name="Removed")
        )

        add_project_user_to_allocations(self.project_user.pk)

        self.assertEqual(allocations_added_to(mock_add_user), [self.first.pk, self.second.pk])

    def test_it_can_be_kept_to_some_of_the_allocations(self, mock_add_user):
        add_project_user_to_allocations(self.project_user.pk, allocation_pks=[self.second.pk])

        self.assertEqual(allocations_added_to(mock_add_user), [self.second.pk])

    def test_the_sync_adds_users_only_to_the_allocation_that_was_activated(self, mock_add_user):
        """Approving one allocation used to re-add every member to every active allocation."""
        other_member = ProjectUserFactory(project=self.project)

        sync_project_users_to_allocations(self.second.pk)

        self.assertEqual(allocations_added_to(mock_add_user), [self.second.pk, self.second.pk])
        added_users = {c.args[1] for c in mock_add_user.call_args_list}
        self.assertEqual(added_users, {self.user, other_member.user})

    def test_the_sync_skips_users_already_on_the_allocation(self, mock_add_user):
        """ColdFront's approval view has already signalled for them."""
        AllocationUserFactory(allocation=self.first, user=self.user)

        sync_project_users_to_allocations(self.first.pk)

        mock_add_user.assert_not_called()


class SignalledOnceTests(TestCase):
    """With ColdFront's real Allocation.add_user(), counting what it signals."""

    def setUp(self):
        # add_user() looks the status up by name; a real database has it from add_allocation_defaults
        AllocationUserStatusChoiceFactory(name="Active")
        self.project = ProjectFactory()
        self.project_user = ProjectUserFactory(project=self.project)
        self.allocation = AllocationFactory(project=self.project)
        self.activated = []
        allocation_activate_user.connect(self.record_activation, dispatch_uid="test-record-activation")

    def tearDown(self):
        allocation_activate_user.disconnect(dispatch_uid="test-record-activation")

    def record_activation(self, sender, allocation_user_pk, **kwargs):
        self.activated.append(allocation_user_pk)

    def test_a_user_already_active_is_not_signalled_again(self):
        AllocationUserFactory(allocation=self.allocation, user=self.project_user.user)

        sync_project_users_to_allocations(self.allocation.pk)

        self.assertEqual(self.activated, [])

    def test_a_user_new_to_the_allocation_is_signalled_once(self):
        sync_project_users_to_allocations(self.allocation.pk)

        allocation_user = self.allocation.allocationuser_set.get(user=self.project_user.user)
        self.assertEqual(self.activated, [allocation_user.pk])


class AllocationLevelReceiverTests(TestCase):
    """Allocation-level mode connected each receiver under two or three dispatch_uids."""

    def tearDown(self):
        allocation_activate_user.disconnect(dispatch_uid="ump_activate_allocation_user_1")
        allocation_remove_user.disconnect(dispatch_uid="ump_remove_allocation_user_1")

    @patch("user_management.signals.async_task")
    def test_each_activation_and_removal_queues_its_group_task_once(self, mock_async_task):
        init_signal_receivers(project_level=False)
        # connecting again, as a second ready() would, mustn't add receivers either
        init_signal_receivers(project_level=False)

        allocation_activate_user.send(sender=None, allocation_user_pk=7)
        allocation_remove_user.send(sender=None, allocation_user_pk=7)

        self.assertEqual(
            mock_async_task.call_args_list,
            [
                call("user_management.tasks.add_allocation_user_to_group", 7),
                call("user_management.tasks.remove_allocation_user_from_group", 7),
            ],
        )
