from app.ingest.text_ingest import html_to_text


def test_strips_escaped_html():
    raw = ("&lt;h2&gt;About the role&lt;/h2&gt;&lt;p&gt;You&amp;#39;ll build "
           "&lt;strong&gt;crawlers&lt;/strong&gt;.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Rust&lt;/li&gt;"
           "&lt;li&gt;Postgres &amp;amp; SQL&lt;/li&gt;&lt;/ul&gt;")
    assert html_to_text(raw) == "About the role\n\nYou'll build crawlers.\n\n• Rust\n• Postgres & SQL"


def test_drops_scripts():
    assert html_to_text("<div><p>Keep me</p><script>track()</script></div>") == "Keep me"


def test_plain_html():
    assert html_to_text("<p>Build.</p>") == "Build."