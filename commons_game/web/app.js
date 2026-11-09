import {MidiMusic} from './music.js';

const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const language = document.documentElement.lang;
const catalogue = await fetch('/api/i18n?lang=' + encodeURIComponent(language)).then(response => response.json());

function t(key, params = {}) {
  if (!Object.hasOwn(catalogue, key)) throw Error('Missing UI message: ' + key);
  return catalogue[key].replace(/\{([a-zA-Z_][a-zA-Z_0-9]*)\}/g, (_, field) => {
    if (!Object.hasOwn(params, field)) throw Error('Missing UI parameter: ' + field);
    return String(params[field]);
  });
}

const music=new MidiMusic();
let state=null,mode='ecosystem',scenario='bilateral-logs',actor='researcher',csrf=null,sessionToken=null,pending=null,busy=false,toastTimer;
const labels={ecosystem:[t("web.headings.ecosystem.kicker"),`${esc(t("web.headings.ecosystem.question"))}<br><em>${esc(t("web.headings.ecosystem.emphasis"))}</em>`],scenarios:[t("web.headings.scenarios.kicker"),`${esc(t("web.headings.scenarios.question"))}<br><em>${esc(t("web.headings.scenarios.emphasis"))}</em>`],gathering:[t("web.headings.gathering.kicker"),`${esc(t("web.headings.gathering.question"))}<br><em>${esc(t("web.headings.gathering.emphasis"))}</em>`]};
const names={propose:t("web.history.events.propose"),amend:t("web.history.events.amend"),accept:t("web.history.events.accept"),authorize:t("web.history.events.authorize"),activate:t("web.history.events.activate"),initiate:t("web.history.events.initiate"),fulfill:t("history.events.fulfill"),verify:t("web.history.events.verify"),invite:t("web.history.events.invite"),respond_invitation:t("web.history.events.respond_invitation")};
const displayLabel=record=>record.kind==='person'?record.label.trim().split(/\s+/)[0]:record.label;
const actorLabel=id=>state?.world.actors[id]?displayLabel(state.world.actors[id]):id;
const currentAgreement=()=>state?Object.values(state.world.agreements)[0]:null;
const currentVersion=agreement=>agreement.versions[agreement.current_version-1];
const shortName=id=>actorLabel(id).split(' · ')[0];
const tag=(text,success=false)=>`<span class="tag${success?' success':''}">${esc(text)}</span>`;

function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,5500);}
async function api(path,body){
  const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf||'','X-Actor-Session':sessionToken||''}:{},body:body?JSON.stringify(body):undefined});
  const result=await response.json();
  if(!result.ok)throw Error(result.errors?.map(code => Object.hasOwn(catalogue, 'errors.' + code) ? t(`errors.${code}`) : code).join(', ') ||
    t("web.connection.the_engine_could_not_complete_this"));
  return result;
}
async function chooseActor(id){
  const session=await api('/api/session',{scenario,actor:id});actor=id;csrf=session.csrf;sessionToken=session.session_token;$('#actor').value=id;
  $('#actor-description').textContent=state.world.actors[actor].roles.join(' · ');
  render();
}
async function refresh(force=false){
  try{
    const next=await api('/api/state?scenario='+encodeURIComponent(scenario));
    const changed=!state||next.version!==state.version||next.world.configuration.world.scenario!==state.world.configuration.world.scenario;
    state=next;$('#world-version').textContent=t("web.connection.shared_world_commit", {value: String(state.version).padStart(3,'0')});
    $('#connection-error').hidden=true;
    if(force||changed)render();
  }catch(error){$('#connection-error').textContent=t("web.connection.engine_connection")+error.message;$('#connection-error').hidden=false;}
}
async function command(payload){
  if(busy)return false;busy=true;
  document.querySelectorAll('[data-command],#action-form button[type="submit"]').forEach(button=>button.disabled=true);
  try{
    const result=await api('/api/command',{scenario,expected_version:state.version,command:{key:crypto.randomUUID(),...payload}});
    await refresh(true);toast(`${names[payload.kind]||t("web.connection.world_changed")} · ${result.commit_id}`);return true;
  }catch(error){toast(error.message);await refresh(true);return false;}
  finally{busy=false;document.querySelectorAll('[data-command],#action-form button[type="submit"]').forEach(button=>button.disabled=false);}
}
function setMode(next){mode=next;document.querySelectorAll('.mode').forEach(button=>{
  button.classList.toggle('active',button.dataset.mode===mode);if(button.dataset.mode===mode)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
});render();}
function banner(){const world=state.world.configuration.world;return `<div class="experiment-banner"><div><h3>${esc(world.title)}</h3><p>${esc(world.description)}</p></div>${tag(t("web.ecosystem.network.synthetic_world"))}</div>`;}

