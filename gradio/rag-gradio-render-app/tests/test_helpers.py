from rag_engine import rrf, split_text, truncate_tokens

def test_rrf_combines_rankings():
    assert rrf([[1, 2], [2, 3]], 3)[0] == 2

def test_chunking():
    chunks = split_text('First sentence. Second sentence. Third sentence.', 28, 5)
    assert chunks
    assert all(len(x) <= 28 for x in chunks)

def test_truncate():
    assert truncate_tokens('你好世界' * 20, 8) != '你好世界' * 20
