"""Public synthetic fixtures for the player-facing terminal and source coverage."""
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import os
import subprocess
import sys
from uuid import UUID

import pytest

from commons_game import CommonsGame, load_scenario
from commons_game.catalogue import SimulationAuthority, affiliations, people
from commons_game.commands import COMMANDS, contract_aliases, parse, resolve
from commons_game.ecosystem_import import import_snapshot
from commons_game.montreal_capture import capture_montreal, declared_topics
from commons_game.play import PlayableTerminal
from commons_game.presentation import OBJECTS, Presentation, dictionary
from commons_game.scenario import demo_commands
from commons_game.tui import Terminal

ROOT=Path(__file__).resolve().parents[1]
SCOPE={'people_data_source_id':'people','people_database_id':'people-db',
       'responses_data_source_id':'responses','responses_database_id':'responses-db',
       'probe_id':'approved-probe','session_id':'approved-session','topics':{'topic':'Recorded topic'}}


def rich(value, kind='rich_text'):
    return {'type':kind,kind:[{'plain_text':value}]}


def person(i, *, name=None):
    return {'id':str(UUID(int=i)),'created_time':'2026-10-01T00:00:00+00:00',
        'properties':{'Name':rich(name or f'Person{i:02} Example','title'),'institution':rich('Source-local institution'),
                      'participant_uuid':rich('subject-'+str(i))}}


def response(i, actor, *, state='submitted', probe='approved-probe', revision=1):
    envelope={'probe_id':probe,'event_id':'approved-session','record_type':'probe_submission','state':state,
              'participant_id':'subject-'+str(actor), 'revision':revision,
              'payload':{'answers':{'knowledge_offer':{'selected':['topic','other'],'other':{'value':'PRIVATE TEXT'}},
                                    'knowledge_need':['topic'],'email':'PRIVATE CONTACT'}}}
    return {'id':str(UUID(int=1000+i)),'created_time':'2026-10-01T00:00:00+00:00',
        'properties':{'value_json':rich(json.dumps(envelope)),
                      'player':{'type':'relation','relation':[{'id':str(UUID(int=actor))}]}}}


class FakeNotion:
    def __init__(self, people_records=None, responses=None, size=3):
        self.records={'people':people_records or [person(i) for i in range(1,8)],
                      'responses':responses or [response(i,i) for i in range(1,8)]}
        self.size=size;self.queries=[]

    def query(self, source, **kwargs):
        self.queries.append((source,kwargs.get('start_cursor')))
        start=int(kwargs.get('start_cursor',0));batch=self.records[source][start:start+self.size]
        more=start+self.size<len(self.records[source])
        return {'results':deepcopy(batch),'has_more':more,'next_cursor':str(start+self.size) if more else None}


def imported(count=7):
    client=FakeNotion([person(i) for i in range(1,count+1)],[response(i,i) for i in range(1,count+1)])
    snapshot,report=capture_montreal(client,SCOPE,captured_at='2026-11-04T00:00:00+00:00')
    game=load_scenario('montreal-commons');assert not import_snapshot(game,snapshot)['rejected']
    return game,snapshot,report


def ui_for(game=None, entered='', *, plain=True):
    output=StringIO();ui=PlayableTerminal(game or imported()[0],source=StringIO(entered),output=output,plain=plain)
    return ui,output


def test_complete_pagination_and_all_eligible_people_in_catalogue():
    client=FakeNotion([person(i) for i in range(1,42)],[response(i,i) for i in range(1,42)],size=8)
    snapshot,report=capture_montreal(client,SCOPE,captured_at='2026-11-04T00:00:00+00:00')
    assert report['source_records_inspected']==82 and report['eligible_people']==41
    assert len(client.queries)==12
    game=load_scenario('montreal-commons');assert not import_snapshot(game,snapshot)['rejected']
    assert len(people(game.get_world()))==41
    assert len({a['id'] for a in people(game.get_world())})==41
    assert 'PRIVATE TEXT' not in json.dumps(snapshot) and 'PRIVATE CONTACT' not in json.dumps(snapshot)


