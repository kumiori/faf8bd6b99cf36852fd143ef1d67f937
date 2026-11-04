import {MidiMusic} from './music.js';

const $=selector=>document.querySelector(selector);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const music=new MidiMusic();
let state=null,mode='ecosystem',scenario='bilateral-logs',actor='researcher',csrf=null,sessionToken=null,pending=null,busy=false,toastTimer;
const labels={ecosystem:['01 / ECOSYSTEM','Who can act<br><em>together?</em>'],scenarios:['02 / SCENARIOS','What can we<br><em>make possible?</em>'],gathering:['03 / GATHERING','How does a collective<br><em>come into being?</em>']};
const names={propose:'Agreement proposed',amend:'Terms revised',accept:'Version accepted',authorize:'Approval recorded',activate:'Resources reserved',initiate:'Action initiated',fulfill:'Fulfilment reported',verify:'Outcome verified',invite:'Invitation recorded',respond_invitation:'Invitation answered'};
const errorText={missing_authorization:'Institutional or collective authorisation is still missing.',agreement_version_conflict:'These terms have changed. Review the latest version.',resource_overcommitment:'That resource is already reserved. No state was changed.',stale_version:'The shared world changed. Review it and try again.',unauthorized_approval:'This actor is not an eligible authoriser.',independent_verifier_required:'A party cannot independently verify its own outcome.',unauthorized_verifier:'Choose the designated independent reviewer.',gathering_attendance_required:'The gathering needs three consenting participants.',invalid_transition:'This action is not available at the current lifecycle stage.',already_accepted:'This actor has already accepted this version.',session_required:'Choose your actor again to renew this local session.'};
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
  if(!result.ok)throw Error(errorText[result.errors?.[0]]||result.errors?.join(', ')||'The engine could not complete this request.');
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
    state=next;$('#world-version').textContent=`SHARED WORLD / COMMIT ${String(state.version).padStart(3,'0')}`;
    $('#connection-error').hidden=true;
    if(force||changed)render();
  }catch(error){$('#connection-error').textContent='Engine connection: '+error.message;$('#connection-error').hidden=false;}
}
async function command(payload){
  if(busy)return false;busy=true;
  document.querySelectorAll('[data-command],#action-form button[type="submit"]').forEach(button=>button.disabled=true);
  try{
    const result=await api('/api/command',{scenario,expected_version:state.version,command:{key:crypto.randomUUID(),...payload}});
    await refresh(true);toast(`${names[payload.kind]||'World changed'} · ${result.commit_id}`);return true;
  }catch(error){toast(error.message);await refresh(true);return false;}
  finally{busy=false;document.querySelectorAll('[data-command],#action-form button[type="submit"]').forEach(button=>button.disabled=false);}
}
function setMode(next){mode=next;document.querySelectorAll('.mode').forEach(button=>{
  button.classList.toggle('active',button.dataset.mode===mode);if(button.dataset.mode===mode)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');
});render();}
function banner(){const world=state.world.configuration.world;return `<div class="experiment-banner"><div><h3>${esc(world.title)}</h3><p>${esc(world.description)}</p></div>${tag('SYNTHETIC WORLD')}</div>`;}

