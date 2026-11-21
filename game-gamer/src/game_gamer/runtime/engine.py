"""Collective transitions and the legacy-compatible event representation."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import hashlib
import json

from .transactions import WorldEngine
from ..model import (TABLES, ENTITY_TABLES, Agreement, AgreementVersion, Approval,
                    Commitment, DomainError, require)
from . import invitations, reconstruction, curation, curation_requests, missions
from .governance import evaluate_authorisation


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def instant(value):
    require(isinstance(value, str), 'invalid_timestamp')
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        raise DomainError('invalid_timestamp') from None
    require(result.tzinfo is not None, 'timezone_required')
    return result


def text(value, code='text_required'):
    require(isinstance(value, str) and bool(value.strip()), code)
    return value.strip()


FIELDS = {
    **invitations.FIELDS,
    **reconstruction.FIELDS,
    **curation.FIELDS,
    **curation_requests.FIELDS,
    **missions.FIELDS,
    'draft': ({'id', 'label', 'parties', 'objective_id', 'terms', 'resources', 'valid_until', 'policy_id', 'verification'}, {'interaction_context'}),
    'propose': ({'id', 'label', 'parties', 'objective_id', 'terms', 'resources', 'valid_until', 'policy_id', 'verification'}, {'interaction_context'}),
    'publish_proposal': ({'agreement_id', 'version'}, set()),
    'amend': ({'agreement_id', 'version', 'terms'}, {'resources', 'valid_until', 'policy_id', 'verification'}),
    'accept': ({'agreement_id', 'version'}, set()),
    'authorize': ({'agreement_id', 'version'}, set()),
    'activate': ({'agreement_id', 'version'}, set()),
    'initiate': ({'agreement_id', 'version', 'reference'}, set()),
    'fulfill': ({'agreement_id', 'version', 'reference', 'criteria'}, set()),
    'verify': ({'agreement_id', 'version', 'reference'}, set()),
    'reject': ({'agreement_id', 'version', 'reason'}, set()),
    'withdraw': ({'agreement_id', 'version', 'reason'}, set()),
    'suspend': ({'agreement_id', 'version', 'reason'}, set()),
    'resume': ({'agreement_id', 'version'}, set()),
    'terminate': ({'agreement_id', 'version', 'reason'}, set()),
    'dispute': ({'agreement_id', 'version', 'reason'}, set()),
    'advance_time': ({'time'}, set()),
    'declare': ({'table', 'record'}, set()),
    'reconcile_resource': ({'resource_id', 'quantity', 'reference'}, set()),
    'invite': ({'recipient_id', 'objective_id'}, set()),
    'respond_invitation': ({'invitation_id', 'response'}, set()),
}
TERMINAL = {'rejected', 'withdrawn', 'expired', 'terminated'}


class CollectiveEngine(WorldEngine):
    tables = TABLES
    fields = FIELDS
    extension_fields = {}
    entity_tables = ENTITY_TABLES
    epoch = datetime.fromisoformat('2026-11-02T00:00:00+00:00')

    @staticmethod
    def _result(event):
        return {**WorldEngine._result(event), 'commit_id': event['commit']['id'],
                'state_version': event['sequence'],
                'authorization': deepcopy(event['commit']['authorization'])}

    def _decorate_event(self, event, before, after):
        action = after['actions'].get(event['action_id'], {})
        event['commit'] = {
            'id': f"commit_{event['sequence']:06}", 'action_id': event['action_id'],
            'author_id': event['actor_id'], 'timestamp': event['occurred_at'],
            'previous_version': event['sequence'] - 1, 'resulting_version': event['sequence'],
            'previous_state': digest(before), 'resulting_state': digest(after),
            'authorization': deepcopy(action.get('authorization', {
                'decision': 'allowed', 'rule': {'ecosystem.imported': 'read_only_ecosystem_import',
                    'reconstruction.sources_imported': 'trusted_historical_source_import',
                    'missions.installed': 'trusted_mission_pack_installation',
                    'curator.access_granted': 'trusted_local_curator_provisioning',
                    'curator.access_revoked': 'trusted_local_curator_provisioning',
                    'identity_binding.requested': 'pending_identity_claim'}.get(event['kind'], 'synthetic_scenario_initialisation'),
                'actor_id': 'system'})),
        }

    def _validate_event(self, entry, before):
        commit = entry.get('commit', {})
        require(commit.get('previous_state') == digest(before), 'invalid_commit_chain')
        require(commit.get('previous_version') == entry['sequence'] - 1 and
                commit.get('resulting_version') == entry['sequence'] and
                commit.get('id') == f"commit_{entry['sequence']:06}" and
                commit.get('action_id') == entry['action_id'] and
                commit.get('author_id') == entry['actor_id'], 'invalid_commit_metadata')
        after = deepcopy(before)
        for mutation in entry['mutations']:
            after[self.entity_tables[mutation['entity_type']]][mutation['entity_id']] = mutation['after']
        require(commit.get('resulting_state') == digest(after), 'invalid_commit_state')

    def validate(self, command):
        try:
            require(isinstance(command, dict), 'invalid_command')
            text(command.get('key'), 'key_required')
            text(command.get('kind'), 'unknown_command')
            text(command.get('actor'), 'actor_required')
            kind = command['kind']
            require(kind in self.fields, 'unknown_command')
            required, optional = self.fields[kind]
            require(required <= command.keys(), 'missing_field')
            require(not (command.keys() - required - optional - {'key', 'kind', 'actor', 'session'}), 'unsupported_field')
            if 'session' in command:
                session = command['session']
                require(isinstance(session, dict) and set(session) ==
                        {'mode', 'provider', 'subject', 'binding_actor', 'authority', 'authenticated'}, 'invalid_session_context')
                require(session['mode'] == 'simulation' and session['authenticated'] is False, 'live_identity_unavailable')
                require(session['binding_actor'] == command['actor'], 'actor_mismatch')
                text(session['provider']); text(session['subject'])
                require(session['authority'] in {'personal', 'organisation'}, 'invalid_binding_authority')
            prior = self._prior(command)
            if prior:
                require(digest(prior['command']) == digest(command), 'key_conflict')
                return []
            require(command['actor'] in self._world['actors'], 'unknown_actor')
            require(self._world['actors'][command['actor']]['status'] == 'active', 'inactive_actor')
            if 'session' in command and self._world['actors'][command['actor']]['kind'] == 'organisation':
                require(command['session']['authority'] == 'organisation', 'organisation_binding_required')
            require(curation.canonical(self._world, command['actor']) == command['actor'], 'canonical_identity_required')
            require(curation.state(self._world).get('visibility', {}).get(command['actor'], {}).get('value') != 'archived',
                    'archived_actor')
            if kind not in curation.FIELDS and kind not in curation_requests.FIELDS:
                for field in ('target_id', 'recipient_id'):
                    target = command.get(field)
                    if target is not None:
                        require(curation.canonical(self._world, target) == target, 'canonical_target_required')
                        require(curation.state(self._world).get('visibility', {}).get(target, {}).get('value') != 'archived',
                                'archived_target')
            self._prepare(command)
            return []
        except DomainError as error:
            return [str(error)]
        except (TypeError, ValueError, KeyError, IndexError):
            return ['invalid_payload']

    @staticmethod
    def _version(agreement):
        return agreement['versions'][agreement['current_version'] - 1]

    @staticmethod
    def _authorised(world, version):
        return evaluate_authorisation(world, version).status == 'allowed'

    @staticmethod
    def _release(world, agreement, status='released'):
        for reservation in world['reservations'].values():
            if reservation['agreement_id'] == agreement['id'] and reservation['status'] == 'held':
                reservation['status'] = status

    @staticmethod
    def _close(world, agreement, status):
        agreement['status'] = status
        CollectiveEngine._release(world, agreement)
        for commitment in world['commitments'].values():
            if commitment['agreement_id'] == agreement['id'] and commitment['status'] != 'verified':
                commitment['status'] = status

    def _new_version(self, world, command, parties, number, actor, timestamp):
        terms = command['terms']
        require(isinstance(terms, dict) and set(terms) == {'purpose', 'responsibilities', 'conditions'}, 'invalid_terms')
        text(terms['purpose'])
        require(isinstance(terms['conditions'], list) and all(isinstance(x, str) and x.strip() for x in terms['conditions']), 'invalid_conditions')
        responsibilities = terms['responsibilities']
        require(isinstance(responsibilities, list) and bool(responsibilities), 'responsibilities_required')
        require(all(isinstance(item, dict) and set(item) == {'actor_id', 'description'} and
                    item['actor_id'] in parties and isinstance(item['description'], str) and item['description'].strip()
                    for item in responsibilities), 'invalid_responsibility')
        require(len({item['actor_id'] for item in responsibilities}) == len(responsibilities), 'one_responsibility_per_actor')
        require({item['actor_id'] for item in responsibilities} == set(parties), 'every_party_requires_responsibility')
        require(instant(command['valid_until']) > instant(world['configuration']['clock']['now']), 'agreement_expired')
        policy = world['governance'].get(command['policy_id'])
        require(policy is not None and policy['status'] == 'active', 'invalid_policy')
        verification = command['verification']
        require(isinstance(verification, dict) and set(verification) == {'verifier_ids', 'criteria', 'independent'}, 'invalid_verification')
        require(verification['independent'] is True, 'independent_verification_required')
        require(isinstance(verification['verifier_ids'], list) and verification['verifier_ids'] and
                all(v in world['actors'] and v not in parties for v in verification['verifier_ids']), 'invalid_verifier')
        require(isinstance(verification['criteria'], list) and verification['criteria'] and
                all(isinstance(v, str) and v.strip() for v in verification['criteria']) and
                len(set(verification['criteria'])) == len(verification['criteria']), 'verification_criteria_required')
        resources = command['resources']
        require(isinstance(resources, list), 'invalid_resources')
        ids = []
        for allocation in resources:
            require(isinstance(allocation, dict) and set(allocation) == {'resource_id', 'quantity'}, 'invalid_resource_request')
            resource = world['resources'].get(allocation['resource_id'])
            require(resource is not None, 'unknown_resource')
            require(resource['owner_id'] in parties, 'resource_owner_must_be_party')
            require(type(allocation['quantity']) is int and allocation['quantity'] > 0, 'positive_integer_quantity_required')
            ids.append(resource['id'])
        require(len(ids) == len(set(ids)), 'duplicate_resource_request')
        content = {key: deepcopy(command[key]) for key in ('terms', 'resources', 'valid_until', 'policy_id', 'verification')}
        content.update(parties=parties, number=number)
        return asdict(AgreementVersion(number=number, proposed_by=actor, created_at=timestamp,
                                      content_digest=digest(content), **{key: content[key] for key in
                                      ('terms', 'resources', 'valid_until', 'policy_id', 'verification')}))

    def _prepare(self, command):
        world = self.get_world()
        require(world['configuration']['world'].get('execution_mode', 'simulation') == 'simulation',
                'unsupported_execution_mode')
        actor, kind = command['actor'], command['kind']
        seq = len(self._log) + 1
        action_id, timestamp = f'action_{seq:06}', self._timestamp()
        authorization = {'decision': 'allowed', 'actor_id': actor, 'rule': kind}
        if 'session' in command:
            authorization['session'] = deepcopy(command['session'])
        action = {'id': action_id, 'kind': kind, 'submitted_by': actor,
                  'submitted_at': timestamp, 'status': 'accepted', 'payload': deepcopy(command),
                  'authorization': authorization, 'target_ids': []}
        agreement = version = None
        summary = f'{kind}.accepted'
        if 'agreement_id' in command:
            text(command['agreement_id'])
            agreement = world['agreements'].get(command['agreement_id'])
            require(agreement is not None, 'unknown_agreement')
            require(type(command['version']) is int and command['version'] == agreement['current_version'], 'agreement_version_conflict')
            version = self._version(agreement)
            require(agreement['status'] not in TERMINAL, 'invalid_transition')
            require(instant(version['valid_until']) > instant(world['configuration']['clock']['now']), 'agreement_expired')
            authorization.update(agreement_id=agreement['id'], agreement_version=version['number'],
                                 policy_id=version['policy_id'], content_digest=version['content_digest'])
            action['target_ids'] = [agreement['id']]

        def party():
            require(actor in agreement['parties'], 'party_required')

        def states(*allowed):
            require(agreement['status'] in allowed, 'invalid_transition')

        def evidence(evidence_kind, reference, **extra):
            eid = f'evidence_{seq:06}'
            world['evidence'][eid] = {'id': eid, 'kind': evidence_kind, 'reference': text(reference, 'evidence_reference_required'),
                                      'submitted_by': actor, 'submitted_at': timestamp, 'action_id': action_id,
                                      'status': 'reported', 'provenance': {'kind': 'synthetic_gameplay'}, **extra}
            return eid

        if kind in invitations.KINDS:
            summary = invitations.prepare(world, command, actor=actor, timestamp=timestamp, sequence=seq, action=action)
        elif kind in missions.FIELDS:
            missions.prepare(world, command, actor=actor, timestamp=timestamp, sequence=seq, action=action)
        elif kind in curation_requests.FIELDS:
            curation_requests.prepare(world, command, actor=actor, timestamp=timestamp, sequence=seq, action=action)
        elif kind in curation.FIELDS:
            curation.prepare(world, command, actor=actor, timestamp=timestamp, sequence=seq, action=action)
        elif kind in self.extension_fields:
            self._prepare_extension(world, command, actor=actor, timestamp=timestamp, sequence=seq, action=action)
        elif kind in reconstruction.FIELDS:
            reconstruction.prepare(world, command, actor=actor, timestamp=timestamp, sequence=seq, action=action)
        elif kind in {'draft', 'propose'}:
            gid = text(command['id'])
            require(gid not in world['agreements'], 'agreement_exists')
            parties = command['parties']
            require(isinstance(parties, list) and len(parties) >= 2 and len(set(parties)) == len(parties)
                    and all(p in world['actors'] for p in parties), 'invalid_parties')
            require(actor in parties, 'party_required')
            require(command['objective_id'] in world['objectives'], 'unknown_objective')
            require(len(parties) >= world['objectives'][command['objective_id']]['success']['minimum_parties'], 'coalition_too_small')
            v = self._new_version(world, command, parties, 1, actor, timestamp)
            agreement = asdict(Agreement(id=gid, label=text(command['label']), parties=parties,
                                         objective_id=command['objective_id'], versions=[v],
                                         created_by=actor, created_at=timestamp,
                                         status='draft' if kind == 'draft' else 'proposed'))
            if 'interaction_context' in command:
                context=command['interaction_context']
                require(isinstance(context,dict) and set(context)=={'relationship','invitation_id'}
                        and isinstance(context['relationship'],dict), 'invalid_interaction_context')
                invitations.validate_context(world,context['relationship'],seq)
                if context['invitation_id'] is not None:
                    invitation=world['relationships'].get(context['invitation_id'],{})
                    require(invitation.get('kind')=='contact_invitation' and
                            {invitation['source_id'],invitation['target_id']} <= set(parties), 'invalid_invitation_context')
                agreement['interaction_context']=deepcopy(context)
            world['agreements'][gid] = agreement
            action['target_ids'] = [gid]
        elif kind == 'publish_proposal':
            party(); states('draft')
            agreement['status'] = 'proposed'
        elif kind == 'amend':
            party(); states('draft', 'proposed', 'negotiating', 'accepted', 'authorized')
            payload = {**version, **command}
            v = self._new_version(world, payload, agreement['parties'], version['number'] + 1, actor, timestamp)
            version['status'] = 'superseded'
            agreement['versions'].append(v)
            agreement['current_version'] += 1
            agreement['status'] = 'negotiating'
        elif kind == 'accept':
            party(); states('proposed', 'negotiating', 'accepted')
            require(actor not in version['acceptances'], 'already_accepted')
            version['acceptances'][actor] = asdict(Approval(actor_id=actor, agreement_id=agreement['id'],
                version=version['number'], content_digest=version['content_digest'], action_id=action_id, recorded_at=timestamp))
            if 'session' in command:
                version['acceptances'][actor]['method'] = ('development_role_simulation'
                    if command['session']['provider'] in {'development_simulation', 'counterfactual_simulation'}
                    else 'mock_identity_simulation')
            if set(agreement['parties']) <= version['acceptances'].keys():
                agreement['status'] = 'accepted'
        elif kind == 'authorize':
            states('accepted', 'authorized')
            policy = world['governance'][version['policy_id']]
            require(actor in policy['eligible_actors'], 'unauthorized_approval')
            require(actor not in version['authorizations'], 'already_authorized')
            version['authorizations'][actor] = asdict(Approval(actor_id=actor, agreement_id=agreement['id'],
                version=version['number'], content_digest=version['content_digest'], action_id=action_id, recorded_at=timestamp))
            authorization['policy_snapshot'] = deepcopy(policy)
            authorization['approvers'] = list(version['authorizations'])
            if self._authorised(world, version):
                agreement['status'] = 'authorized'
        elif kind == 'activate':
            party()
            require(agreement['status'] in {'accepted', 'authorized'}, 'invalid_transition')
            require(self._authorised(world, version), 'missing_authorization')
            require(set(agreement['parties']) <= version['acceptances'].keys(), 'missing_acceptance')
            objective = world['objectives'][agreement['objective_id']]
            if objective['mode'] == 'gathering':
                attendees = {r['target_id'] for r in world['relationships'].values()
                             if r.get('kind') == 'invited' and r.get('objective_id') == objective['id'] and r['status'] == 'accepted'}
                attendees.add(agreement['created_by'])
                require(len(attendees & set(agreement['parties'])) >= objective['success']['minimum_attendees'], 'gathering_attendance_required')
            for allocation in version['resources']:
                resource = world['resources'][allocation['resource_id']]
                require(resource['control'] == 'internal' or resource['status'] == 'reconciled', 'external_resource_unverified')
                used = sum(r['quantity'] for r in world['reservations'].values()
                           if r['resource_id'] == resource['id'] and r['status'] == 'held')
                require(used + allocation['quantity'] <= resource['quantity'], 'resource_overcommitment')
                rid = f"reservation_{seq:06}_{len(world['reservations']) + 1}"
                world['reservations'][rid] = {'id': rid, 'agreement_id': agreement['id'], 'agreement_version': version['number'],
                    **allocation, 'status': 'held', 'release_condition': 'verified_outcome_or_explicit_closure',
                    'created_by': actor, 'created_at': timestamp, 'escrow_kind': 'simulated_reservation'}
            for i, responsibility in enumerate(version['terms']['responsibilities'], 1):
                cid = f'commitment_{seq:06}_{i}'
                world['commitments'][cid] = asdict(Commitment(id=cid, agreement_id=agreement['id'],
                    agreement_version=version['number'], actor_id=responsibility['actor_id'],
                    responsibility=responsibility['description'], created_by=actor, created_at=timestamp))
            agreement['status'] = 'active'
            authorization['approvers'] = list(version['authorizations'])
            authorization['accepting_parties'] = list(version['acceptances'])
            authorization['policy_snapshot'] = deepcopy(world['governance'][version['policy_id']])
        elif kind == 'initiate':
            party(); states('active')
            commitments = [c for c in world['commitments'].values() if c['agreement_id'] == agreement['id'] and c['actor_id'] == actor]
            require(bool(commitments), 'responsibility_required')
            require(all(c['status'] == 'active' for c in commitments), 'execution_already_recorded')
            eid = evidence('execution_record', command['reference'], agreement_id=agreement['id'], agreement_version=version['number'])
            agreement['initiated_actions'].append(action_id)
            agreement['evidence_ids'].append(eid)
            for commitment in commitments:
                commitment['execution_action_id'] = action_id
                commitment['status'] = 'in_progress'
        elif kind == 'fulfill':
            party(); states('active')
            commitments = [c for c in world['commitments'].values() if c['agreement_id'] == agreement['id'] and c['actor_id'] == actor]
            require(bool(commitments) and all(c['status'] == 'in_progress' for c in commitments), 'execution_required')
            require(isinstance(command['criteria'], list) and set(command['criteria']) == set(version['verification']['criteria']), 'all_criteria_required')
            eid = evidence('fulfilment_report', command['reference'], criteria=command['criteria'],
                           agreement_id=agreement['id'], agreement_version=version['number'])
            agreement['evidence_ids'].append(eid)
            for commitment in commitments:
                commitment.update(status='fulfilled', evidence_ids=[eid])
            if all(c['status'] == 'fulfilled' for c in world['commitments'].values() if c['agreement_id'] == agreement['id']):
                agreement['status'] = 'fulfilled'
        elif kind == 'verify':
            states('fulfilled')
            require(agreement['outcome_status'] != 'verified', 'outcome_already_verified')
            require(actor not in agreement['parties'], 'independent_verifier_required')
            require(actor in version['verification']['verifier_ids'], 'unauthorized_verifier')
            eid = evidence('independent_verification', command['reference'], agreement_id=agreement['id'], agreement_version=version['number'])
            world['evidence'][eid]['status'] = 'verified'
            agreement['evidence_ids'].append(eid)
            agreement['outcome_status'] = 'verified'
            for commitment in world['commitments'].values():
                if commitment['agreement_id'] == agreement['id']:
                    commitment['status'] = 'verified'
                    commitment['evidence_ids'].append(eid)
            self._release(world, agreement)
        elif kind in {'reject', 'withdraw', 'terminate', 'suspend', 'dispute'}:
            text(command['reason'], 'reason_required')
            party()
            allowed = {'reject': ('draft', 'proposed', 'negotiating'),
                       'withdraw': ('draft', 'proposed', 'negotiating', 'accepted', 'authorized'),
                       'terminate': ('active', 'suspended', 'disputed', 'fulfilled'),
                       'suspend': ('active',), 'dispute': ('active', 'fulfilled', 'suspended')}
            states(*allowed[kind])
            require(agreement['outcome_status'] != 'verified', 'verified_outcome_is_final')
            status = {'reject': 'rejected', 'withdraw': 'withdrawn', 'terminate': 'terminated', 'suspend': 'suspended', 'dispute': 'disputed'}[kind]
            agreement['reason'] = command['reason']
            if kind in {'suspend', 'dispute'}:
                agreement['status'] = status  # preserve held reservations until explicit resolution
            else:
                self._close(world, agreement, status)
        elif kind == 'resume':
            party(); states('suspended')
            require(self._authorised(world, version), 'missing_authorization')
            agreement['status'] = 'active'
        elif kind == 'advance_time':
            require('facilitator' in world['actors'][actor]['roles'], 'facilitator_required')
            require(instant(command['time']) > instant(world['configuration']['clock']['now']), 'time_must_advance')
            world['configuration']['clock']['now'] = command['time']
            invitations.expire(world, command['time'], f'commit_{seq:06}')
            for item in world['agreements'].values():
                if item['status'] not in TERMINAL and item['outcome_status'] != 'verified' and instant(self._version(item)['valid_until']) <= instant(command['time']):
                    self._close(world, item, 'expired')
        elif kind == 'declare':
            table = command['table']
            require(table in {'relationships', 'capacities', 'needs'}, 'invalid_declaration_table')
            record = command['record']
            allowed = {'relationships': {'source_id', 'target_id', 'kind', 'note'},
                       'capacities': {'domain', 'quantity', 'unit'}, 'needs': {'domain', 'quantity', 'unit'}}[table]
            require(isinstance(record, dict) and set(record) == allowed, 'invalid_declaration')
            if table == 'relationships':
                require(record['source_id'] in world['actors'] and record['target_id'] in world['actors'], 'unknown_actor')
                require(record['kind'] in {'knows', 'collaborates_with', 'affiliated_with'}, 'invalid_relationship')
                text(record['note'])
            else:
                text(record['domain']); text(record['unit'])
                require(type(record['quantity']) is int and record['quantity'] > 0, 'positive_integer_quantity_required')
            rid = f'{table}_{seq:06}'
            world[table][rid] = {**deepcopy(record), 'id': rid, 'actor_id': actor,
                'status': 'reported', 'created_by': actor, 'created_at': timestamp,
                'provenance': {'kind': 'player_declaration', 'action_id': action_id}}
        elif kind == 'reconcile_resource':
            resource = world['resources'].get(command['resource_id'])
            require(resource is not None and resource['control'] == 'external', 'external_resource_required')
            require('resource_verifier' in world['actors'][actor]['roles'] and actor != resource['owner_id'], 'resource_verifier_required')
            require(type(command['quantity']) is int and command['quantity'] >= 0, 'invalid_quantity')
            held = sum(r['quantity'] for r in world['reservations'].values() if r['resource_id'] == resource['id'] and r['status'] == 'held')
            require(command['quantity'] >= held, 'resource_overcommitment')
            eid = evidence('resource_reconciliation', command['reference'], resource_id=resource['id'])
            resource.update(quantity=command['quantity'], status='reconciled', evidence_ids=resource['evidence_ids'] + [eid])
        elif kind == 'invite':
            require(command['objective_id'] in world['objectives'] and world['objectives'][command['objective_id']]['mode'] == 'gathering', 'gathering_objective_required')
            require(command['recipient_id'] in world['actors'] and command['recipient_id'] != actor, 'invalid_recipient')
            require(not any(r.get('kind') == 'invited' and r['source_id'] == actor and r['target_id'] == command['recipient_id'] and r['objective_id'] == command['objective_id'] for r in world['relationships'].values()), 'invitation_exists')
            rid = f'invitation_{seq:06}'
            world['relationships'][rid] = {'id': rid, 'source_id': actor, 'target_id': command['recipient_id'],
                'objective_id': command['objective_id'], 'kind': 'invited', 'status': 'proposed', 'created_by': actor,
                'created_at': timestamp, 'provenance': {'kind': 'synthetic_gameplay'}}
        elif kind == 'respond_invitation':
            invitation = world['relationships'].get(command['invitation_id'])
            require(invitation is not None and invitation['kind'] == 'invited' and invitation['status'] == 'proposed', 'pending_invitation_required')
            require(invitation['target_id'] == actor, 'recipient_required')
            require(command['response'] in {'accept', 'decline'}, 'invalid_response')
            invitation['status'] = 'accepted' if command['response'] == 'accept' else 'rejected'
        else:
            raise DomainError('unknown_command')

        world['actions'][action_id] = action
        for objective in world['objectives'].values():
            agreements = [a for a in world['agreements'].values() if a['objective_id'] == objective['id']]
            objective['support_ids'] = [a['id'] for a in agreements if a['outcome_status'] == 'verified']
            objective['status'] = 'verified' if len(objective['support_ids']) >= objective['success']['verified_agreements'] else 'open'
        return world, action_id, summary

    def project(self, view='now', *, at=None, time=None):
        with self._lock:
            world = self.world_at(event=at, time=time) if at is not None or time is not None else self.get_world()
            if view in {'log', 'timeline', 'now'}:
                entries = [entry for entry in self._log if (at is None or entry['sequence'] <= at) and
                           (time is None or instant(entry['occurred_at']) <= instant(time))]
                if view != 'now':
                    return deepcopy(entries)
        if view == 'world':
            return world
        if view == 'network':
            return self._network(world)
        if view == 'missions':
            from ..projections.missions import project_mission
            return [project_mission(world, ident) for ident in missions.definitions(world)]
        if view in self.tables:
            return list(world[view].values())
        if view == 'now':
            return {'version': len(entries), 'world': world,
                    'possibilities': self.derive_possibilities(world), 'network': self._network(world)}
        raise DomainError('unknown_projection')

    def derive_possibilities(self, world=None):
        world = world if world is not None else self.get_world()
        from ..projections.network import potential_complementarities
        return potential_complementarities(world)

    def _network(self, world):
        from ..projections.network import network
        return network(world, possibilities=self.derive_possibilities(world))