def test_reconciliation_counts_duplicates_missing_identity_and_source_local_mentions():
    records=[response(1,1),response(2,2),response(3,1,revision=2),response(4,3),
             response(5,2,probe='outside'),response(6,2,state='draft')]
    snapshot,report=capture_montreal(FakeNotion([person(1,name='Same name'),person(2,name='Same name')],records),SCOPE,
                                     captured_at='2026-11-04T00:00:00+00:00')
    assert report['eligible_people']==2 and report['repeated_submitted_inventories']==1
    assert len(report['unresolved_identity_records'])==1 and len(report['duplicate_name_candidates'])==1
    assert report['source_local_organisation_mentions']==2 and report['distinct_organisation_labels']==1
    game=load_scenario('montreal-commons');import_snapshot(game,snapshot)
    assert len(people(game.get_world()))==2
    assert len([a for a in game.project('actors') if a['kind']=='organisation'])==2


def test_latest_skipped_declaration_does_not_recreate_old_answer():
    envelope={'payload':{'answers':{'knowledge_offer':['topic']},'trajectory':{'events':[
        {'question_id':'knowledge_offer','kind':'answered','value':['topic']},
        {'question_id':'knowledge_offer','kind':'skipped'}]}}}
    assert declared_topics(envelope,'knowledge_offer',SCOPE['topics'])==([], 'skipped')


def test_repeated_cursor_is_rejected_instead_of_truncating_capture():
    class Stuck(FakeNotion):
        def query(self,*args,**kwargs):
            return {'results':[],'has_more':True,'next_cursor':'same'}
    with pytest.raises(ValueError,match='source_pagination_did_not_advance'):
        capture_montreal(Stuck(),SCOPE)


def test_conflicting_person_relation_and_inventory_identity_are_reported_not_joined():
    raw=response(1,1)
    raw['properties']['player']['relation']=[{'id':str(UUID(int=2))}]
    snapshot,report=capture_montreal(FakeNotion([person(1),person(2)],[raw]),SCOPE,
                                    captured_at='2026-11-04T00:00:00+00:00')
    assert report['eligible_people']==0
    assert report['skipped']['conflicting_person_identity']==1
    assert report['unresolved_identity_records'][0]['reason']=='conflicting_person_identity'
    assert snapshot['expertise']['participants']=={}


def test_actor_search_selection_preview_and_organisation_filter():
    game,_,_=imported();ui,out=ui_for(game,entered='/Person05\n\n\n')
    ui.select_actor()
    assert ui.label(ui.session.actor)=='Person05'
    assert len(people(game.get_world(),organisation='source-LOCAL'))==7
    assert len(people(game.get_world(),search='PERSON05'))==1
    assert 'SIMULATION ONLY' in out.getvalue()
    assert 'notion:person:' not in out.getvalue()


def test_first_names_only_across_selection_contracts_and_historical_profiles():
    names=['Amira PlaceholderA','Amira PlaceholderB','Jean-Philippe PlaceholderC']
    snapshot,_=capture_montreal(FakeNotion([person(i,name=name) for i,name in enumerate(names,1)],
                                         [response(i,i) for i in range(1,4)]),SCOPE,
                                captured_at='2026-11-04T00:00:00+00:00')
    game=load_scenario('montreal-commons');import_snapshot(game,snapshot)
    original=game.get_world();roster=people(original,search='amira')
    assert len(roster)==2 and roster[0]['id']!=roster[1]['id']
    assert resolve(original,'Amira') is None  # A first name never merges identities.
    assert resolve(original,'Jean-Philippe')==people(original,search='jean')[0]['id']
    ui,out=ui_for(game,entered='/Amira\n2\n')
    ui.select_actor();assert ui.session.actor==roster[1]['id']
    ui._proposal_target=roster[0]['id'];ui.source=StringIO('1\n\n\n\n\ny\n')
    payload=ui.collect_action({'kind':'propose'},game)
    result=ui.session.submit(payload);assert result['ok'],result
    ui.refresh();ui.inspect_node(payload['id'])
    ui.inspect_node(roster[0]['id'],at=2)
    ui.assume_actor(roster[0]);ui.refresh()
    ui.source=StringIO('b\n');ui.cmd_inbox('')
    text=out.getvalue()
    assert 'Amira' in text and 'Source-local institution' in text
    assert all(name.split()[-1] not in text for name in names)
    assert {a['label'] for a in people(game.get_world())}==set(names)
    assert {a['label'] for a in people(game.replay().get_world())}==set(names)


