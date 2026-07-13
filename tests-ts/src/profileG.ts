/** Canonical Profile G artifact codec (risk-scheduling.md version 1.0). */
import { createHash } from 'node:crypto';

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type ProfileGErrorCode = 'G_INVALID_ARTIFACT' | 'G_LIMIT_EXCEEDED';

export class ProfileGValidationError extends Error {
  constructor(public readonly code: ProfileGErrorCode, public readonly path: string, message: string) {
    super(message); this.name = 'ProfileGValidationError';
  }
}

export interface ProfileGLimits {
  max_artifact_bytes: number; max_parents: number; max_dependencies: number;
  max_evidence: number; max_neighbors: number; min_lease_ms: number; max_lease_ms: number;
}
export const DEFAULT_PROFILE_G_LIMITS: ProfileGLimits = {
  max_artifact_bytes: 1048576, max_parents: 32, max_dependencies: 256,
  max_evidence: 256, max_neighbors: 64, min_lease_ms: 5000, max_lease_ms: 300000,
};

const MAX_SAFE = 9007199254740991;
const B32 = 'abcdefghijklmnopqrstuvwxyz234567';
const schemas: Record<string, string> = {
  Goal:'mcp++/profile-g/goal@1', Subgoal:'mcp++/profile-g/subgoal@1',
  PlanBranch:'mcp++/profile-g/plan-branch@1', PlanSelection:'mcp++/profile-g/plan-selection@1',
  TaskSpec:'mcp++/profile-g/task@1', RiskModel:'mcp++/profile-g/risk-model@1',
  RiskEvidence:'mcp++/profile-g/risk-evidence@1', RiskAssessment:'mcp++/profile-g/risk-assessment@1',
  NeighborhoodRecord:'mcp++/profile-g/neighborhood-record@1', NeighborhoodAttestation:'mcp++/profile-g/neighborhood-attestation@1',
  ScheduleProposal:'mcp++/profile-g/schedule-proposal@1', TaskClaim:'mcp++/profile-g/task-claim@1',
  ClaimResolution:'mcp++/profile-g/claim-resolution@1', TaskReceipt:'mcp++/profile-g/task-receipt@1',
};
const fields: Record<string, string[]> = {
  Goal:['owner_did','objective_cid','policy_cid','parent_goal_cids','labels'],
  Subgoal:['goal_cid','parent_subgoal_cid','objective_cid','decomposition_method','decomposer_cid','selection_cid'],
  PlanBranch:['subgoal_cid','candidate_input_cids','task_template_cids','evaluator_cid','score_millionths','explanation_cid'],
  PlanSelection:['subgoal_cid','plan_branch_cid','selector_did','proof_cid','policy_decision_cid','reason_cid'],
  TaskSpec:['subgoal_cid','plan_branch_cid','selection_cid','interface_cid','input_cid','tool','dependency_task_cids','idempotency_key','resource_class','deadline_ms','expected_value_millionths','max_attempts','execution_mode'],
  RiskModel:['name','version','factor_names','weight_millionths','saturation_millionths','algorithm','missing_evidence','max_history_events','risk_buckets'],
  RiskEvidence:['subject_cid','evidence_type','observed_cids','observer_did','observed_at_ms','expires_at_ms','classification','redacted_cid','signer_did','signature_alg','signature'],
  RiskAssessment:['task_cid','subject_did','model_cid','evidence_cids','factor_millionths','score_millionths','confidence_millionths','action','assessed_at_ms','expires_at_ms'],
  NeighborhoodRecord:['peer_did','interface_cids','resource_classes','capacity_millionths','health_evidence_cid','trust_domain_cid','reachable_artifact_cids','valid_from_ms','expires_at_ms','signer_did','signature_alg','signature'],
  NeighborhoodAttestation:['proposal_cid','attester_did','record_cid','verdict','reason_code','evidence_cid','observed_epoch','expires_at_ms','signer_did','signature_alg','signature'],
  ScheduleProposal:['task_cid','risk_assessment_cid','selection_policy_cid','policy_decision_cid','logical_epoch','priority_tuple','candidates'],
  TaskClaim:['task_cid','proposal_cid','claimant_did','record_cid','logical_epoch','requested_lease_ms','risk_bucket','capability_fit_millionths','expected_finish_ms','proof_cid','policy_decision_cid','attempt'],
  ClaimResolution:['task_cid','logical_epoch','considered_claim_cids','accepted_claim_cid','outcome','fencing_token','lease_expires_at_ms','attestation_cids','quorum_policy_cid','policy_decision_cid','coordination_receipt_cid','retry_not_before_ms','resolver_did'],
  TaskReceipt:['task_cid','claim_cid','resolution_cid','fencing_token','profile_b_receipt_cid','output_cid','status','failure_class','attempt','started_at_ms','finished_at_ms','resource_use_cid','provider','provider_version','next_state'],
};
const common = ['schema','created_at_ms','parents','correlation_id'];

