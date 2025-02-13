from jina import Flow
from jina import Document, Executor, Client, requests

exposed_port = 12345


def validate_results(results):
    req = results[0]
    assert len(req.docs) == 1
    assert len(req.docs[0].matches) == 5
    assert len(req.docs[0].matches[0].matches) == 5
    assert len(req.docs[0].matches[-1].matches) == 5
    assert len(req.docs[0].matches[0].matches[0].matches) == 0


class MatchAdder(Executor):
    def __init__(self, traversal_paths='r', **kwargs):
        super().__init__(**kwargs)
        self._traversal_paths = traversal_paths

    @requests(on='index')
    def index(self, docs, **kwargs):
        for path_docs in docs.traverse(self._traversal_paths):
            for doc in path_docs:
                for i in range(5):
                    doc.matches.append(Document())


def test_single_executor():

    f = Flow(port_expose=exposed_port).add(
        uses={'jtype': 'MatchAdder', 'with': {'traversal_paths': 'r,m'}}
    )

    with f:
        results = Client(port=exposed_port, return_responses=True).post(
            on='index',
            inputs=Document(),
        )
    validate_results(results)


def test_multi_executor():

    f = (
        Flow(port_expose=exposed_port)
        .add(uses={'jtype': 'MatchAdder', 'with': {'traversal_paths': 'r'}})
        .add(uses={'jtype': 'MatchAdder', 'with': {'traversal_paths': 'm'}})
    )

    with f:
        results = Client(port=exposed_port, return_responses=True).post(
            on='index',
            inputs=Document(),
        )
    validate_results(results)
