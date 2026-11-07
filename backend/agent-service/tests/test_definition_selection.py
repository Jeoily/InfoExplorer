"""Offline regressions for definition subjects competing with incidental mentions."""
from app.web_research.selection import Document, select_passages


def test_sparse_generic_words_do_not_pad_evidence_with_unrelated_document():
    question=' '.join('subject'+str(i) for i in range(30))
    relevant=Document('good','example.org','Relevant',(question,))
    irrelevant=Document('bad','other.org','Portal',('subject1 portal navigation and unrelated news',))
    assert {p.source_id for p in select_passages([relevant,irrelevant],{'Q1':question})}=={'good'}


def test_translated_aliases_do_not_dilute_relevant_english_passage():
    questions={'Q1':'是否自己抓取网页建立索引，需要官方说明解释架构中的资料来源和查询机制。 '
                   'ExampleTool meta search engine result aggregation'}
    docs=[Document('s','example.org','About ExampleTool',(
        'About ExampleTool — ExampleTool is a metasearch engine aggregating results from other search services.',))]
    assert select_passages(docs,questions)[0].source_id=='s'


def test_nearest_sections_cover_three_subjects_without_ancestor_contamination():
    root = '前端、后端与数据库的学习建议'
    paragraphs = (
        root + ' / 学习路径 — 前端后端数据库的学习通常需要持续练习。',
        root + ' / 什么是前端？ — 展示界面并接收用户输入。',
        root + ' / 什么是后端？ — 处理业务逻辑并返回结果。',
        root + ' / 数据库的角色 — 保存和读取应用数据。',
        root + ' / 常用工具 — 前端后端数据库工具包含许多框架。',
    )
    questions = {'Q1':'前端通常负责哪些工作？', 'Q2':'后端通常负责哪些工作？',
                 'Q3':'数据库的作用是什么？'}
    doc = Document('s', 'example.org', root, paragraphs)
    selected = select_passages([doc], questions, per_source=4)
    assert {1,2,3} <= {p.paragraph_index for p in selected}
    assert len(selected) == 4
    assert len(select_passages([doc], questions)) == 2


def test_definition_subjects_survive_a_method_matching_both_questions():
    paragraphs = (
        'Network API / PlainChannel.send(data) — PlainChannel and SecureChannel '
        'both send data. Python network clients support buffers and headers.',
        'Network API / class api.PlainChannel(host) — A connection to a network host.',
        'Network API / class api.SecureChannel(host) — A connection protected by TLS.',
    )
    result = select_passages([Document('s', 'example.org', 'Network API', paragraphs)], {
        'Q1': 'What is PlainChannel in the Python network API?',
        'Q2': 'What is SecureChannel in the Python network API?',
    })
    assert {p.paragraph_index for p in result} == {1, 2}


def test_body_declaration_does_not_masquerade_as_the_structural_subject():
    paragraphs = (
        'API / class Other(host) — class SecureChannel(host) is mentioned here.',
        'API / class SecureChannel(host) — A TLS connection.',
    )
    result = select_passages([Document('s', 'example.org', 'API', paragraphs)],
                             {'Q1': 'What is SecureChannel?'}, max_evidence=1)
    assert result[0].paragraph_index == 1


def test_usage_question_does_not_get_a_definition_bonus():
    paragraphs = (
        'API / class SecureChannel(host) — Creates a connection.',
        'API / SecureChannel.send(data) — SecureChannel can send streaming data.',
    )
    result = select_passages([Document('s', 'example.org', 'API', paragraphs)],
                             {'Q1': 'How does SecureChannel send streaming data?'}, max_evidence=1)
    assert result[0].paragraph_index == 1


def test_chinese_definition_question_and_normalized_identifier():
    paragraphs = (
        'API / Other.send() — SecureChannel 是什么？',
        'API / class SecureChannel(host) — 加密连接。',
    )
    result = select_passages([Document('s', 'example.org', 'API', paragraphs)],
                             {' Q1 ': 'SecureChannel 是什么？'}, max_evidence=1)
    assert result[0].paragraph_index == 1
    assert result[0].matched_question_ids == ('Q1',)


def test_other_source_does_not_saturate_this_documents_definition_coverage():
    old = Document('old', 'example.org', 'Legacy API', (
        'API / class SecureChannel(host) — SecureChannel purpose TLS network security.',))
    current = Document('new', 'example.org', 'Current API', (
        'API / class PlainChannel(host) — PlainChannel purpose network connection.',
        'API — Python network purpose security connection overview.',
        'API / class SecureChannel(host) — SecureChannel purpose TLS connection.',))
    result = select_passages([old, current], {
        'Q1': 'What is the purpose of PlainChannel in the Python network API?',
        'Q2': 'What is the purpose of SecureChannel in the Python network API?',
    })
    assert {p.paragraph_index for p in result if p.source_id == 'new'} == {0, 2}


def test_compound_question_preserves_each_subject_in_direct_fallback():
    paragraphs = (
        'API / class PlainChannel(host) — PlainChannel is a connection.',
        'API / PlainChannel.send(data) — PlainChannel and SecureChannel support API networking.',
        'API / class SecureChannel(host) — SecureChannel uses TLS.',
    )
    result = select_passages([Document('s', 'example.org', 'API', paragraphs)],
        {'Q1': 'What are PlainChannel and SecureChannel in the networking API?'})
    assert {p.paragraph_index for p in result} == {0, 2}


def test_chinese_section_headings_beat_an_aside_with_the_same_keywords():
    paragraphs = (
        '个人经历 — 前端开发使用 HTML 和 CSS，后端开发使用数据库和 API。后来转行了。',
        '前端开发 — 使用 HTML 和 CSS 构建页面。',
        '后端开发 — 通过 API 处理数据库请求。',
    )
    selected = select_passages([Document('s', 'example.org', '开发', paragraphs)],
                              {'Q1': '前端开发 HTML CSS', 'Q2': '后端开发 数据库 API'})
    assert {e.paragraph_index for e in selected} == {1, 2}


def test_comparison_keeps_both_current_definitions_despite_legacy_coverage():
    old = Document('old', 'legacy.example.org', 'API', (
        'API / class PlainChannel(host) — PlainChannel provides a client connection.',))
    current = Document('current', 'example.org', 'API', (
        'API / class PlainChannel(host) — PlainChannel provides a current client connection.',
        'API / class SecureChannel(host) — SecureChannel uses encryption.',
        'API / Examples — PlainChannel and SecureChannel usage comparison: '
        'connections provide client requests and server responses.',))
    result = select_passages([old, current], {
        'Q1': 'What are PlainChannel and SecureChannel in the client API?',
        'Q2': 'What is the key difference between PlainChannel and SecureChannel connections?',
    })
    assert {p.paragraph_index for p in result if p.source_id == 'current'} == {0, 1}