def test_first_name_rendering_keeps_hyphens_accents_and_complete_organisation_names():
    out=StringIO();view=Presentation(out,plain=True)
    person_record={'id':'p','kind':'person','label':'Éloïse-Marie Placeholder · Research group'}
    organisation={'id':'o','kind':'organisation','label':'Source-local Research Organisation'}
    before=deepcopy(person_record)
    view.node(person_record);view.node(organisation)
    assert 'Éloïse-Marie / Research group' in out.getvalue()
    assert 'Placeholder' not in out.getvalue()
    assert organisation['label'] in out.getvalue() and person_record==before


def test_switching_simulated_people_preserves_shared_state_and_rejects_spoofing():
    game,_,_=imported();ui,out=ui_for(game)
    first,second=people(game.get_world())[:2]
    ui.assume_actor(first);before=game.get_world(),game.project('log')
    assert ui.session.submit({'actor':second['id'],'kind':'accept'})['errors']==['actor_mismatch']
    ui.assume_actor(second)
    assert (game.get_world(),game.project('log'))==before
    assert ui.session.actor==second['id'] and ui.identity.authenticated is False
    assert not game.get_world()['actors'][second['id']]['roles']


def test_simulating_organisation_requires_explicit_development_act():
    game,_,_=imported();org=next(a for a in game.project('actors') if a['kind']=='organisation')
    authority=SimulationAuthority()
    with pytest.raises(ValueError,match='explicit_organisation_simulation_required'):
        authority.assume(org)
    identity,binding=authority.assume(org,organisation_confirmed=True)
    assert authority.permits(identity,binding,org) and not identity.authenticated


def test_plain_fallback_shared_dictionary_and_no_domain_mutation():
    game,_,_=imported();before=game.get_world();out=StringIO()
    view=Presentation(out,plain=True,colour=True,width=40)
    for kind in OBJECTS:view.node({'id':kind,'kind':kind,'label':'Example','status':'proposed'})
    text=out.getvalue();assert '\x1b' not in text and all(ord(c)<128 for c in text)
    assert '(P)' in text and '(C)' in text and 'PROPOSED' in text
    assert dictionary()['person']['symbol']=='●'
    assert game.get_world()==before


def test_no_colour_and_unsupported_output_encoding(monkeypatch):
    monkeypatch.setenv('NO_COLOR','1');out=StringIO()
    view=Presentation(out,colour=True);view.node({'id':'p','kind':'person','label':'Person'})
    assert '\x1b' not in out.getvalue()
    class ASCII(StringIO):
        @property
        def encoding(self):return 'ascii'
    output=ASCII();view=Presentation(output,colour=True)
    assert view.plain;view.node({'id':'p','kind':'person','label':'Person'})
    assert output.getvalue().isascii()
    view.write('↑↓ Select');assert 'Up/Down Select' in output.getvalue()
    view.node({'id':'p','kind':'person','label':'Montréal'});assert 'Montre' in output.getvalue()


def test_all_advertised_commands_have_handlers_help_and_availability():
    ui,_=ui_for()
    aliases=[]
    for command in COMMANDS:
        assert callable(getattr(ui,command.handler)) and callable(getattr(ui,command.availability))
        assert command.help and command.screens and command.description
        assert parse(command.name)[0]==command
        aliases.extend([command.name,*command.aliases])
    assert len(set(aliases))==len(aliases)


def test_unavailable_invite_respond_and_actor_permissions_explain_why():
    ui,out=ui_for();ui.assume_actor(people(ui.current().get_world())[0])
    ui.dispatch('invite');ui.dispatch('respond')
    assert 'registered invitation requires a gathering objective' in ' '.join(out.getvalue().split())
    assert 'No pending invitations or proposals' in out.getvalue()
    game=load_scenario();game.submit(demo_commands()[0]);ui,out=ui_for(game)
    ui.assume_actor(game.get_world()['actors']['verifier']);ui.selected='agreement-main';ui.cmd_actions('')
    assert 'No action is permitted' in out.getvalue()


