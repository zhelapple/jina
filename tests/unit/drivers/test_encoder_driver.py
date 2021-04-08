from typing import Any

import numpy as np
import pytest

from jina import Document, DocumentSet
from jina.drivers.encode import EncodeDriver
from jina.executors.encoders import BaseEncoder
from jina.executors.decorators import batching, single


@pytest.fixture(scope='function')
def num_docs():
    return 10


@pytest.fixture(scope='function')
def docs_to_encode(num_docs):
    docs = []
    for idx in range(num_docs):
        doc = Document(content=np.array([idx]))
        docs.append(doc)
    return DocumentSet(docs)


def get_encoder(batch_size):
    class MockEncoder(BaseEncoder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        @batching(batch_size=batch_size)
        def encode(self, data: Any, *args, **kwargs) -> Any:
            if batch_size is not None and batch_size > 0:
                assert len(data) <= batch_size
            if batch_size == 5:
                assert len(data) == 5
            return data

    return MockEncoder()


class SimpleEncoderDriver(EncodeDriver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def exec_fn(self):
        return self._exec_fn


@pytest.mark.parametrize(
    'batch_size', [None, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 20, 100, 10000]
)
def test_encode_driver(batch_size, docs_to_encode, num_docs):
    driver = SimpleEncoderDriver()
    executor = get_encoder(batch_size)
    driver.attach(executor=executor, runtime=None)
    assert len(docs_to_encode) == num_docs
    for doc in docs_to_encode:
        assert doc.embedding is None
    driver._apply_all(docs_to_encode)
    assert len(docs_to_encode) == num_docs
    for doc in docs_to_encode:
        assert doc.embedding == doc.blob


@pytest.fixture
def row():
    return np.array([0, 0, 1, 2, 2, 2])


@pytest.fixture
def column():
    return np.array([0, 2, 2, 0, 1, 2])


@pytest.fixture
def data():
    return np.array([1, 2, 3, 4, 5, 6])


def scipy_sparse_list():
    from scipy.sparse import coo_matrix, bsr_matrix, csr_matrix, csc_matrix

    return [coo_matrix, bsr_matrix, csr_matrix, csc_matrix]


@pytest.fixture(params=scipy_sparse_list())
def scipy_sparse_matrix(request, row, column, data):
    matrix_type = request.param
    return matrix_type((data, (row, column)), shape=(4, 10))


# @pytest.fixture
# def tf_sparse_matrix(row, column, data):
#     import tensorflow as tf
#
#     indices = [(x, y) for x, y in zip(row, column)]
#     return tf.SparseTensor(indices=indices, values=data, dense_shape=[4, 10])


def get_sparse_vector(sparse_type):
    row = np.array([0, 0, 1, 2, 2, 2])
    column = np.array([0, 2, 2, 0, 1, 2])
    data = np.array([1, 2, 3, 4, 5, 6])

    if sparse_type == 'scipy_coo':
        from scipy.sparse import coo_matrix

        return coo_matrix((data, (row, column)), shape=(4, 10))
    elif sparse_type == 'scipy_bsr':
        from scipy.sparse import bsr_matrix

        return bsr_matrix((data, (row, column)), shape=(4, 10))
    elif sparse_type == 'scipy_csr':
        from scipy.sparse import csr_matrix

        return csr_matrix((data, (row, column)), shape=(4, 10))
    elif sparse_type == 'scipy_csc':
        from scipy.sparse import csc_matrix

        return csc_matrix((data, (row, column)), shape=(4, 10))
    elif sparse_type == 'tf':
        import tensorflow as tf

        indices = [(x, y) for x, y in zip(row, column)]
        return tf.SparseTensor(indices=indices, values=data, dense_shape=[4, 10])
    elif sparse_type == 'torch':
        import torch

        shape = [4, 10]
        indices = [list(row), list(column)]
        return torch.sparse_coo_tensor(indices, data, shape)


def get_sparse_encoder(sparse_type):
    class MockEncoder(BaseEncoder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        @batching
        def encode(self, data: Any, *args, **kwargs) -> Any:
            return get_sparse_vector(sparse_type)

    return MockEncoder()


@pytest.mark.parametrize(
    'sparse_type', ['scipy_coo', 'scipy_bsr', 'scipy_csr', 'scipy_csc', 'tf', 'torch']
)
def test_encode_sparse_driver(sparse_type, docs_to_encode, num_docs):
    driver = SimpleEncoderDriver()
    executor = get_sparse_encoder(sparse_type)
    driver.attach(executor=executor, runtime=None)
    assert len(docs_to_encode) == num_docs
    for doc in docs_to_encode:
        assert doc.embedding is None
    driver._apply_all(docs_to_encode)
    assert len(docs_to_encode) == num_docs
    for doc in docs_to_encode:
        print(f' embed {doc.embedding}')