function fail(path: string, message: string, code: ProfileGErrorCode='G_INVALID_ARTIFACT'): never {
  throw new ProfileGValidationError(code, path, message);
}
function object(v: unknown, p=''): any { if (!v || typeof v !== 'object' || Array.isArray(v)) fail(p, 'must be an object'); return v as any; }
function integer(v: unknown,p:string,min=0,max=MAX_SAFE): number { if(typeof v!=='number'||!Number.isSafeInteger(v)||Object.is(v,-0)||v<min||v>max) fail(p,`must be an integer in [${min}, ${max}]`); return v; }
function string(v:unknown,p:string,max=4096):string { if(typeof v!=='string'||!v.length||Buffer.byteLength(v)>max||v.includes('\0')) fail(p,'invalid string'); return v; }
function oneOf(v:unknown,p:string,values:string[]):string { const s=string(v,p); if(!values.includes(s)) fail(p,`must be one of ${values.join(', ')}`); return s; }
function did(v:unknown,p:string):void { const s=string(v,p); if(!/^did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\0]*)?$/.test(s)) fail(p,'invalid DID'); }
function varint(b:Uint8Array,start:number):[number,number] { let n=0,shift=0,i=start; for(;i<b.length&&shift<56;i++,shift+=7){const x=b[i]!;n+=(x&127)*2**shift;if(!(x&128))return[n,i+1];} fail('', 'invalid CID varint'); }
function cid(v:unknown,p:string):void {
  const s=string(v,p); if(!/^b[a-z2-7]+$/.test(s)) fail(p,'CID must be lowercase base32 CIDv1');
  let bits=0,acc=0; const out:number[]=[]; for(const c of s.slice(1)){const x=B32.indexOf(c);if(x<0)fail(p,'invalid CID');acc=(acc<<5)|x;bits+=5;if(bits>=8){bits-=8;out.push((acc>>bits)&255);acc&=(1<<bits)-1;}}
  const b=Uint8Array.from(out); const [version,a]=varint(b,0),[,z]=varint(b,a),[mh,n]=varint(b,z),[len,e]=varint(b,n);
  if(version!==1||mh!==0x12||len!==32||e+len!==b.length) fail(p,'CID must use CIDv1 sha2-256');
}
function array(v:unknown,p:string,min:number,max:number):any[]{if(!Array.isArray(v)||v.length<min||v.length>max)fail(p,`must contain ${min}..${max} items`);return v;}
function utf8Compare(a:string,b:string):number{return Buffer.compare(Buffer.from(a),Buffer.from(b));}
function sortedSet(v:unknown,p:string,min:number,max:number,check:(x:unknown,p:string)=>void):any[]{const a=array(v,p,min,max);a.forEach((x,i)=>check(x,`${p}/${i}`));for(let i=1;i<a.length;i++)if(utf8Compare(a[i-1],a[i])>=0)fail(`${p}/${i}`,'must be sorted and unique');return a;}
function cidSet(v:unknown,p:string,min:number,max:number):any[]{return sortedSet(v,p,min,max,cid);}
function million(v:unknown,p:string):number{return integer(v,p,0,1000000);}

function canonical(v:unknown,p=''): string {
  if(v===null)return 'null'; if(typeof v==='boolean')return v?'true':'false';
  if(typeof v==='number'){integer(v,p,-MAX_SAFE,MAX_SAFE);return String(v);}
  if(typeof v==='string')return JSON.stringify(v);
  if(Array.isArray(v))return '['+v.map((x,i)=>canonical(x,`${p}/${i}`)).join(',')+']';
  const o=object(v,p); const keys=Object.keys(o).sort(utf8Compare);
  return '{'+keys.map(k=>JSON.stringify(k)+':'+canonical(o[k],`${p}/${k}`)).join(',')+'}';
}
export function canonicalProfileGBytes(value: unknown): Uint8Array { return Buffer.from(canonical(value)); }
function base32(bytes:Uint8Array):string{let out='',bits=0,acc=0;for(const x of bytes){acc=(acc<<8)|x;bits+=8;while(bits>=5){bits-=5;out+=B32[(acc>>bits)&31]!;acc&=(1<<bits)-1;}}if(bits)out+=B32[(acc<<(5-bits))&31]!;return out;}
export function profileGArtifactCid(value: unknown): string {
  const digest=createHash('sha256').update(canonicalProfileGBytes(value)).digest();
  return 'b'+base32(Uint8Array.from([1,0xa9,0x02,0x12,0x20,...digest]));
}

