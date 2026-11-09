from pathlib import Path

import pytest
from game_gamer.tui import i18n
from test_matrix_navigation import app

from commons_game.i18n import browser_messages, t
from commons_game.server import render_page
from commons_game.validate_text import _files, audit

ROOT = Path(__file__).resolve().parents[1]


def test_language_fallback_and_named_interpolation(monkeypatch):
    monkeypatch.setenv('SADDLE_LANGUAGE', 'en')
    assert t('matrix.score.unknown_lower_bound', lower=1, upper=3) == 'Unknown (1–3; lower bound 1)'
    with pytest.raises(KeyError, match='upper'):
        t('matrix.score.unknown_lower_bound', lower=1)
    with pytest.raises(KeyError, match='unregistered'):
        t('unregistered')
    with i18n.using_language('fr_CA'):
        assert t('navigation.montreal_network.title') == 'RÉSEAU MONTRÉALAIS'
        assert t('controls.back') == 'Retour'
        assert t('matrix.score.unknown_lower_bound', lower=1, upper=3) == 'Unknown (1–3; lower bound 1)'
        with i18n.using_language('de'):
            assert t('controls.back') == 'Back'
        assert t('controls.back') == 'Retour'
    assert t('controls.back') == 'Back'



def test_duplicate_catalogue_keys_are_rejected(tmp_path):
    catalogue = tmp_path / 'en.yaml'
    catalogue.write_text('menu:\n  title: Paths\n  title: Modes\n', encoding='utf-8')
    with pytest.raises(ValueError, match="duplicate catalogue key 'title'"):
        i18n.read_catalogue(catalogue)


def test_one_yaml_edit_updates_montreal_picker_and_screen_without_world_writes(tmp_path, monkeypatch):
    locales = tmp_path / 'locales'
    locales.mkdir()
    original = ROOT / 'commons_game/locales/en.yaml'
    (locales / 'en.yaml').write_text(
        original.read_text(encoding='utf-8').replace('MONTRÉAL NETWORK', 'MONTRÉAL LINKS'),
        encoding='utf-8',
    )
    original_files = i18n.files
    monkeypatch.setattr(i18n, 'files', lambda package: tmp_path if package == 'commons_game' else original_files(package))
    i18n.load_catalogue.cache_clear()
    i18n.messages.cache_clear()
    try:
        with i18n.using_language('en'):
            ui, viewport = app(choices=[4])
            before = ui.game.get_world(), ui.game.project('log')
            ui.choose_mode()
            assert any(label.startswith('MONTRÉAL LINKS · ') for label in viewport.drawn[-1][1])
            assert ui.build_screen().title == 'MONTRÉAL LINKS'
            assert (ui.game.get_world(), ui.game.project('log')) == before
    finally:
        i18n.load_catalogue.cache_clear()
        i18n.messages.cache_clear()


def test_french_invitation_label_keeps_the_draft_action_and_original_contribution():
    ui, viewport = app(answers=['Échangeons sur les données.', 'Comparer nos notes.', 'y'], choices=[1])
    recipient = next(key for key in ui.world()['actors'] if key != ui.playing_actor)
    with i18n.using_language('fr'):
        ui.contact_to(recipient)
    delivery = next(labels for title, labels, _ in viewport.drawn if title == 'ENVOI DE L’INVITATION')
    assert delivery == ['Envoyer maintenant', 'Enregistrer le brouillon']
    records = list(ui.world()['relationships'].values())
    draft = next(record for record in records if record.get('status') == 'draft')
    assert draft['message'] == 'Échangeons sur les données.'
    assert draft['purpose'] == 'Comparer nos notes.'


def test_browser_uses_the_same_catalogue_and_falls_back():
    page = render_page('fr-CA')
    assert '<html lang="fr-ca">' in page
    assert 'Entrer sans son' in page
    assert 'Begin the experiment' in page
    assert 'A commons of knowledge' in page
    assert '{{' not in page
    messages = browser_messages('fr-CA')
    assert messages['web.audio.off'] == 'Sound off ♫'
    assert messages['web.connection.shared_world_commit'] == 'MONDE PARTAGÉ / TRANSACTION {value}'


def test_catalogue_source_audit_passes_and_detects_regressions(tmp_path):
    problems, count, translations = audit(ROOT)
    assert not problems, '\n'.join(problems)
    assert 0 < translations['fr'] < count

    catalogues = [path.relative_to(ROOT) for path in ROOT.glob('commons_game/locales/*')]
    catalogues += [path.relative_to(ROOT) for path in ROOT.glob('game-gamer/src/game_gamer/tui/locales/*')]
    for path in [*_files(ROOT), *catalogues]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / path).read_bytes())
    source = tmp_path / 'commons_game/play.py'
    with source.open('a', encoding='utf-8') as file:
        file.write("\n\ndef example():\n    print('Translate this UI prompt')\n    print(t('navigation.missing'))\n")
    locale = tmp_path / 'commons_game/locales/en.yaml'
    with locale.open('a', encoding='utf-8') as file:
        file.write('\nunused_test_message: This key has no caller.\n')
    script = tmp_path / 'commons_game/web/app.js'
    with script.open('a', encoding='utf-8') as file:
        file.write("\nconst newLabel = 'Translate this browser label';\n")
    french = tmp_path / 'commons_game/locales/fr.yaml'
    french.write_text(french.read_text(encoding='utf-8').replace('{value}', '{wrong}'), encoding='utf-8')
    problems, _, _ = audit(tmp_path)
    assert any('hard-coded UI text' in problem and 'Translate this UI prompt' in problem for problem in problems)
    assert any('hard-coded UI text' in problem and 'Translate this browser label' in problem for problem in problems)
    assert any('missing key navigation.missing' in problem for problem in problems)
    assert 'Unused key unused_test_message' in problems
    assert any('interpolation fields differ for web.connection.shared_world_commit' in problem for problem in problems)