def test_invite_and_respond_execute_in_gathering_fixture():
    game=load_scenario('commons-gathering');ui,out=ui_for(game,entered='1\n1\ny\n')
    ui.assume_actor(game.get_world()['actors']['researcher']);ui.dispatch('invite')
    invitation=next(r for r in game.project('relationships') if r['kind']=='invited')
    ui.source=StringIO('y\n1\n1\ny\n');ui.assume_actor(game.get_world()['actors'][invitation['target_id']]);ui.dispatch('respond')
    assert game.get_world()['relationships'][invitation['id']]['status']=='accepted'
    assert 'Invitation sent' in out.getvalue()


def test_open_latest_contract_and_history_aliases_reach_real_records():
    game=load_scenario();game.submit(demo_commands()[0]);ui,out=ui_for(game,entered='b\n')
    ui.dispatch('open latest contract')
    assert 'Synthetic log access agreement' in out.getvalue() and 'K-001' in out.getvalue()
    ui.source=StringIO('1\n\nb\n');ui.dispatch('contract history')
    assert 'HISTORICAL STATE 2' in out.getvalue()
    assert resolve(game.get_world(),'K-001')=='agreement-main'


def test_bare_open_actions_and_history_use_selection_instead_of_empty_id_errors():
    game=load_scenario();game.submit(demo_commands()[0]);ui,out=ui_for(game,entered='1\nb\n')
    ui.dispatch('open')
    assert 'CHOOSE AN OBJECT' in out.getvalue() and 'unknown node' not in out.getvalue()
    ui.assume_actor(game.get_world()['actors']['researcher']);ui.selected='agreement-main';ui.source=StringIO('b\n')
    ui.dispatch('available actions')
    assert 'WHAT CAN I DO?' in out.getvalue()


def test_developer_graph_command_repairs_preserve_original_repro():
    game=load_scenario();game.submit(demo_commands()[0])
    for entered,expected in [('open latest contract\nb\n','CONTRACT agreement-main / VERSION'),
                             ('history\n1\nb\n','propose.accepted'),
                             ('available actions\n0\nb\n','Available actions for researcher:')]:
        out=StringIO();Terminal(game,actor='researcher',source=StringIO(entered),output=out).graph()
        assert expected in out.getvalue()


def test_default_executable_launches_game_with_no_operation(tmp_path):
    data=tmp_path/'data';data.mkdir();game,_,_=imported();game.save(data/'commons.sqlite')
    result=subprocess.run([sys.executable,'-B','-m','commons_game'],input='/Person02\n\n\nq\n',text=True,capture_output=True,
        cwd=tmp_path,env={**os.environ,'PYTHONPATH':str(ROOT),'SADDLE_DATA_DIR':str(data)},timeout=15)
    assert result.returncode==0,result.stderr
    assert 'WHO WILL YOU PLAY?' in result.stdout and 'Play for real' not in result.stdout
    assert 'EXPLICIT SYNTHETIC HOT-SEAT DEMONSTRATION' not in result.stdout
    assert 'Person02' in result.stdout and 'Example' not in result.stdout


@pytest.mark.parametrize('command',COMMANDS,ids=lambda c:c.name)
def test_each_advertised_command_dispatches_or_gives_contextual_explanation(command):
    game=load_scenario();game.submit(demo_commands()[0]);ui,out=ui_for(game,entered='b\n')
    ui.assume_actor(game.get_world()['actors']['researcher']);ui.selected='agreement-main'
    ui.dispatch(command.name)
    assert 'Unknown command.' not in out.getvalue()


def test_mapped_rich_text_property_is_fully_hydrated():
    from commons_game.montreal_capture import pages
    class Client:
        calls=0
        def query(self,*args,**kwargs):
            return {'results':[{'id':'record','properties':{'Name':{'type':'title','id':'title',
                'title':[{'plain_text':'x'}]*25}}}],'has_more':False}
        def property(self,*args,**kwargs):
            self.calls+=1
            return {'results':[{'title':{'plain_text':'A' if self.calls==1 else 'B'}}],
                    'has_more':self.calls==1,'next_cursor':'second' if self.calls==1 else None}
    client=Client();result=list(pages(client,'source',properties=['Name']))
    assert client.calls==2 and len(result[0]['properties']['Name']['title'])==2