/** Strictly validate an artifact and return its canonical CID. */
export function validateProfileGArtifact(kind:string,value:unknown,limits:Partial<ProfileGLimits>={}):string {
  const l={...DEFAULT_PROFILE_G_LIMITS,...limits}, o=object(value);
  if(!schemas[kind])fail('/kind',`unknown artifact kind ${kind}`);
  const allowed=new Set([...common,...fields[kind]!]); for(const k of Object.keys(o))if(!allowed.has(k))fail('/'+k,'unknown field');
  for(const k of allowed)if(!(k in o))fail('/'+k,'required field missing');
  if(o.schema!==schemas[kind])fail('/schema','wrong schema marker'); integer(o.created_at_ms,'/created_at_ms'); cidSet(o.parents,'/parents',0,l.max_parents); string(o.correlation_id,'/correlation_id',128);
  validateSpecific(kind,o,l);
  const bytes=canonicalProfileGBytes(o); if(bytes.length>l.max_artifact_bytes)fail('', 'artifact too large','G_LIMIT_EXCEEDED');
  return profileGArtifactCid(o);
}

function validateSpecific(k:string,o:any,l:ProfileGLimits):void {
  const c=(n:string)=>cid(o[n],'/'+n), d=(n:string)=>did(o[n],'/'+n), s=(n:string,m=4096)=>string(o[n],'/'+n,m), i=(n:string,min=0,max=MAX_SAFE)=>integer(o[n],'/'+n,min,max);
  switch(k){
    case 'Goal': d('owner_did');c('objective_cid');c('policy_cid');cidSet(o.parent_goal_cids,'/parent_goal_cids',0,32);sortedSet(o.labels,'/labels',0,32,(x,p)=>string(x,p,64));break;
    case 'Subgoal': c('goal_cid'); if(o.parent_subgoal_cid!==null)c('parent_subgoal_cid');c('objective_cid');s('decomposition_method',128);c('decomposer_cid');if(o.selection_cid!==null)c('selection_cid');break;
    case 'PlanBranch': c('subgoal_cid');cidSet(o.candidate_input_cids,'/candidate_input_cids',0,64);cidSet(o.task_template_cids,'/task_template_cids',1,256);c('evaluator_cid');million(o.score_millionths,'/score_millionths');c('explanation_cid');break;
    case 'PlanSelection': c('subgoal_cid');c('plan_branch_cid');d('selector_did');c('proof_cid');c('policy_decision_cid');c('reason_cid');break;
    case 'TaskSpec': ['subgoal_cid','plan_branch_cid','selection_cid','interface_cid','input_cid'].forEach(c);s('tool',256);cidSet(o.dependency_task_cids,'/dependency_task_cids',0,l.max_dependencies);s('idempotency_key',128);s('resource_class',128);if(o.deadline_ms!==null)i('deadline_ms');million(o.expected_value_millionths,'/expected_value_millionths');i('max_attempts',1,100);oneOf(o.execution_mode,'/execution_mode',['idempotent','compensatable','exclusive']);break;
    case 'RiskModel': s('name');s('version');const names=sortedSet(o.factor_names,'/factor_names',1,64,(x,p)=>string(x,p,128)); const w=object(o.weight_millionths,'/weight_millionths'),sat=object(o.saturation_millionths,'/saturation_millionths');if(JSON.stringify(Object.keys(w).sort(utf8Compare))!==JSON.stringify(names))fail('/weight_millionths','factor keys mismatch');if(JSON.stringify(Object.keys(sat).sort(utf8Compare))!==JSON.stringify(names))fail('/saturation_millionths','factor keys mismatch');let positive=false;for(const n of names){positive=positive||million(w[n],`/weight_millionths/${n}`)>0;integer(sat[n],`/saturation_millionths/${n}`,1,1000000);}if(!positive)fail('/weight_millionths','one weight must be positive');oneOf(o.algorithm,'/algorithm',['weighted-saturated-sum-v1']);oneOf(o.missing_evidence,'/missing_evidence',['deny','challenge','max-risk']);i('max_history_events',1,l.max_evidence);const rb=array(o.risk_buckets,'/risk_buckets',1,64);rb.forEach((x,j)=>million(x,`/risk_buckets/${j}`));for(let j=1;j<rb.length;j++)if(rb[j]<=rb[j-1])fail(`/risk_buckets/${j}`,'must increase');if(rb.at(-1)!==1000000)fail('/risk_buckets','must end at 1000000');break;
    case 'RiskEvidence':c('subject_cid');oneOf(o.evidence_type,'/evidence_type',['policy-denial','authority-failure','obligation-overdue','execution-failure','timeout','resource-overrun','dispute','rollback','archive-inclusion','capacity-health']);cidSet(o.observed_cids,'/observed_cids',1,l.max_evidence);d('observer_did');i('observed_at_ms');i('expires_at_ms');if(o.expires_at_ms<=o.observed_at_ms)fail('/expires_at_ms','must exceed observation');oneOf(o.classification,'/classification',['public','trust-domain','confidential','restricted']);if(o.redacted_cid!==null)c('redacted_cid');d('signer_did');s('signature_alg',128);s('signature');break;
    case 'RiskAssessment':c('task_cid');d('subject_did');c('model_cid');cidSet(o.evidence_cids,'/evidence_cids',0,l.max_evidence);const factors=object(o.factor_millionths,'/factor_millionths');for(const [n,v] of Object.entries(factors))million(v,`/factor_millionths/${n}`);million(o.score_millionths,'/score_millionths');million(o.confidence_millionths,'/confidence_millionths');oneOf(o.action,'/action',['allow','challenge','review','deny']);i('assessed_at_ms');i('expires_at_ms');if(o.expires_at_ms<=o.assessed_at_ms)fail('/expires_at_ms','must exceed assessment');break;
    case 'NeighborhoodRecord':d('peer_did');cidSet(o.interface_cids,'/interface_cids',1,128);sortedSet(o.resource_classes,'/resource_classes',1,64,(x,p)=>string(x,p,128));million(o.capacity_millionths,'/capacity_millionths');c('health_evidence_cid');c('trust_domain_cid');cidSet(o.reachable_artifact_cids,'/reachable_artifact_cids',0,128);i('valid_from_ms');i('expires_at_ms');if(o.expires_at_ms<=o.valid_from_ms)fail('/expires_at_ms','must exceed valid_from');d('signer_did');s('signature_alg',128);s('signature');break;
    case 'NeighborhoodAttestation':c('proposal_cid');d('attester_did');c('record_cid');oneOf(o.verdict,'/verdict',['support','challenge','abstain']);s('reason_code',128);if(o.evidence_cid!==null)c('evidence_cid');i('observed_epoch',1);i('expires_at_ms');d('signer_did');s('signature_alg',128);s('signature');break;
    case 'ScheduleProposal': ['task_cid','risk_assessment_cid','selection_policy_cid','policy_decision_cid'].forEach(c);i('logical_epoch',1);const pt=array(o.priority_tuple,'/priority_tuple',8,8);for(let j=0;j<7;j++)integer(pt[j],`/priority_tuple/${j}`,-MAX_SAFE,MAX_SAFE);if(pt[0]!==0&&pt[0]!==1)fail('/priority_tuple/0','ready must be 0 or 1');if(pt[2]<0||pt[2]>3)fail('/priority_tuple/2','invalid risk action');cid(pt[7],'/priority_tuple/7');const ca=array(o.candidates,'/candidates',1,l.max_neighbors);ca.forEach((x,j)=>candidate(x,`/candidates/${j}`));for(let j=1;j<ca.length;j++)if(compareCandidate(ca[j-1],ca[j])>=0)fail(`/candidates/${j}`,'candidates out of order or duplicate');break;
    case 'TaskClaim':['task_cid','proposal_cid'].forEach(c);d('claimant_did');c('record_cid');i('logical_epoch',1);i('requested_lease_ms',0);if(o.requested_lease_ms<l.min_lease_ms||o.requested_lease_ms>l.max_lease_ms)fail('/requested_lease_ms','outside negotiated lease bounds','G_LIMIT_EXCEEDED');i('risk_bucket');million(o.capability_fit_millionths,'/capability_fit_millionths');i('expected_finish_ms');c('proof_cid');c('policy_decision_cid');i('attempt',1,100);break;
    case 'ClaimResolution':c('task_cid');i('logical_epoch',1);cidSet(o.considered_claim_cids,'/considered_claim_cids',1,l.max_neighbors);if(o.accepted_claim_cid!==null)c('accepted_claim_cid');oneOf(o.outcome,'/outcome',['accepted','conflict','released','expired','completed']);i('fencing_token',1);if(o.lease_expires_at_ms!==null)i('lease_expires_at_ms');if(o.outcome==='accepted'&&(o.accepted_claim_cid===null||o.lease_expires_at_ms===null))fail('/accepted_claim_cid','accepted outcome requires claim and lease');if(o.outcome!=='accepted'&&(o.accepted_claim_cid!==null||o.lease_expires_at_ms!==null))fail('/accepted_claim_cid','non-accepted outcome forbids claim and lease');cidSet(o.attestation_cids,'/attestation_cids',0,l.max_neighbors);c('quorum_policy_cid');c('policy_decision_cid');if(o.coordination_receipt_cid!==null)c('coordination_receipt_cid');i('retry_not_before_ms');d('resolver_did');break;
    case 'TaskReceipt':['task_cid','claim_cid','resolution_cid'].forEach(c);i('fencing_token',1);c('profile_b_receipt_cid');if(o.output_cid!==null)c('output_cid');oneOf(o.status,'/status',['succeeded','failed','cancelled','compensated']);oneOf(o.failure_class,'/failure_class',['none','retryable','permanent','policy','authority','fenced','resource']);i('attempt',1,100);i('started_at_ms');i('finished_at_ms');if(o.finished_at_ms<o.started_at_ms)fail('/finished_at_ms','precedes start');c('resource_use_cid');s('provider',128);s('provider_version',128);oneOf(o.next_state,'/next_state',['complete','ready','blocked','compensation-required']);if(o.status==='succeeded'&&(o.output_cid===null||o.failure_class!=='none'||o.next_state!=='complete'))fail('/output_cid','invalid successful receipt');break;
  }
}
function candidate(x:unknown,p:string):void{const o=object(x,p),ks=['peer_did','record_cid','capability_fit_millionths','expected_finish_ms','risk_bucket'];if(JSON.stringify(Object.keys(o).sort())!==JSON.stringify([...ks].sort()))fail(p,'invalid candidate fields');did(o.peer_did,p+'/peer_did');cid(o.record_cid,p+'/record_cid');million(o.capability_fit_millionths,p+'/capability_fit_millionths');integer(o.expected_finish_ms,p+'/expected_finish_ms');integer(o.risk_bucket,p+'/risk_bucket');}
function compareCandidate(a:any,b:any):number{return a.risk_bucket-b.risk_bucket||b.capability_fit_millionths-a.capability_fit_millionths||a.expected_finish_ms-b.expected_finish_ms||utf8Compare(a.peer_did,b.peer_did)||utf8Compare(a.record_cid,b.record_cid);}

