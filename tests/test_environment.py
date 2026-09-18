import crewai


def test_crewai_version_is_pinned():
    assert crewai.__version__ == "1.15.22"