function graph(){
  const actors=Object.values(state.world.actors),center={x:235,y:148},rx=155,ry=104;
  const positions=Object.fromEntries(actors.map((a,i)=>[a.id,{x:center.x+Math.cos(i/actors.length*Math.PI*2-Math.PI/2)*rx,y:center.y+Math.sin(i/actors.length*Math.PI*2-Math.PI/2)*ry}]));
  const agreement=currentAgreement();let lines='';
  for(const edge of state.world.relationships?Object.values(state.world.relationships):[]){
    const from=positions[edge.source_id],to=positions[edge.target_id];if(from&&to)lines+=`<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke-dasharray="3 5"/>`;
  }
  if(agreement)for(const party of agreement.parties){const p=positions[party];lines+=`<line class="agreement" x1="${p.x}" y1="${p.y}" x2="${center.x}" y2="${center.y}"/>`;}
  const nodes=actors.map(a=>{const p=positions[a.id];return `<g><circle class="actor" cx="${p.x}" cy="${p.y}" r="17"/><text x="${p.x}" y="${p.y+3}" text-anchor="middle">${esc(shortName(a.id).slice(0,1))}</text><text x="${p.x}" y="${p.y+33}" text-anchor="middle">${esc(shortName(a.id))}</text></g>`;}).join('');
  const middle=agreement?`<circle class="agreement" cx="235" cy="148" r="34"/><text class="center" x="235" y="145">AGREEMENT</text><text class="center" x="235" y="160">V${agreement.current_version}</text>`:`<circle cx="235" cy="148" r="37" fill="none" stroke="#a7b88f" stroke-dasharray="2 6"/><text x="235" y="151" text-anchor="middle">POSSIBILITY</text>`;
  return `<svg viewBox="0 0 470 310" class="network" role="img" aria-label="Declared relationships and agreement parties in the fictional ecosystem">${lines}${middle}${nodes}</svg>`;
}
function ecosystem(){
  const potential=state.possibilities[0];
  const actors=Object.values(state.world.actors).map(a=>`<div class="actor-row"><span class="actor-avatar">${esc(shortName(a.id).slice(0,1))}</span><div><strong>${esc(actorLabel(a.id))}</strong><small>${esc(a.category.toUpperCase())} / ${esc(a.kind)}</small></div><button data-inhabit="${esc(a.id)}" aria-label="Inhabit ${esc(actorLabel(a.id))}">↗</button></div>`).join('');
  const signals=[...Object.values(state.world.capacities).map(r=>({...r,type:'CAPACITY'})),...Object.values(state.world.needs).map(r=>({...r,type:'NEED'}))];
  return `${banner()}<div class="two-column"><section class="panel network-panel"><div class="panel-title"><h3>A WORLD IN RELATION</h3><span>${Object.keys(state.world.actors).length} ACTORS / ${Object.keys(state.world.agreements).length} AGREEMENTS</span></div>${graph()}<div class="legend"><span><i class="declared"></i> Declared relationship</span><span><i class="agreement"></i> Agreement party</span></div><div class="potential"><p class="eyebrow">A POTENTIAL COMPLEMENTARITY</p><p>${potential?`${esc(shortName(potential.source_id))} offers what ${esc(shortName(potential.target_id))} needs.`:'A new possibility begins with a capacity or a need.'}</p><span class="small-label">${potential?esc(potential.domain.toUpperCase())+' / INFERRED FROM REPORTED CAPACITIES':'NO MATCHES REPORTED'}</span><p class="small-label">A potential connection is not an accepted collaboration.</p></div></section><section class="panel"><div class="panel-title"><h3>THE PEOPLE & ORGANISATIONS</h3><span>INHABIT ↗</span></div><div class="actor-list">${actors}</div></section></div><div class="section-row"><h3>What we bring. What we need.</h3><button class="secondary" data-declare>Declare a signal <span>+</span></button></div><table class="signal-table"><thead><tr><th>ACTOR</th><th>REPORTED SIGNAL</th><th>QUANTITY</th><th>KNOWLEDGE STATUS</th></tr></thead><tbody>${signals.map(r=>`<tr><td>${esc(shortName(r.actor_id))}</td><td>${esc(r.type)} · ${esc(r.domain)}</td><td>${r.quantity} ${esc(r.unit)}</td><td>REPORTED / ${esc(r.provenance.kind.replaceAll('_',' ').toUpperCase())}</td></tr>`).join('')}</tbody></table><div class="objective-note"><span>↗</span><div><h4>A connection is a beginning.</h4><p>Turn potential into an agreement, a responsibility, and an inspectable outcome.</p></div><button class="secondary" data-mode-go="scenarios">Enter the scenario <span>↗</span></button></div>`;
}
function ledger(){
  return `<section class="panel"><div class="panel-title"><h3>THE SHARED HISTORY</h3><span>${state.version} COMMITS</span></div><div class="ledger">${[...state.commits].reverse().slice(0,18).map(entry=>`<div class="ledger-entry"><strong>${esc(entry.commit.id.toUpperCase())}</strong><p>${esc(entry.kind==='world.initialized'?'Fictional world initialised':`${shortName(entry.actor_id)} · ${names[entry.command?.kind]||entry.command?.kind||entry.kind}`)}</p><details><summary>Inspect authorisation & state change</summary><code>Author: ${esc(entry.commit.author_id)}<br>Action: ${esc(entry.commit.action_id||'scenario seed')}<br>Rule: ${esc(entry.commit.authorization.rule)}<br>Version: ${entry.commit.previous_version} → ${entry.commit.resulting_version}<br>Before: ${esc(entry.commit.previous_state.slice(0,18))}…<br>After: ${esc(entry.commit.resulting_state.slice(0,18))}…<br>${esc(entry.commit.timestamp)}</code></details></div>`).join('')}</div><p class="proof-note">A commit records an authorised state change. It does not, by itself, establish successful real-world execution.</p></section>`;
}
function resources(){return Object.values(state.world.resources).map(resource=>{
  const held=Object.values(state.world.reservations).filter(r=>r.resource_id===resource.id&&r.status==='held').reduce((sum,r)=>sum+r.quantity,0);
  return `<div class="resource-meter"><p><span>${esc(resource.label)}</span><b>${held}/${resource.quantity} held</b></p><progress max="${resource.quantity||1}" value="${held}" aria-label="${esc(resource.label)} reserved capacity"></progress><span class="small-label">${esc(resource.control.toUpperCase())} / ${esc(resource.unit.toUpperCase())}</span></div>`;
}).join('');}
function flow(agreement){
  const steps=['Proposed','Revised','Accepted','Authorised','Active','Fulfilled','Verified'];
  const current=agreement.outcome_status==='verified'?6:({draft:0,proposed:0,negotiating:1,accepted:2,authorized:3,active:4,fulfilled:5})[agreement.status]??-1;
  return `<div class="flow" aria-label="Agreement lifecycle">${steps.map((step,i)=>`<span class="${i<current?'done':i===current?'current':''}">${step}</span>`).join('')}</div>`;
}
function editor(agreement=null){
  const proposal=state.world.configuration.world.proposal,v=agreement?currentVersion(agreement):proposal;
  const terms=v.terms,resource=v.resources[0];
  return `<form id="agreement-editor" class="editor" data-editing="${agreement?'amend':'propose'}"><label for="purpose">SHARED PURPOSE</label><textarea id="purpose" name="purpose" required>${esc(terms.purpose)}</textarea><label for="conditions">CONDITIONS · ONE PER LINE</label><textarea id="conditions" name="conditions" required>${esc(terms.conditions.join('\n'))}</textarea><details><summary>Responsibilities, resource & verification criteria</summary><label for="responsibilities">ACTOR ID | RESPONSIBILITY · ONE PER LINE</label><textarea id="responsibilities" name="responsibilities" required>${esc(terms.responsibilities.map(r=>r.actor_id+' | '+r.description).join('\n'))}</textarea><p>Parties: ${proposal.parties.map(esc).join(', ')}. Every party must hold a responsibility.</p><label for="quantity">RESOURCE QUANTITY</label><input id="quantity" name="quantity" type="number" min="1" step="1" value="${resource.quantity}" required><p>${esc(state.world.resources[resource.resource_id].label)} · owned by ${esc(shortName(state.world.resources[resource.resource_id].owner_id))}</p><p>Verification requires: ${v.verification.criteria.map(esc).join(' · ')}</p><p>Valid until: ${esc(v.valid_until)}. Governance: ${esc(state.world.governance[v.policy_id].label)}.</p></details><button class="primary" type="submit">${agreement?'Propose revised terms':'Propose this agreement'} <span>↗</span></button></form>`;
}
function nextActions(agreement){
  const v=currentVersion(agreement),party=agreement.parties.includes(actor),policy=state.world.governance[v.policy_id],actions=[];
  const button=(kind,label)=>`<button class="primary" data-command="${kind}">${label}<span>↗</span></button>`;
  if(['proposed','negotiating','accepted'].includes(agreement.status)&&party&&!v.acceptances[actor])actions.push(button('accept',`Accept version ${v.number}`));
  if(['accepted','authorized'].includes(agreement.status)&&policy.eligible_actors.includes(actor)&&!v.authorizations[actor])actions.push(button('authorize',`Authorise version ${v.number}`));
  if(agreement.status==='authorized'&&party)actions.push(button('activate','Activate & reserve resources'));
  const mine=Object.values(state.world.commitments).find(c=>c.agreement_id===agreement.id&&c.actor_id===actor);
  if(agreement.status==='active'&&mine?.status==='active')actions.push(button('initiate','Record a concrete action'));
  if(agreement.status==='active'&&mine?.status==='in_progress')actions.push(button('fulfill','Report fulfilment'));
  if(agreement.status==='fulfilled'&&agreement.outcome_status!=='verified'&&v.verification.verifier_ids.includes(actor))actions.push(button('verify','Verify the outcome'));
  if(['draft','proposed','negotiating','accepted','authorized'].includes(agreement.status)&&party)actions.push('<button class="secondary" data-amend>Negotiate / revise terms <span>↗</span></button>');
  if(['proposed','negotiating'].includes(agreement.status)&&party)actions.push('<button class="secondary" data-command="reject">Decline the agreement <span>×</span></button>');
  if(['active','suspended','disputed'].includes(agreement.status)&&party)actions.push('<button class="secondary" data-command="terminate">Terminate & release resources <span>↗</span></button>');
  return actions.length?actions.join(''):`<p class="waiting">${agreement.outcome_status==='verified'?'A verified outcome.<br>A new collective possibility.':'This move belongs<br>to another actor.'}</p>`;
}
function guidance(agreement){
  const v=currentVersion(agreement);
  if(agreement.outcome_status==='verified')return 'The independent reviewer has verified the agreed criteria. The objective is supported by evidence and the resource reservation is released.';
  const missing=agreement.parties.filter(id=>!v.acceptances[id]);
  if(missing.length)return `Review version ${v.number}. Waiting for acceptance from ${missing.map(shortName).join(' and ')}. Change actor using the local hot-seat selector.`;
  if(agreement.status==='accepted')return `All parties accepted the same terms. Authorisation remains separate: ${state.world.governance[v.policy_id].label}. Eligible approvers: ${state.world.governance[v.policy_id].eligible_actors.map(shortName).join(', ')}.`;
  if(agreement.status==='authorized')return 'A party may now activate the agreement. The engine will check and reserve every requested resource atomically.';
  if(agreement.status==='active')return 'Each responsible party records its action, then reports fulfilment with evidence for every agreed criterion. A promise alone does not complete the objective.';
  if(agreement.status==='fulfilled')return `Delivery is reported, but remains unverified. ${v.verification.verifier_ids.map(shortName).join(', ')} must independently review the outcome.`;
  return `Agreement is ${agreement.status}. Its recorded history remains available.`;
}
function evidencePanel(agreement){
  const records=agreement.evidence_ids.map(id=>state.world.evidence[id]).filter(Boolean);
  if(!records.length)return '';
  return `<div class="agreement-terms"><h4>ACTIONS & EVIDENCE TO REVIEW</h4>${records.map(record=>`<div class="commitment"><strong>${esc(shortName(record.submitted_by))}</strong> ${tag(record.kind.replaceAll('_',' ').toUpperCase(),record.status==='verified')}<p>${esc(record.reference)}</p>${record.criteria?`<p class="small-label">CRITERIA: ${record.criteria.map(esc).join(' · ')}</p>`:''}<span class="small-label">${esc(record.id)} / ${esc(record.action_id)}</span></div>`).join('')}</div>`;
}
function agreementPanel(){
  const agreement=currentAgreement();
  if(!agreement)return `<section class="panel"><div class="panel-title"><h3>01 / PROPOSE A SHARED UNDERTAKING</h3>${tag('NO COMMITMENT YET')}</div><h3 class="agreement-title">A possibility becomes<br>an agreement.</h3><p class="agreement-desc">Review and change these proposed terms. Each party must accept the same version; institutional authorisation comes afterwards.</p>${editor()}</section>`;
  const v=currentVersion(agreement),commitments=Object.values(state.world.commitments).filter(c=>c.agreement_id===agreement.id);
  return `<section class="panel"><div class="panel-title"><h3>THE AGREEMENT / VERSION ${v.number}</h3>${tag(agreement.outcome_status==='verified'?'VERIFIED OUTCOME':agreement.status.toUpperCase(),agreement.outcome_status==='verified')}</div><h3 class="agreement-title">${esc(agreement.label)}</h3>${flow(agreement)}<div class="agreement-meta">${tag(`${agreement.parties.length} PARTIES`)}${tag('LOCAL APPROVALS · NO CRYPTOGRAPHIC SIGNATURE')}</div><p class="agreement-desc">${esc(v.terms.purpose)}</p><div class="party-receipts">${agreement.parties.map(id=>`<span class="${v.acceptances[id]?'received':''}">${v.acceptances[id]?'✓':'○'} ${esc(shortName(id))} · V${v.number}</span>`).join('')}</div><div class="agreement-terms"><h4>WHAT WE UNDERTAKE</h4>${v.terms.responsibilities.map(r=>`<div class="responsibility"><b>${esc(shortName(r.actor_id))}</b><span>${esc(r.description)}</span></div>`).join('')}<h4>CONDITIONS</h4><ul>${v.terms.conditions.map(c=>`<li>${esc(c)}</li>`).join('')}</ul><h4>AUTHORISATION</h4><p>${esc(state.world.governance[v.policy_id].label)}</p><p class="small-label">RECORDED APPROVERS: ${Object.keys(v.authorizations).map(id=>esc(shortName(id))).join(', ')||'NONE YET'}</p></div><div class="action-stack">${nextActions(agreement)}</div><p class="hint">${esc(guidance(agreement))}</p><div id="amend-editor" hidden>${editor(agreement)}</div>${commitments.length?`<div class="agreement-terms"><h4>RESPONSIBILITIES, NOT TRANSACTION COMMITS</h4>${commitments.map(c=>`<div class="commitment">${esc(shortName(c.actor_id))} ${tag(c.status.toUpperCase(),c.status==='verified')}<p>${esc(c.responsibility)}</p></div>`).join('')}</div>`:''}${evidencePanel(agreement)}${resources()}<details class="version-details"><summary>Inspect ${agreement.versions.length} version(s), approvals & evidence</summary><pre>${esc(JSON.stringify({versions:agreement.versions,evidence_ids:agreement.evidence_ids},null,2))}</pre></details></section>`;
}
function scenarios(){return `${banner()}<div class="agreement-layout">${agreementPanel()}<div>${ledger()}<p class="hint">Accepted commitment ≠ verified fulfilment.<br>Suggestion ≠ authorisation ≠ commit.</p></div></div>`;}
function gathering(){
  const objective=Object.values(state.world.objectives).find(o=>o.mode==='gathering');
  if(!objective)return `${banner()}<div class="two-column"><section class="panel"><div class="gathering-art"><div class="assembly-symbol"></div></div><p class="eyebrow">A MODE OF COLLECTIVE FORMATION</p><h3 class="agreement-title">A collective does not<br>appear by declaration.</h3><p class="agreement-desc">Invite participants. Obtain their consent. Agree facilitation, hospitality and documentation. Reserve a room, hold the assembly, and record what follows.</p><p class="hint">Gathering has its own objective and attendance constraint. It uses the same agreement, authorisation, resource and evidence primitives.</p><button class="primary" data-open-gathering>Open the gathering world <span>↗</span></button></section>${ledger()}</div>`;
  const invitations=Object.values(state.world.relationships).filter(r=>r.kind==='invited');
  const eligible=state.world.configuration.world.proposal.parties.filter(id=>id!==actor&&!invitations.some(r=>r.source_id===actor&&r.target_id===id));
  return `${banner()}<div class="two-column"><section class="panel"><div class="panel-title"><h3>THE ASSEMBLY / CONSENT TO GATHER</h3>${tag(objective.status.toUpperCase(),objective.status==='verified')}</div><div class="gathering-art"><div class="assembly-symbol"></div></div><h3 class="agreement-title">Make room for<br>the collective.</h3><p class="agreement-desc">The room can be reserved only after three agreement parties have consented to gather, including the host. Every invitation belongs to its recipient.</p>${eligible.map(id=>`<div class="invitation"><span>${esc(actorLabel(id))}</span><button class="secondary" data-invite="${esc(id)}">Invite ↗</button></div>`).join('')}${invitations.map(r=>`<div class="invitation"><span>${esc(shortName(r.source_id))} → ${esc(shortName(r.target_id))}<br>${tag(r.status.toUpperCase(),r.status==='accepted')}</span>${r.target_id===actor&&r.status==='proposed'?`<button class="secondary" data-rsvp="${esc(r.id)}" data-response="accept">Accept ↗</button><button class="secondary" data-rsvp="${esc(r.id)}" data-response="decline">Decline ×</button>`:''}</div>`).join('')}<div class="objective-note"><div><h4>Consent creates a possibility.</h4><p>The assembly still needs an authorised agreement and verified outcomes.</p></div><button class="secondary" data-mode-go="scenarios">Agree the next step ↗</button></div></section>${ledger()}</div>`;
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
      const split=line.indexOf('|');if(split<1)throw Error('Use actor ID | responsibility on every line.');
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
  const titles={accept:`Accept version ${v.number}`,authorize:`Authorise version ${v.number}`,activate:'Activate this agreement',initiate:'Record a concrete action',fulfill:'Report fulfilment',verify:'Independently verify the outcome',reject:'Decline this agreement',terminate:'Terminate the agreement'};
  $('#action-title').textContent=titles[kind];$('#dialog-error').textContent='';
  $('#action-description').textContent=kind==='authorize'?`You are ${actorLabel(actor)}. Your approval will apply only to these exact terms and version. This is a simulated approval receipt, not a digital signature.`:kind==='verify'?'Confirm that you have reviewed the delivery evidence against every criterion. This records your independent attestation.':kind==='accept'?`You are ${actorLabel(actor)}. Acceptance records your undertaking under version ${v.number}; it does not verify fulfilment.`:kind==='activate'?'The engine will check the approvals and reserve capacity. All requested resources must be available in the same transaction.':kind==='fulfill'?'Describe the delivered work and reference evidence. Your report remains unverified until the independent reviewer acts.':'Describe the concrete action or reason. The engine will record its author and provenance.';
  const ref=['initiate','fulfill','verify'].includes(kind),reason=['reject','terminate'].includes(kind);
  $('#action-fields').innerHTML=(kind==='fulfill'?v.verification.criteria.map(c=>`<label class="criterion"><input type="checkbox" name="criterion" value="${esc(c)}" required><span>${esc(c)}</span></label>`).join(''):'')+
    (ref?'<label>Evidence reference or action note<textarea name="reference" class="form-field" required placeholder="Describe the synthetic action and where its evidence can be reviewed."></textarea></label>':'')+
    (reason?'<label>Reason<textarea name="reason" class="form-field" required></textarea></label>':'');
  $('#action-dialog').showModal();
}
function prepareDeclaration(){
  pending={kind:'declare'};$('#action-title').textContent='Declare a capacity or a need';$('#dialog-error').textContent='';
  $('#action-description').textContent='This updates what the collective knows. It does not create a resource reservation, an agreement or a verified fact.';
  $('#action-fields').innerHTML='<label>Signal<select name="table" class="form-field"><option value="capacities">I can offer</option><option value="needs">I need</option></select></label><label>Domain<input class="form-field" name="domain" required placeholder="For example: digital commons"></label><label>Quantity<input class="form-field" name="quantity" type="number" min="1" step="1" value="1" required></label><label>Unit<input class="form-field" name="unit" required placeholder="For example: session"></label>';
  $('#action-dialog').showModal();
}
$('#action-form').onsubmit=async event=>{
  event.preventDefault();const data=new FormData(event.currentTarget);let payload={...pending};
  if(pending.kind==='declare')payload={kind:'declare',table:data.get('table'),record:{domain:data.get('domain'),quantity:Number(data.get('quantity')),unit:data.get('unit')}};
  else{if(data.has('reference'))payload.reference=data.get('reference');if(data.has('reason'))payload.reason=data.get('reason');if(pending.kind==='fulfill')payload.criteria=data.getAll('criterion');}
  if(await command(payload))$('#action-dialog').close();else $('#dialog-error').textContent='The action was rejected. Review the message and current world before retrying.';
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
function syncSound(){$('#sound-toggle').textContent=music.playing?'Sound on ♫':'Sound off ♫';$('#sound-toggle').setAttribute('aria-pressed',String(music.playing));}
async function sound(){try{await music.toggle();syncSound();}catch(error){toast(error.message);}}
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
