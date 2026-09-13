from demail.domain.selection import SelectionCriteria
from demail.gmail.client import GmailLabel, GmailMessageMetadata, SelectionResult
from demail.ui.selection import SelectionController


class ImmediatePool:
    def start(self, task) -> None:
        task.run()


class Service:
    def labels(self):
        return (GmailLabel("INBOX", "Inbox", "system"),)

    def exact_selection(self, criteria):
        return SelectionResult(())

    def resolve_selection(self, criteria):
        return self.exact_selection(criteria)

    def recent_messages(self, criteria, limit=100):
        return (GmailMessageMetadata("a", None, None, "Subject", "From", ()),)


def test_controller_delivers_background_selection_results(qtbot) -> None:
    controller = SelectionController(Service, ImmediatePool())
    with qtbot.waitSignal(controller.labels_loaded) as labels:
        controller.load_labels()
    assert labels.args[0][0].id == "INBOX"

    criteria = SelectionCriteria(search_query="has:attachment")
    with qtbot.waitSignal(controller.candidates_loaded) as candidates:
        controller.load_candidates(criteria)
    assert candidates.args[0][0].id == "a"

    with qtbot.waitSignal(controller.exact_count_loaded) as count:
        controller.calculate_exact_count(criteria)
    assert count.args[0] == (criteria, 0)

    with qtbot.waitSignal(controller.eras_loaded) as eras:
        controller.scan_eras(False)
    assert eras.args[0] == ()


def test_controller_sanitizes_service_failures(qtbot) -> None:
    class BrokenService(Service):
        def labels(self):
            raise RuntimeError("private@example.com secret-token")

    controller = SelectionController(BrokenService, ImmediatePool())
    with qtbot.waitSignal(controller.failed) as failure:
        controller.load_labels()
    assert failure.args[0] == "labels"
    assert "private@example.com" not in failure.args[1]