function graph(){
  const actors=Object.values(state.world.actors),center={x:235,y:148},rx=155,ry=104;
  const positions=Object.fromEntries(actors.map((a,i)=>[a.id,{x:center.x+Math.cos(i/actors.length*Math.PI*2-Math.PI/2)*rx,y:center.y+Math.sin(i/actors.length*Math.PI*2-Math.PI/2)*ry}]));
  const agreement=currentAgreement();let lines='';
  for(const edge of state.world.relationships?Object.values(state.world.relationships):[]){
    const from=positions[edge.source_id],to=positions[edge.target_id];if(from&&to)lines+=`<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke-dasharray="3 5"/>`;
  }
  if(agreement)for(const party of agreement.parties){const p=positions[party];lines+=`<line class="agreement" x1="${p.x}" y1="${p.y}" x2="${center.x}" y2="${center.y}"/>`;}
  const nodes=actors.map(a=>{const p=positions[a.id];return `<g><circle class="actor" cx="${p.x}" cy="${p.y}" r="17"/><text x="${p.x}" y="${p.y+3}" text-anchor="middle">${esc(shortName(a.id).slice(0,1))}</text><text x="${p.x}" y="${p.y+33}" text-anchor="middle">${esc(shortName(a.id))}</text></g>`;}).join('');
  const middle=agreement?`<circle class="agreement" cx="235" cy="148" r="34"/><text class="center" x="235" y="145">${esc(t("web.ecosystem.network.agreement"))}</text><text class="center" x="235" y="160">${esc(t("web.agreement.lifecycle.version_marker", {number: agreement.current_version}))}</text>`:`<circle cx="235" cy="148" r="37" fill="none" stroke="#a7b88f" stroke-dasharray="2 6"/><text x="235" y="151" text-anchor="middle">${esc(t("web.ecosystem.network.possibility"))}</text>`;
  return `<svg viewBox="0 0 470 310" class="network" role="img" aria-label="${esc(t("web.ecosystem.network.declared_relationships_and_agreement_parties_in"))}">${lines}${middle}${nodes}</svg>`;
}
function ecosystem(){
  const potential=state.possibilities[0];
  const actors=Object.values(state.world.actors).map(a=>`<div class="actor-row"><span class="actor-avatar">${esc(shortName(a.id).slice(0,1))}</span><div><strong>${esc(actorLabel(a.id))}</strong><small>${esc(a.category.toUpperCase())} / ${esc(a.kind)}</small></div><button data-inhabit="${esc(a.id)}" aria-label="${esc(t("web.ecosystem.inhabit", {id: actorLabel(a.id)}))}">↗</button></div>`).join('');
  const signals=[...Object.values(state.world.capacities).map(r=>({...r,type:t("web.ecosystem.capacity")})),...Object.values(state.world.needs).map(r=>({...r,type:t("matrix.expertise.need")}))];
  return `${banner()}<div class="two-column"><section class="panel network-panel"><div class="panel-title"><h3>${esc(t("web.ecosystem.a_world_in_relation"))}</h3><span>${esc(t("web.ecosystem.actors_agreements", {value: Object.keys(state.world.actors).length, value2: Object.keys(state.world.agreements).length}))}</span></div>${graph()}<div class="legend"><span><i class="declared"></i> ${esc(t("workshop.directory.layers.declared"))}</span><span><i class="agreement"></i> ${esc(t("web.ecosystem.agreement_party"))}</span></div><div class="potential"><p class="eyebrow">${esc(t("web.ecosystem.a_potential_complementarity"))}</p><p>${esc(potential?t("web.ecosystem.offers_what_needs", {source: shortName(potential.source_id), target: shortName(potential.target_id)}):t("web.ecosystem.a_new_possibility_begins_with_a"))}</p><span class="small-label">${potential?esc(potential.domain.toUpperCase())+esc(t("web.ecosystem.inferred_from_reported_capacities")):esc(t("web.ecosystem.no_matches_reported"))}</span><p class="small-label">${esc(t("web.ecosystem.a_potential_connection_is_not_an"))}</p></div></section><section class="panel"><div class="panel-title"><h3>${esc(t("web.ecosystem.the_people_organisations"))}</h3><span>${esc(t("web.ecosystem.inhabit_2"))}</span></div><div class="actor-list">${actors}</div></section></div><div class="section-row"><h3>${esc(t("web.ecosystem.what_we_bring_what_we_need"))}</h3><button class="secondary" data-declare>${esc(t("web.ecosystem.declare_a_signal"))} <span>+</span></button></div><table class="signal-table"><thead><tr><th>${esc(t("web.ecosystem.actor"))}</th><th>${esc(t("web.ecosystem.reported_signal"))}</th><th>${esc(t("web.ecosystem.quantity"))}</th><th>${esc(t("web.ecosystem.knowledge_status"))}</th></tr></thead><tbody>${signals.map(r=>`<tr><td>${esc(shortName(r.actor_id))}</td><td>${esc(r.type)} · ${esc(r.domain)}</td><td>${r.quantity} ${esc(r.unit)}</td><td>${esc(t("web.ecosystem.reported", {value: r.provenance.kind.replaceAll('_',' ').toUpperCase()}))}</td></tr>`).join('')}</tbody></table><div class="objective-note"><span>↗</span><div><h4>${esc(t("web.ecosystem.a_connection_is_a_beginning"))}</h4><p>${esc(t("web.ecosystem.turn_potential_into_an_agreement_a"))}</p></div><button class="secondary" data-mode-go="scenarios">${esc(t("web.ecosystem.enter_the_scenario"))} <span>↗</span></button></div>`;
}
function ledger(){
  return `<section class="panel"><div class="panel-title"><h3>${esc(t("web.history.the_shared_history"))}</h3><span>${esc(t("web.history.commits", {version: state.version}))}</span></div><div class="ledger">${[...state.commits].reverse().slice(0,18).map(entry=>`<div class="ledger-entry"><strong>${esc(entry.commit.id.toUpperCase())}</strong><p>${esc(entry.kind==='world.initialized'?t("web.history.fictional_world_initialised"):`${shortName(entry.actor_id)} · ${names[entry.command?.kind]||entry.command?.kind||entry.kind}`)}</p><details><summary>${esc(t("web.history.inspect_authorisation_state_change"))}</summary><code>${esc(t("web.history.author", {author_id: entry.commit.author_id}))}<br>${esc(t("web.history.action", {value: entry.commit.action_id||t("web.history.scenario_seed")}))}<br>${esc(t("web.history.rule", {rule: entry.commit.authorization.rule}))}<br>${esc(t("web.history.version", {previous_version: entry.commit.previous_version, resulting_version: entry.commit.resulting_version}))}<br>${esc(t("web.history.before", {value: entry.commit.previous_state.slice(0,18)}))}<br>${esc(t("web.history.after", {value: entry.commit.resulting_state.slice(0,18)}))}<br>${esc(entry.commit.timestamp)}</code></details></div>`).join('')}</div><p class="proof-note">${esc(t("web.history.a_commit_records_an_authorised_state"))}</p></section>`;
}
function resources(){return Object.values(state.world.resources).map(resource=>{
  const held=Object.values(state.world.reservations).filter(r=>r.resource_id===resource.id&&r.status==='held').reduce((sum,r)=>sum+r.quantity,0);
  return `<div class="resource-meter"><p><span>${esc(resource.label)}</span><b>${esc(t("web.resources.held_2", {value: held, quantity: resource.quantity}))}</b></p><progress max="${resource.quantity||1}" value="${held}" aria-label="${esc(t("web.resources.reserved_capacity", {label: resource.label}))}"></progress><span class="small-label">${esc(resource.control.toUpperCase())} / ${esc(resource.unit.toUpperCase())}</span></div>`;
}).join('');}
function flow(agreement){
  const steps=[esc(t("web.agreement.lifecycle.proposed")),esc(t("web.agreement.lifecycle.revised")),esc(t("web.agreement.lifecycle.accepted")),esc(t("web.agreement.lifecycle.authorised")),esc(t("web.agreement.lifecycle.active")),esc(t("web.agreement.lifecycle.fulfilled")),esc(t("web.agreement.lifecycle.verified"))];
  const current=agreement.outcome_status==='verified'?6:({draft:0,proposed:0,negotiating:1,accepted:2,authorized:3,active:4,fulfilled:5})[agreement.status]??-1;
  return `<div class="flow" aria-label="${esc(t("web.agreement.lifecycle.agreement_lifecycle"))}">${steps.map((step,i)=>`<span class="${i<current?'done':i===current?'current':''}">${step}</span>`).join('')}</div>`;
}
function editor(agreement=null){
  const proposal=state.world.configuration.world.proposal,v=agreement?currentVersion(agreement):proposal;
  const terms=v.terms,resource=v.resources[0];
  return `<form id="agreement-editor" class="editor" data-editing="${agreement?'amend':'propose'}"><label for="purpose">${esc(t("web.agreement.editor.shared_purpose"))}</label><textarea id="purpose" name="purpose" required>${esc(terms.purpose)}</textarea><label for="conditions">${esc(t("web.agreement.editor.conditions_one_per_line"))}</label><textarea id="conditions" name="conditions" required>${esc(terms.conditions.join('\n'))}</textarea><details><summary>${esc(t("web.agreement.editor.responsibilities_resource_verification_criteria"))}</summary><label for="responsibilities">${esc(t("web.agreement.editor.actor_id_responsibility_one_per_line"))}</label><textarea id="responsibilities" name="responsibilities" required>${esc(terms.responsibilities.map(r=>r.actor_id+' | '+r.description).join('\n'))}</textarea><p>${esc(t("web.agreement.editor.parties_every_party_must_hold_a", {value: proposal.parties.join(', ')}))}</p><label for="quantity">${esc(t("web.agreement.editor.resource_quantity"))}</label><input id="quantity" name="quantity" type="number" min="1" step="1" value="${resource.quantity}" required><p>${esc(t("web.agreement.editor.owned_by", {label: state.world.resources[resource.resource_id].label, owner_id: shortName(state.world.resources[resource.resource_id].owner_id)}))}</p><p>${esc(t("web.agreement.editor.verification_requires", {value: v.verification.criteria.join(' · ')}))}</p><p>${esc(t("web.agreement.editor.valid_until_governance", {valid_until: v.valid_until, label: state.world.governance[v.policy_id].label}))}</p></details><button class="primary" type="submit">${agreement?esc(t("web.agreement.editor.propose_revised_terms")):esc(t("web.agreement.editor.propose_this_agreement"))} <span>↗</span></button></form>`;
}
function nextActions(agreement){
  const v=currentVersion(agreement),party=agreement.parties.includes(actor),policy=state.world.governance[v.policy_id],actions=[];
  const button=(kind,label)=>`<button class="primary" data-command="${kind}">${esc(label)}<span>↗</span></button>`;
  if(['proposed','negotiating','accepted'].includes(agreement.status)&&party&&!v.acceptances[actor])actions.push(button('accept',t("web.agreement.actions.accept_version", {number: v.number})));
  if(['accepted','authorized'].includes(agreement.status)&&policy.eligible_actors.includes(actor)&&!v.authorizations[actor])actions.push(button('authorize',t("web.agreement.actions.authorise_version", {number: v.number})));
  if(agreement.status==='authorized'&&party)actions.push(button('activate',t("web.agreement.actions.activate_reserve_resources")));
  const mine=Object.values(state.world.commitments).find(c=>c.agreement_id===agreement.id&&c.actor_id===actor);
  if(agreement.status==='active'&&mine?.status==='active')actions.push(button('initiate',t("contracts.record_action")));
  if(agreement.status==='active'&&mine?.status==='in_progress')actions.push(button('fulfill',t("web.agreement.actions.report_fulfilment")));
  if(agreement.status==='fulfilled'&&agreement.outcome_status!=='verified'&&v.verification.verifier_ids.includes(actor))actions.push(button('verify',t("web.agreement.actions.verify_the_outcome")));
  if(['draft','proposed','negotiating','accepted','authorized'].includes(agreement.status)&&party)actions.push(`<button class="secondary" data-amend>${esc(t("web.agreement.actions.negotiate_revise_terms"))} <span>↗</span></button>`);
  if(['proposed','negotiating'].includes(agreement.status)&&party)actions.push(`<button class="secondary" data-command="reject">${esc(t("web.agreement.actions.decline_the_agreement"))} <span>×</span></button>`);
  if(['active','suspended','disputed'].includes(agreement.status)&&party)actions.push(`<button class="secondary" data-command="terminate">${esc(t("web.agreement.actions.terminate_release_resources"))} <span>↗</span></button>`);
  return actions.length?actions.join(''):`<p class="waiting">${agreement.outcome_status==='verified'?`${esc(t("web.agreement.actions.a_verified_outcome"))}<br>${esc(t("web.agreement.actions.a_new_collective_possibility"))}`:`${esc(t("web.agreement.actions.this_move_belongs"))}<br>${esc(t("web.agreement.actions.to_another_actor"))}`}</p>`;
}
function guidance(agreement){
  const v=currentVersion(agreement);
  if(agreement.outcome_status==='verified')return t("web.agreement.guidance.the_independent_reviewer_has_verified_the");
  const missing=agreement.parties.filter(id=>!v.acceptances[id]);
  if(missing.length)return t("web.agreement.guidance.review_version_waiting_for_acceptance_from", {number: v.number, value: new Intl.ListFormat(language).format(missing.map(shortName))});
  if(agreement.status==='accepted')return t("web.agreement.guidance.all_parties_accepted_the_same_terms", {label: state.world.governance[v.policy_id].label, value: state.world.governance[v.policy_id].eligible_actors.map(shortName).join(', ')});
  if(agreement.status==='authorized')return t("web.agreement.guidance.a_party_may_now_activate_the");
  if(agreement.status==='active')return t("web.agreement.guidance.each_responsible_party_records_its_action");
  if(agreement.status==='fulfilled')return t("web.agreement.guidance.delivery_is_reported_but_remains_unverified", {value: v.verification.verifier_ids.map(shortName).join(', ')});
  return t("web.agreement.guidance.agreement_is_its_recorded_history_remains", {status: agreement.status});
}
function evidencePanel(agreement){
  const records=agreement.evidence_ids.map(id=>state.world.evidence[id]).filter(Boolean);
  if(!records.length)return '';
  return `<div class="agreement-terms"><h4>${esc(t("web.agreement.evidence.actions_evidence_to_review"))}</h4>${records.map(record=>`<div class="commitment"><strong>${esc(shortName(record.submitted_by))}</strong> ${tag(record.kind.replaceAll('_',' ').toUpperCase(),record.status==='verified')}<p>${esc(record.reference)}</p>${record.criteria?`<p class="small-label">${esc(t("web.agreement.evidence.criteria", {value: record.criteria.map(esc).join(' · ')}))}</p>`:''}<span class="small-label">${esc(record.id)} / ${esc(record.action_id)}</span></div>`).join('')}</div>`;
}
function agreementPanel(){
  const agreement=currentAgreement();
  if(!agreement)return `<section class="panel"><div class="panel-title"><h3>${esc(t("web.agreement.step_01_propose_a_shared_undertaking"))}</h3>${tag(t("web.agreement.no_commitment_yet"))}</div><h3 class="agreement-title">${esc(t("web.agreement.a_possibility_becomes"))}<br>${esc(t("web.agreement.an_agreement"))}</h3><p class="agreement-desc">${esc(t("web.agreement.review_and_change_these_proposed_terms"))}</p>${editor()}</section>`;
  const v=currentVersion(agreement),commitments=Object.values(state.world.commitments).filter(c=>c.agreement_id===agreement.id);
  return `<section class="panel"><div class="panel-title"><h3>${esc(t("web.agreement.the_agreement_version", {number: v.number}))}</h3>${tag(agreement.outcome_status==='verified'?t("web.agreement.verified_outcome"):agreement.status.toUpperCase(),agreement.outcome_status==='verified')}</div><h3 class="agreement-title">${esc(agreement.label)}</h3>${flow(agreement)}<div class="agreement-meta">${tag(t("web.agreement.parties", {value: agreement.parties.length}))}${tag(esc(t("web.agreement.local_approvals_no_cryptographic_signature")))}</div><p class="agreement-desc">${esc(v.terms.purpose)}</p><div class="party-receipts">${agreement.parties.map(id=>`<span class="${v.acceptances[id]?'received':''}">${v.acceptances[id]?'✓':'○'} ${esc(shortName(id))} · V${v.number}</span>`).join('')}</div><div class="agreement-terms"><h4>${esc(t("web.agreement.what_we_undertake"))}</h4>${v.terms.responsibilities.map(r=>`<div class="responsibility"><b>${esc(shortName(r.actor_id))}</b><span>${esc(r.description)}</span></div>`).join('')}<h4>${esc(t("web.agreement.conditions"))}</h4><ul>${v.terms.conditions.map(c=>`<li>${esc(c)}</li>`).join('')}</ul><h4>${esc(t("web.agreement.authorisation"))}</h4><p>${esc(state.world.governance[v.policy_id].label)}</p><p class="small-label">${esc(t("web.agreement.recorded_approvers", {value: Object.keys(v.authorizations).map(id=>esc(shortName(id))).join(', ')||esc(t("web.agreement.none_yet"))}))}</p></div><div class="action-stack">${nextActions(agreement)}</div><p class="hint">${esc(guidance(agreement))}</p><div id="amend-editor" hidden>${editor(agreement)}</div>${commitments.length?`<div class="agreement-terms"><h4>${esc(t("web.agreement.responsibilities_not_transaction_commits"))}</h4>${commitments.map(c=>`<div class="commitment">${esc(shortName(c.actor_id))} ${tag(c.status.toUpperCase(),c.status==='verified')}<p>${esc(c.responsibility)}</p></div>`).join('')}</div>`:''}${evidencePanel(agreement)}${resources()}<details class="version-details"><summary>${esc(t("web.agreement.inspect_version_s_approvals_evidence", {value: agreement.versions.length}))}</summary><pre>${esc(JSON.stringify({versions:agreement.versions,evidence_ids:agreement.evidence_ids},null,2))}</pre></details></section>`;
}
function scenarios(){return `${banner()}<div class="agreement-layout">${agreementPanel()}<div>${ledger()}<p class="hint">${esc(t("web.agreement.accepted_commitment_verified_fulfilment"))}<br>${esc(t("web.agreement.suggestion_authorisation_commit"))}</p></div></div>`;}
function gathering(){
  const objective=Object.values(state.world.objectives).find(o=>o.mode==='gathering');
  if(!objective)return `${banner()}<div class="two-column"><section class="panel"><div class="gathering-art"><div class="assembly-symbol"></div></div><p class="eyebrow">${esc(t("web.gathering.a_mode_of_collective_formation"))}</p><h3 class="agreement-title">${esc(t("web.gathering.a_collective_does_not"))}<br>${esc(t("web.gathering.appear_by_declaration"))}</h3><p class="agreement-desc">${esc(t("web.gathering.invite_participants_obtain_their_consent_agree"))}</p><p class="hint">${esc(t("web.gathering.gathering_has_its_own_objective_and"))}</p><button class="primary" data-open-gathering>${esc(t("web.gathering.open_the_gathering_world"))} <span>↗</span></button></section>${ledger()}</div>`;
  const invitations=Object.values(state.world.relationships).filter(r=>r.kind==='invited');
  const eligible=state.world.configuration.world.proposal.parties.filter(id=>id!==actor&&!invitations.some(r=>r.source_id===actor&&r.target_id===id));
  return `${banner()}<div class="two-column"><section class="panel"><div class="panel-title"><h3>${esc(t("web.gathering.the_assembly_consent_to_gather"))}</h3>${tag(objective.status.toUpperCase(),objective.status==='verified')}</div><div class="gathering-art"><div class="assembly-symbol"></div></div><h3 class="agreement-title">${esc(t("web.gathering.make_room_for"))}<br>${esc(t("web.gathering.the_collective"))}</h3><p class="agreement-desc">${esc(t("web.gathering.the_room_can_be_reserved_only"))}</p>${eligible.map(id=>`<div class="invitation"><span>${esc(actorLabel(id))}</span><button class="secondary" data-invite="${esc(id)}">${esc(t("web.gathering.invite"))}</button></div>`).join('')}${invitations.map(r=>`<div class="invitation"><span>${esc(shortName(r.source_id))} → ${esc(shortName(r.target_id))}<br>${tag(r.status.toUpperCase(),r.status==='accepted')}</span>${r.target_id===actor&&r.status==='proposed'?`<button class="secondary" data-rsvp="${esc(r.id)}" data-response="accept">${esc(t("web.gathering.accept"))}</button><button class="secondary" data-rsvp="${esc(r.id)}" data-response="decline">${esc(t("web.gathering.decline"))}</button>`:''}</div>`).join('')}<div class="objective-note"><div><h4>${esc(t("web.gathering.consent_creates_a_possibility"))}</h4><p>${esc(t("web.gathering.the_assembly_still_needs_an_authorised"))}</p></div><button class="secondary" data-mode-go="scenarios">${esc(t("web.gathering.agree_the_next_step"))}</button></div></section>${ledger()}</div>`;
}
function render(){
  if(!state)return;
  $('#mode-kicker').textContent=labels[mode][0];$('#page-title').innerHTML=labels[mode][1];
  $('#content').innerHTML=mode==='ecosystem'?ecosystem():mode==='scenarios'?scenarios():gathering();
  $('#actor').innerHTML=Object.values(state.world.actors).map(a=>`<option value="${esc(a.id)}"${a.id===actor?' selected':''}>${esc(actorLabel(a.id))}</option>`).join('');
  $('#actor-description').textContent=state.world.actors[actor]?.roles.join(' · ')||'';
  document.querySelectorAll('[data-inhabit]').forEach(button=>button.onclick=()=>chooseActor(button.dataset.inhabit).catch(e=>toast(e.message)));
  document.querySelectorAll('[data-mode-go]').forEach(button=>button.onclick=()=>setMode(button.dataset.modeGo));
  document.querySelectorAll('[data-command]').forEach(button=>button.onclick=()=>prepareAction(button.dataset.command));
  document.querySelectorAll('[data-invite]').forEach(button=>button.onclick=()=>command({kind:'invite',recipient_id:button.dataset.invite,objective_id:'objective-main'}));
  document.querySelectorAll('[data-rsvp]').forEach(button=>button.onclick=()=>command({kind:'respond_invitation',invitation_id:button.dataset.rsvp,response:button.dataset.response}));
  const amend=$('[data-amend]');if(amend)amend.onclick=()=>{$('#amend-editor').hidden=!$('#amend-editor').hidden;$('#amend-editor textarea')?.focus();};
  const form=$('#agreement-editor');if(form)form.onsubmit=submitTerms;
  const gatheringButton=$('[data-open-gathering]');if(gatheringButton)gatheringButton.onclick=()=>switchScenario('commons-gathering',true);
  const declare=$('[data-declare]');if(declare)declare.onclick=prepareDeclaration;
}
async function submitTerms(event){
  event.preventDefault();const form=event.currentTarget,fields=new FormData(form),base=state.world.configuration.world.proposal;
  try{
    const responsibilities=String(fields.get('responsibilities')).split('\n').filter(x=>x.trim()).map(line=>{
      const split=line.indexOf('|');if(split<1)throw Error(t("web.agreement.editor.use_actor_id_responsibility_on_every"));
      return {actor_id:line.slice(0,split).trim(),description:line.slice(split+1).trim()};
    });
    const terms={purpose:fields.get('purpose'),conditions:String(fields.get('conditions')).split('\n').filter(x=>x.trim()),responsibilities};
    const resources=[{resource_id:base.resources[0].resource_id,quantity:Number(fields.get('quantity'))}];
    if(form.dataset.editing==='amend')await command({kind:'amend',agreement_id:currentAgreement().id,version:currentAgreement().current_version,terms,resources});
    else await command({kind:'propose',...base,terms,resources});
  }catch(error){toast(error.message);}
}
function prepareAction(kind){
  const agreement=currentAgreement(),v=currentVersion(agreement);
  pending={kind,agreement_id:agreement.id,version:v.number};
  const titles={accept:t("web.agreement.actions.accept_version", {number: v.number}),authorize:t("web.agreement.actions.authorise_version", {number: v.number}),activate:t("web.action.activate_this_agreement"),initiate:t("contracts.record_action"),fulfill:t("web.agreement.actions.report_fulfilment"),verify:t("contracts.actions.verify"),reject:t("web.action.decline_this_agreement"),terminate:t("web.action.terminate_the_agreement")};
  $('#action-title').textContent=titles[kind];$('#dialog-error').textContent='';
  $('#action-description').textContent=kind==='authorize'?t("web.action.you_are_your_approval_will_apply", {value: actorLabel(actor)}):kind==='verify'?t("web.action.confirm_that_you_have_reviewed_the"):kind==='accept'?t("web.action.you_are_acceptance_records_your_undertaking", {value: actorLabel(actor), number: v.number}):kind==='activate'?t("web.action.the_engine_will_check_the_approvals"):kind==='fulfill'?t("web.action.describe_the_delivered_work_and_reference"):t("web.action.describe_the_concrete_action_or_reason");
  const ref=['initiate','fulfill','verify'].includes(kind),reason=['reject','terminate'].includes(kind);
  $('#action-fields').innerHTML=(kind==='fulfill'?v.verification.criteria.map(c=>`<label class="criterion"><input type="checkbox" name="criterion" value="${esc(c)}" required><span>${esc(c)}</span></label>`).join(''):'')+
    (ref?`<label>${esc(t("web.action.evidence_reference_or_action_note"))}<textarea name="reference" class="form-field" required placeholder="${esc(t("web.action.describe_the_synthetic_action_and_where"))}"></textarea></label>`:'')+
    (reason?`<label>${esc(t("forms.reason"))}<textarea name="reason" class="form-field" required></textarea></label>`:'');
  $('#action-dialog').showModal();
}
function prepareDeclaration(){
  pending={kind:'declare'};$('#action-title').textContent=t("web.declaration.declare_a_capacity_or_a_need");$('#dialog-error').textContent='';
  $('#action-description').textContent=t("web.declaration.this_updates_what_the_collective_knows");
  $('#action-fields').innerHTML=`<label>${esc(t("web.declaration.signal"))}<select name="table" class="form-field"><option value="capacities">${esc(t("web.declaration.i_can_offer"))}</option><option value="needs">${esc(t("web.declaration.i_need"))}</option></select></label><label>${esc(t("web.forms.domain"))}<input class="form-field" name="domain" required placeholder="${esc(t("web.declaration.for_example_digital_commons"))}"></label><label>${esc(t("web.forms.quantity"))}<input class="form-field" name="quantity" type="number" min="1" step="1" value="1" required></label><label>${esc(t("web.forms.unit"))}<input class="form-field" name="unit" required placeholder="${esc(t("web.declaration.for_example_session"))}"></label>`;
  $('#action-dialog').showModal();
}
$('#action-form').onsubmit=async event=>{
  event.preventDefault();const data=new FormData(event.currentTarget);let payload={...pending};
  if(pending.kind==='declare')payload={kind:'declare',table:data.get('table'),record:{domain:data.get('domain'),quantity:Number(data.get('quantity')),unit:data.get('unit')}};
  else{if(data.has('reference'))payload.reference=data.get('reference');if(data.has('reason'))payload.reason=data.get('reason');if(pending.kind==='fulfill')payload.criteria=data.getAll('criterion');}
  if(await command(payload))$('#action-dialog').close();else $('#dialog-error').textContent=t("web.declaration.the_action_was_rejected_review_the");
};
async function switchScenario(next,gather=false){
  scenario=next;state=null;csrf=null;sessionToken=null;actor='researcher';$('#scenario').value=next;
  await refresh(true);if(state)await chooseActor(actor);if(gather)setMode('gathering');
}
$('#scenario').onchange=event=>switchScenario(event.target.value).catch(e=>toast(e.message));
$('#actor').onchange=event=>chooseActor(event.target.value).catch(e=>toast(e.message));
document.querySelectorAll('.mode').forEach(button=>button.onclick=()=>setMode(button.dataset.mode));
$('#close-dialog').onclick=()=>$('#action-dialog').close();
$('#read-principles').onclick=()=>$('#principles').showModal();$('#close-principles').onclick=()=>$('#principles').close();
function syncSound(){$('#sound-toggle').textContent=music.playing?t("web.audio.on"):t("web.audio.off");$('#sound-toggle').setAttribute('aria-pressed',String(music.playing));}
async function sound(){try{await music.toggle();syncSound();}catch {
  toast(t("web.audio.unavailable"));
}}
$('#sound-toggle').onclick=sound;
function declare(){ $('#invitation').hidden=true;$('#declaration').hidden=false; }
$('#enter-sound').onclick=async()=>{declare();await sound();};$('#enter-quiet').onclick=declare;
$('#begin').onclick=()=>{$('#intro').hidden=true;$('#application').hidden=false;window.scrollTo(0,0);$('#main').focus({preventScroll:true});};
$('#return-intro').onclick=event=>{event.preventDefault();$('#application').hidden=true;$('#intro').hidden=false;$('#invitation').hidden=false;$('#declaration').hidden=true;};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&music.playing){music.stop();syncSound();}});

