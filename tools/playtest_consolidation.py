"""Record the revised workshop using fictional people and a provisioned test curator."""
import argparse
import asyncio
import json
import re
import time
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'tools'))

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.catalogue import people
from game_gamer.exercises.tutorials import catalogue
from playtest_matrix import Driver, PTY, fictional_world


class RecordingDriver(Driver):
    def __init__(self, transport, output):
        super().__init__(transport, output)
        self.started = time.monotonic()
        self.recorded = 0
        self.frames = []

    def record_output(self):
        data = bytes(self.raw[self.recorded:])
        if data:
            self.frames.append([round(time.monotonic()-self.started, 6), 'o', data.decode('utf-8', 'replace')])
            self.recorded = len(self.raw)

    async def expect(self, value, timeout=12):
        await super().expect(value, timeout)
        self.record_output()

    async def send(self, value):
        await super().send(value)
        self.record_output()

    def save(self):
        super().save()
        self.record_output()
        header = {'version': 2, 'width': 144, 'height': 34,
                  'title': 'Commons Game · fictional consolidation playthrough'}
        with (self.output/'session.cast').open('w') as recording:
            recording.write(json.dumps(header)+'\n')
            for frame in self.frames:
                recording.write(json.dumps(frame, ensure_ascii=False)+'\n')


