"""Path handling in load_report_template."""
import anakrisis


def test_default_template_resolves():
    text = anakrisis.load_report_template("general_investigation", "internal")
    assert "Template not found" not in text
    assert text.strip(), "default.md should resolve for any sane inputs"


def test_traversal_components_are_rejected(tmp_path, monkeypatch):
    # Plant a file outside the templates dir and try to reach it with a
    # traversal component; the loader must fall through to default.md.
    templates = tmp_path / "report_templates"
    templates.mkdir()
    (templates / "default.md").write_text("DEFAULT", encoding="utf-8")
    (tmp_path / "SECRET_internal.md").write_text("SECRET", encoding="utf-8")

    monkeypatch.setattr(anakrisis, "REPORT_TEMPLATES_DIR", templates)

    text = anakrisis.load_report_template("../SECRET", "internal")
    assert "SECRET" not in text
    assert text == "DEFAULT"


def test_traversal_in_audience_is_rejected(tmp_path, monkeypatch):
    templates = tmp_path / "report_templates"
    templates.mkdir()
    (templates / "default.md").write_text("DEFAULT", encoding="utf-8")
    (tmp_path / "leak.md").write_text("SECRET", encoding="utf-8")

    monkeypatch.setattr(anakrisis, "REPORT_TEMPLATES_DIR", templates)

    text = anakrisis.load_report_template("generic", "../leak")
    assert "SECRET" not in text
    assert text == "DEFAULT"


def test_valid_specific_template_still_wins(tmp_path, monkeypatch):
    templates = tmp_path / "report_templates"
    templates.mkdir()
    (templates / "default.md").write_text("DEFAULT", encoding="utf-8")
    (templates / "fraud_investigation_client.md").write_text("SPECIFIC", encoding="utf-8")

    monkeypatch.setattr(anakrisis, "REPORT_TEMPLATES_DIR", templates)

    assert anakrisis.load_report_template("fraud_investigation", "client") == "SPECIFIC"
