import asyncio
import os
from typing import Dict
import time

import numpy as np
import pytest
from docarray.array.document import DocumentArray
from docarray.document import Document
from jina import Executor, Flow, requests, Client

PORT_EXPOSE = 53171


class Indexer(Executor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._docs = DocumentArray()

    @requests(on='/index')
    def index(self, docs: DocumentArray, **kwargs):
        self._docs.extend(docs)

    @requests(on='/search')
    def process(self, docs: DocumentArray, parameters: Dict, **kwargs):
        limit = 2
        if parameters:
            limit = int(parameters.get('limit', 2))
        docs.match(self._docs, limit=limit)

    @requests(on='/foo')
    def foo(self, docs: DocumentArray, **kwargs):
        docs[0].text = 'foo'

    @requests(on='/bar')
    def bar(self, docs: DocumentArray, **kwargs):
        docs[0].text = 'bar'

    @requests(on='/target-exec')
    def target_exec(self, docs: DocumentArray, **kwargs):
        docs[0].text = 'Indexer'


class SlowExec(Executor):
    @requests(on='/slow')
    def foo(self, docs: DocumentArray, **kwargs):
        time.sleep(0.1)


class Encoder(Executor):
    @requests
    def embed(self, docs: DocumentArray, **kwargs):
        docs.embeddings = np.random.random([len(docs), 10]).astype(np.float32)

    @requests(on='/target-exec')
    def target_exec(self, docs: DocumentArray, **kwargs):
        docs[0].text = 'Encoder'


@pytest.fixture(scope="module", autouse=True)
def flow():
    f = (
        Flow(protocol='http', port_expose=PORT_EXPOSE)
        .add(uses=Encoder, name='Encoder')
        .add(uses=Indexer, name='Indexer')
        .add(uses=SlowExec)
    )
    with f:
        f.index(inputs=(Document(text=t.strip()) for t in open(__file__) if t.strip()))
        yield


def graphql_query(mutation):
    c = Client(port=PORT_EXPOSE, protocol='HTTP')
    return c.mutate(mutation=mutation)


async def async_graphql_query(mutation, filepath):
    c = Client(port=PORT_EXPOSE, protocol='HTTP', asyncio=True)
    with open(filepath, 'a+') as f:
        f.write('before\n')
    result = await c.mutate(mutation=mutation)
    with open(filepath, 'a') as f:
        f.write('after\n')
    return result


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
def test_id_only(req_type):
    response = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}) { 
                id 
            } 
        }
    '''
        % req_type
    )
    assert 'data' in response
    assert 'docs' in response['data']
    assert len(response['data']['docs']) == 1
    assert set(response['data']['docs'][0].keys()) == {'id'}


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
def test_asyncio(req_type, tmp_path):
    filepath = os.path.join(tmp_path, 'test.txt')
    q = (
        '''
            %s {
                docs(data: {text: "abcd"}, execEndpoint: "/slow") { 
                    id 
                } 
            }
        '''
        % req_type
    )

    async def cuncurrent_mutations():
        inputs = [async_graphql_query(q, filepath) for _ in range(3)]
        await asyncio.gather(*inputs)

    asyncio.run(cuncurrent_mutations())
    with open(filepath, 'r') as f:
        lines = f.readlines()
        assert lines[0] == 'before\n'
        assert lines[1] == 'before\n'
        assert lines[2] == 'before\n'
        assert lines[3] == 'after\n'
        assert lines[4] == 'after\n'
        assert lines[5] == 'after\n'


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
def test_data_list(req_type):
    texts = 'abcd', 'efgh', 'ijkl'
    response = graphql_query(
        '''
        %s {
            docs(data: [{text: "%s"}, {text: "%s"}, {text: "%s"}]) { 
                text
            } 
        }
    '''
        % (req_type, *texts)
    )
    assert 'data' in response
    assert 'docs' in response['data']
    assert len(response['data']['docs']) == 3
    assert response['data']['docs'][0]['text'] == texts[0]
    assert response['data']['docs'][1]['text'] == texts[1]
    assert response['data']['docs'][2]['text'] == texts[2]


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
def test_id_and_text(req_type):
    response = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}) { 
                id 
                text
            } 
        }
    '''
        % req_type
    )
    assert sorted(set(response['data']['docs'][0].keys())) == sorted({'id', 'text'})


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
def test_id_in_matches(req_type):
    response = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}) { 
                id 
                text
                matches {
                    id
                }
            } 
        }
    '''
        % req_type
    )
    assert sorted(set(response['data']['docs'][0].keys())) == sorted(
        {'id', 'text', 'matches'}
    )
    assert len(response['data']['docs'][0]['matches']) == 2
    for match in response['data']['docs'][0]['matches']:
        assert set(match.keys()) == {'id'}


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
def test_id_text_in_matches(req_type):
    response = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}) { 
                id 
                text
                matches {
                    id
                    text
                }
            } 
        }
    '''
        % req_type
    )
    assert sorted(set(response['data']['docs'][0].keys())) == sorted(
        {'id', 'text', 'matches'}
    )
    for match in response['data']['docs'][0]['matches']:
        assert sorted(set(match.keys())) == sorted({'id', 'text'})


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
def test_text_scores_in_matches(req_type):
    response = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}) { 
                id 
                text
                matches {
                    text
                    scores {
                        name
                        score {
                            value
                        }
                    }
                }
            } 
        }
    '''
        % req_type
    )
    assert sorted(set(response['data']['docs'][0].keys())) == sorted(
        {'id', 'text', 'matches'}
    )
    for match in response['data']['docs'][0]['matches']:
        assert sorted(set(match.keys())) == sorted({'text', 'scores'})
        assert match['scores'][0]['name'] == 'cosine'
        assert isinstance(match['scores'][0]['score']['value'], float)


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
@pytest.mark.skip('Something wrong with json syntax is python string. Works on browser')
def test_parameters(req_type):
    response = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}, parameters: "{\"limit\": 3}") {
                id
                text
                matches {
                    text
                }
            }
        }
    '''
        % req_type
    )
    assert sorted(set(response['data']['docs'][0].keys())) == sorted(
        {'id', 'text', 'matches'}
    )
    assert len(response['data']['docs'][0]['matches']) == 3


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
@pytest.mark.parametrize('endpoint', ['/foo', '/bar'])
def test_endpoints(req_type, endpoint):
    response_foo = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}, execEndpoint: "%s") { 
                text
            } 
        }
    '''
        % (req_type, endpoint)
    )

    assert 'data' in response_foo
    assert 'docs' in response_foo['data']
    assert 'text' in response_foo['data']['docs'][0]
    assert response_foo['data']['docs'][0]['text'] == endpoint[1:]


@pytest.mark.parametrize('req_type', ['mutation', 'query'])
@pytest.mark.parametrize('target', ['Indexer', 'Encoder'])
def test_target_exec(req_type, target):
    response_foo = graphql_query(
        '''
        %s {
            docs(data: {text: "abcd"}, targetExecutor: "%s", execEndpoint: "/target-exec") { 
                text
            } 
        }
    '''
        % (req_type, target)
    )

    assert 'data' in response_foo
    assert 'docs' in response_foo['data']
    assert 'text' in response_foo['data']['docs'][0]
    assert response_foo['data']['docs'][0]['text'] == target
