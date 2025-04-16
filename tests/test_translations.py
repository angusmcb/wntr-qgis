from pathlib import Path

import pytest
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QTranslator

from wntrqgis.i18n import tr


def translator(locale):
    qgis_locale = QLocale(locale)
    locale_path = str(Path(__file__).parent.parent / "wntrqgis" / "resources" / "i18n")
    translator = QTranslator()
    translator.load(qgis_locale, "", "", locale_path)
    return translator


@pytest.fixture
def translator_en():
    return translator("en")


@pytest.mark.parametrize(
    ("num_hours", "expected_message"),
    [
        (1, "1 hour"),
        (2, "2 hours"),
    ],
)
def test_numerus_translation_hours(num_hours, expected_message, translator_en):
    QCoreApplication.installTranslator(translator_en)

    translated_message = tr("%n hour(s)", "", num_hours)
    assert translated_message == expected_message


@pytest.mark.parametrize(
    ("num_features", "expected_message"),
    [
        (1, "in nodes, 1 feature has no geometry"),
        (2, "in nodes, 2 features have no geometry"),
    ],
)
def test_numerus_translation_nodes(num_features, expected_message, translator_en):
    QCoreApplication.installTranslator(translator_en)

    translated_message = tr("in nodes, %n feature(s) have no geometry", "", num_features)
    assert translated_message == expected_message


@pytest.mark.parametrize(
    ("num_features", "expected_message"),
    [
        (1, "in links, 1 feature has no geometry"),
        (2, "in links, 2 features have no geometry"),
    ],
)
def test_numerus_translation_links(num_features, expected_message, translator_en):
    QCoreApplication.installTranslator(translator_en)

    translated_message = tr("in links, %n feature(s) have no geometry", "", num_features)

    assert translated_message == expected_message


@pytest.mark.parametrize(
    ("num_pipes", "expected_message"),
    [
        (1, "1 pipe has very different attribute length vs measured length. First five are: "),
        (2, "2 pipes have very different attribute length vs measured length. First five are: "),
    ],
)
def test_numerus_translation_pipes(num_pipes, expected_message, translator_en):
    QCoreApplication.installTranslator(translator_en)

    translated_message = tr(
        "%n pipe(s) have very different attribute length vs measured length. First five are: ",
        "",
        num_pipes,
    )

    assert translated_message == expected_message


@pytest.mark.parametrize(
    ("locale", "expected_message"),
    [
        ("en", "Run Simulation"),
        ("es", "Ejecutar simulación"),
        ("fr", "Exécuter la simulation"),
        ("de", "Simulation ausführen"),
        ("it", "Esegui simulazione"),
        ("pt", "Executar Simulação"),
        ("ar", "تشغيل المحاكاة"),
    ],
)
def test_run_simulation_translation(locale, expected_message):
    t = translator(locale)
    QCoreApplication.installTranslator(t)

    translated_message = tr("Run Simulation")

    assert translated_message == expected_message