export type PriorityTuple=[number,number,number,number,number,number,number,string];
export function derivePriorityTuple(x:{ready:boolean;deadline_class:number;risk_action:'allow'|'challenge'|'review'|'deny';age_bucket:number;expected_value_millionths:number;resource_fit_millionths:number;retry_not_before_ms:number;task_cid:string}):PriorityTuple{
  cid(x.task_cid,'/task_cid');return[x.ready?0:1,integer(x.deadline_class,'/deadline_class'),({allow:0,challenge:1,review:2,deny:3})[x.risk_action],-integer(x.age_bucket,'/age_bucket'),-million(x.expected_value_millionths,'/expected_value_millionths'),-million(x.resource_fit_millionths,'/resource_fit_millionths'),integer(x.retry_not_before_ms,'/retry_not_before_ms'),x.task_cid];
}
export function evaluateRisk(model:any,factorMillionths:Record<string,number>):{score_millionths:number;risk_bucket:number}{validateProfileGArtifact('RiskModel',model);let weighted=0n,total=0n;for(const n of model.factor_names){const f=BigInt(million(factorMillionths[n],`/factor_millionths/${n}`)),w=BigInt(model.weight_millionths[n]),sat=BigInt(model.saturation_millionths[n]);const normalized=f*1000000n/sat;weighted+=w*(normalized>1000000n?1000000n:normalized);total+=w;}const score=Number(weighted/total);return{score_millionths:Math.min(1000000,score),risk_bucket:model.risk_buckets.findIndex((x:number)=>score<=x)};}
export function compareClaims(a:any,b:any):number{return b.logical_epoch-a.logical_epoch||a.risk_bucket-b.risk_bucket||b.capability_fit_millionths-a.capability_fit_millionths||a.expected_finish_ms-b.expected_finish_ms||utf8Compare(a.claimant_did,b.claimant_did)||utf8Compare(a.claim_cid,b.claim_cid);}