async def run(output):
    output.mkdir(parents=True, exist_ok=False)
    game = fictional_world()
    before = game.get_world()
    after = deepcopy(before)
    roster = people(before)
    after['actors'][roster[0]['id']]['roles'].append('curator')
    duplicate = deepcopy(after['actors'][roster[1]['id']])
    duplicate['id'] = 'fixture-duplicate'
    after['actors'][duplicate['id']] = duplicate
    game._commit(before, after, 'fixture.curator_provisioned')
    store = SQLiteStore(output/'fictional.sqlite', CommonsGame)
    store.initialise(game)
    port = PTY([sys.executable, '-B', '-m', 'commons_game', '--db', str(store.path), 'play'], colour=True)
    d = RecordingDriver(port, output)

    async def capture(name):
        await d.send('')
        # Curator screens intentionally expose original source IDs, all fictional here.
        (output/(name+'.txt')).write_text(d.text()+'\n')

    async def menu(label):
        for _ in range(40):
            if any('> [' in line and label in line[line.index('> ['):] for line in d.screen.display):
                await d.enter()
                return
            current = re.search(r'> \[(\d+)\]', d.text())
            target = re.search(r'\[(\d+)\] '+re.escape(label), d.text())
            upward = current and (not target or int(current[1]) > int(target[1])) and int(current[1]) > 1
            await d.send('\x1bOA' if upward else '\x1bOB')
        raise AssertionError('Could not select displayed option '+label+'\n'+d.text())

    try:
        await d.expect('SADDLE PATHWAYS')
        await d.enter()
        await d.expect('WHO WILL YOU PLAY?')
        await d.choose('Alex')
        await d.expect('CHOOSE YOUR PATH')
        await capture('01-worlds-and-workshop')
        await d.send('4')
        await d.expect('EXERCISES / WORKSHOP')
        await capture('02-exercises')
        await d.send('4')
        await d.expect('BEGIN RECONSTRUCTION')
        await capture('03-visible-begin')
        await d.enter()
        await d.expect('DIRECTORY')
        await port.resize(144, 34)
        d.screen.resize(lines=34, columns=144)
        await d.expect('CONNECTIONS / NETWORK')
        await capture('04-three-regions-and-curator')
        await d.send('f')
        await d.expect('FILTER PEOPLE')
        await menu('Offers')
        await d.expect('FILTER / OFFERS')
        await capture('05-counted-facets')
        await d.enter()
        await d.send('b')
        await d.expect('FILTER PEOPLE')
        await menu('APPLY')
        await d.expect('DIRECTORY')
        await d.send('c')
        await d.expect('CONNECT WITH Casey')
        await d.enter()
        await d.expect('RECORD THIS CONNECTION?')
        await d.send('az')
        await capture('06-invalid-input-preserves-confirmation')
        await d.send('\x1b')
        await d.expect('Action cancelled.')
        await d.send('c')
        await d.expect('CONNECT WITH Casey')
        await d.enter()
        await d.expect('RECORD THIS CONNECTION?')
        await d.enter()
        await d.expect('RECOLLECTION RECORDED')
        await capture('07-action-result')
        await d.enter()
        await d.expect('1 directed claims')
        await d.send('G')
        await d.send('v')
        await d.expect('Collective')
        await capture('08-collective-graph')
        await d.send('L')
        await d.expect('NETWORK / LAYERS')
        await capture('09-observation-layers')
        await d.send('b')
        await d.send('d')
        await d.expect('CONNECTION / PROVENANCE')
        await capture('10-connection-provenance')
        await d.send('b')
        await d.send('b')
        await d.send('u')
        await d.expect('CONTEXT / CURATION')
        await capture('11-curator-operations')
        # The contextual target is the selected duplicate Casey; choose the
        # explicitly displayed original, then reverse the synthetic merge.
        await menu('Preview verified')
        await d.expect('SELECT VERIFIED CANONICAL IDENTITY')
        await d.choose('Casey Example')
        await d.expect('CURATOR / MERGE PREVIEW')
        await capture('12-merge-preview')
        await d.enter()
        await d.answer('Reference for the verified identity check', 'Synthetic duplicate checked for this test')
        await d.expect('MERGE THESE VERIFIED IDENTITIES?')
        await d.enter()
        await d.expect('CURATOR CHANGE RECORDED')
        await menu('Reverse identity')
        await d.expect('REVERSE IDENTITY MERGE')
        await d.enter()
        await d.answer('Reference for the corrected identity decision', 'Synthetic reversal test')
        await d.expect('REVERSE THIS IDENTITY MERGE?')
        await d.enter()
        await d.expect('CURATOR CHANGE RECORDED')
        await capture('13-merge-reversal')
        await menu('Request profile')
        await d.answer('Reason for the curation request', 'Please review this fictional participant profile')
        await d.expect('SUBMIT THIS CURATION REQUEST?')
        await d.enter()
        await d.expect('CURATION REQUEST RECORDED')
        await menu('Curator review queue')
        await d.enter()
        await d.expect('CURATION / REQUEST REVIEW')
        await menu('APPROVE REQUEST')
        await d.answer('Review reason or clarification', 'Fictional source reviewed')
        await d.expect('RECORD THIS CURATION REVIEW?')
        await d.enter()
        await d.expect('Status: approved')
        await capture('15-reviewed-request')
        await d.send('b')
        await d.send('b')
        await port.resize(70, 26)
        d.screen.resize(lines=26, columns=70)
        await d.expect('CONTEXT / CURATION')
        await capture('16-narrow-context-panel')
        await d.send('\t')
        await d.expect('RECONSTRUCT THE NETWORK')
        await capture('17-narrow-main-view')
        await d.send('u')
        await port.resize(144, 34)
        d.screen.resize(lines=34, columns=144)
        await d.send('H')
        await d.expect('HISTORY / COLLECTIVE / Overview')
        await capture('18-global-history')
        await d.send('+')
        await d.expect('HISTORY / COLLECTIVE / Detailed')
        await d.send('+')
        await d.expect('HISTORY / COLLECTIVE / Technical')
        await capture('19-technical-history')
        await d.enter()
        await d.expect('HISTORY / EVENT / Technical')
        await d.enter()
        await d.expect('HISTORICAL OBJECT')
        await d.send('b')
        await d.expect('HISTORY / EVENT / Technical')
        await d.send('b')
        await d.expect('HISTORY / COLLECTIVE / Technical')
        await d.send('--')
        await d.send('f')
        await d.expect('HISTORY FILTER')
        await d.choose('Action')
        await d.expect('CHOOSE HISTORY ACTION')
        await d.choose('recall_connection')
        await d.expect('1 events')
        await capture('20-filtered-history')
        await d.send('m')
        await d.expect('CHOOSE YOUR PATH')
        await d.send('4')
        await d.expect('EXERCISES / WORKSHOP')
        for index, definition in enumerate(catalogue(), 1):
            await d.send(str(index))
            await d.expect('TUTORIAL / '+definition['title'].upper())
            for step in definition['steps']:
                await d.enter()
                await d.expect('CONTINUE AS '+step['actor_id'].upper())
                await d.enter()
            await d.expect('TUTORIAL COMPLETE')
            await capture(f'14-tutorial-{definition["id"]}')
            await d.send('b')
            await d.expect('EXERCISES / WORKSHOP')
        await d.send('q')
    finally:
        d.save()
        await port.close()
    restored = store.load()
    claims = [r for r in restored.project('relationships') if r['kind'] == 'recollection_claim']
    assert len(claims) == 1
    assert not restored.project('agreements')  # tutorial agreements never reached this world
    assert restored.get_world() == restored.replay().get_world()
    assert all(row['status'] == 'reversed' for row in restored.get_world()['configuration']['curation']['merges'].values())
    print('Workshop, counted facets, invalid/cancelled confirmation, claim, graph, merge/reversal and three tutorials passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(run(parser.parse_args().output.resolve()))