// Optional visual field. It has no connection to the authoritative transition rules.
const canvas=$('#field'),ctx=canvas.getContext('2d'),reduced=matchMedia('(prefers-reduced-motion: reduce)'),start=performance.now();
let frame;
function draw(now){
  const rect=canvas.getBoundingClientRect(),ratio=Math.min(devicePixelRatio||1,2),w=rect.width,h=rect.height;
  if(w&&h){if(canvas.width!==Math.round(w*ratio)||canvas.height!==Math.round(h*ratio)){canvas.width=w*ratio;canvas.height=h*ratio;}
    ctx.setTransform(ratio,0,0,ratio,0,0);ctx.fillStyle='#101a15';ctx.fillRect(0,0,w,h);
    const t=reduced.matches?0:(now-start)/1000,cx=w*.78,cy=h*.45,scale=Math.min(w,h)*.57;
    const glow=ctx.createRadialGradient(cx,cy,10,cx,cy,scale*1.2);glow.addColorStop(0,'#6d71472a');glow.addColorStop(.6,'#6c52351c');glow.addColorStop(1,'#101a1500');ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
    ctx.save();ctx.translate(cx,cy);ctx.rotate(-.28+Math.sin(t*.05)*.05);
    for(let ring=0;ring<68;ring++){
      const r=scale*(.07+ring/68*.95),phase=ring*.085+t*.065;
      ctx.beginPath();for(let step=0;step<=240;step++){
        const theta=step/240*Math.PI*2,wave=Math.sin(theta*3+phase)*.09+Math.cos(theta*5-phase*.5)*.055;
        const x=Math.cos(theta)*r*(1+wave),y=Math.sin(theta)*r*(.83+Math.sin(theta*2+phase)*.095);
        if(!step)ctx.moveTo(x,y);else ctx.lineTo(x,y);
      }
      const hue=ring<30?80+ring*.4:20+(ring-30)*1.7;
      ctx.strokeStyle=`hsla(${hue},${ring%4===0?49:29}%,${40+ring*.28}%,${.20+(ring%5)*.065})`;ctx.lineWidth=.65;ctx.stroke();
    }
    ctx.restore();
    for(let i=0;i<45;i++){const x=(Math.sin(i*127.1)*.5+.5)*w,y=(Math.sin(i*311.7)*.5+.5)*h;ctx.fillStyle='#d1e9a633';ctx.fillRect(x,y,1,1);}
  }
  if(!reduced.matches)frame=requestAnimationFrame(draw);
}
draw(performance.now());reduced.addEventListener('change',()=>{cancelAnimationFrame(frame);draw(performance.now());});
setInterval(()=>{if(!document.hidden&&!busy&&!$('#action-dialog').open&&!document.activeElement?.closest('.editor'))refresh();},5000);
await refresh(true);if(state)await chooseActor(actor);
