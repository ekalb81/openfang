import pathlib
import unittest


class ApprovalApiRecentHistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        cls.source = (repo_root / 'crates' / 'openfang-api' / 'src' / 'routes.rs').read_text()

    def test_list_approvals_includes_recent_history(self):
        self.assertIn('let recent = state.kernel.approval_manager.list_recent(50);', self.source)
        self.assertIn('approvals.extend(recent.into_iter().map(|record| {', self.source)

    def test_recent_history_status_mapping_covers_all_decisions(self):
        self.assertIn('ApprovalDecision::Approved => "approved"', self.source)
        self.assertIn('ApprovalDecision::Denied => "rejected"', self.source)
        self.assertIn('ApprovalDecision::TimedOut => "expired"', self.source)

    def test_recent_history_exposes_decision_metadata(self):
        self.assertIn('"decided_at": record.decided_at,', self.source)
        self.assertIn('"decided_by": record.decided_by,', self.source)

    def test_approvals_are_sorted_pending_first_then_newest(self):
        self.assertIn('let a_pending = a["status"].as_str() == Some("pending");', self.source)
        self.assertIn('let b_pending = b["status"].as_str() == Some("pending");', self.source)
        self.assertIn('.then_with(|| b["created_at"].as_str().cmp(&a["created_at"].as_str()))', self.source)


if __name__ == '__main__':
    unittest.main()
