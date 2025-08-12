from pathlib import Path

import pytest
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QTranslator

from gusnet.i18n import tr


@pytest.fixture
def locale():
    return "en"


@pytest.fixture
def translator(locale):
    qgis_locale = QLocale(locale)
    locale_path = str(Path(__file__).parent.parent / "gusnet" / "resources" / "i18n")
    translator = QTranslator()
    translator.load(qgis_locale, "", "", locale_path)
    QCoreApplication.installTranslator(translator)
    yield
    QCoreApplication.removeTranslator(translator)  # not strictly needed


@pytest.mark.parametrize(
    ("num_hours", "expected_message"),
    [
        (1, "1 hour"),
        (2, "2 hours"),
    ],
)
def test_numerus_translation_hours(num_hours, expected_message, translator):
    translated_message = tr("%n hour(s)", "", num_hours)

    assert translated_message == expected_message


@pytest.mark.parametrize(
    ("num_features", "expected_message"),
    [
        (1, "1 hour"),
        (2, "2 hours"),
    ],
)
def test_numerus_translation(num_features, expected_message, translator):
    translated_message = tr("%n hour(s)", "", num_features)

    assert translated_message == expected_message


@pytest.mark.parametrize(
    ("num_pipes", "expected_message"),
    [
        (1, "1 pipe has very different attribute length vs measured length. First five are: "),
        (2, "2 pipes have very different attribute length vs measured length. First five are: "),
    ],
)
def test_numerus_translation_pipes(num_pipes, expected_message, translator):
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
def test_run_simulation_translation(translator, expected_message):
    translated_message = tr("Run Simulation")

    assert translated_message == expected_message
