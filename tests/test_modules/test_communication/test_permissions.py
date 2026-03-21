from grove.core.events import Member
from grove.modules.communication.permissions import check_permission, Action


class TestPermissions:
    def _member(self, authority: str) -> Member:
        return Member(name="Test", github="test", lark_id="ou_test", role="backend", authority=authority)

    def test_member_can_query_progress(self):
        assert check_permission(self._member("member"), Action.QUERY_PROGRESS) is True

    def test_member_can_propose_idea(self):
        assert check_permission(self._member("member"), Action.PROPOSE_IDEA) is True

    def test_member_cannot_modify_config(self):
        assert check_permission(self._member("member"), Action.MODIFY_CONFIG) is False

    def test_member_cannot_approve_change(self):
        assert check_permission(self._member("member"), Action.APPROVE_CHANGE) is False

    def test_lead_can_approve_change(self):
        assert check_permission(self._member("lead"), Action.APPROVE_CHANGE) is True

    def test_lead_cannot_modify_config(self):
        assert check_permission(self._member("lead"), Action.MODIFY_CONFIG) is False

    def test_owner_can_modify_config(self):
        assert check_permission(self._member("owner"), Action.MODIFY_CONFIG) is True

    def test_owner_can_do_everything(self):
        for action in Action:
            assert check_permission(self._member("owner"), action) is True
