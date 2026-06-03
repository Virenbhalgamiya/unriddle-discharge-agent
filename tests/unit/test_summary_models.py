from app.models.summary_models import SectionStatus, section_content_or_literal


def test_pending_section_shows_description():
    content = section_content_or_literal(
        SectionStatus.PENDING,
        ["Culture pending"],
    )
    assert "Culture pending" in content
    assert "PENDING" in content
