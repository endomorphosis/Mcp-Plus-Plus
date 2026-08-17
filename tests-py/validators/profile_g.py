"""Canonical Profile G DAG-JSON codec and scheduling primitives."""
from __future__ import annotations
import base64, hashlib, json, re
from dataclasses import dataclass
from typing import Any, Mapping

MAX=9007199254740991
LIMITS={"max_artifact_bytes":1048576,"max_parents":32,"max_dependencies":256,"max_evidence":256,"max_neighbors":64,"min_lease_ms":5000,"max_lease_ms":300000}
SCHEMAS=dict(zip("Goal Subgoal PlanBranch PlanSelection TaskSpec RiskModel RiskEvidence RiskAssessment NeighborhoodRecord NeighborhoodAttestation ScheduleProposal TaskClaim ClaimResolution TaskReceipt".split(),"goal subgoal plan-branch plan-selection task risk-model risk-evidence risk-assessment neighborhood-record neighborhood-attestation schedule-proposal task-claim claim-resolution task-receipt".split()))
FIELDS={
"Goal":"owner_did objective_cid policy_cid parent_goal_cids labels","Subgoal":"goal_cid parent_subgoal_cid objective_cid decomposition_method decomposer_cid selection_cid","PlanBranch":"subgoal_cid candidate_input_cids task_template_cids evaluator_cid score_millionths explanation_cid","PlanSelection":"subgoal_cid plan_branch_cid selector_did proof_cid policy_decision_cid reason_cid","TaskSpec":"subgoal_cid plan_branch_cid selection_cid interface_cid input_cid tool dependency_task_cids idempotency_key resource_class deadline_ms expected_value_millionths max_attempts execution_mode","RiskModel":"name version factor_names weight_millionths saturation_millionths algorithm missing_evidence max_history_events risk_buckets","RiskEvidence":"subject_cid evidence_type observed_cids observer_did observed_at_ms expires_at_ms classification redacted_cid signer_did signature_alg signature","RiskAssessment":"task_cid subject_did model_cid evidence_cids factor_millionths score_millionths confidence_millionths action assessed_at_ms expires_at_ms","NeighborhoodRecord":"peer_did interface_cids resource_classes capacity_millionths health_evidence_cid trust_domain_cid reachable_artifact_cids valid_from_ms expires_at_ms signer_did signature_alg signature","NeighborhoodAttestation":"proposal_cid attester_did record_cid verdict reason_code evidence_cid observed_epoch expires_at_ms signer_did signature_alg signature","ScheduleProposal":"task_cid risk_assessment_cid selection_policy_cid policy_decision_cid logical_epoch priority_tuple candidates","TaskClaim":"task_cid proposal_cid claimant_did record_cid logical_epoch requested_lease_ms risk_bucket capability_fit_millionths expected_finish_ms proof_cid policy_decision_cid attempt","ClaimResolution":"task_cid logical_epoch considered_claim_cids accepted_claim_cid outcome fencing_token lease_expires_at_ms attestation_cids quorum_policy_cid policy_decision_cid coordination_receipt_cid retry_not_before_ms resolver_did","TaskReceipt":"task_cid claim_cid resolution_cid fencing_token profile_b_receipt_cid output_cid status failure_class attempt started_at_ms finished_at_ms resource_use_cid provider provider_version next_state"}

@dataclass
class ProfileGValidationError(ValueError):
 code:str; path:str; detail:str
def fail(p,d,c="G_INVALID_ARTIFACT"): raise ProfileGValidationError(c,p,d)
def integer(v,p,lo=0,hi=MAX):
 if isinstance(v,bool) or not isinstance(v,int) or not lo<=v<=hi: fail(p,"invalid integer")
 return v
def string(v,p,n=4096):
 if not isinstance(v,str) or not v or len(v.encode())>n or "\0" in v: fail(p,"invalid string")
 return v
def enum(v,p,vals):
 if string(v,p) not in vals: fail(p,"invalid value")
def did(v,p):
 if not re.fullmatch(r"did:[a-z0-9]+:[A-Za-z0-9._:%-]+(?:[/?#][^\x00]*)?",string(v,p)): fail(p,"invalid DID")
def varint(b,p):
 n=s=0
 while p<len(b):
  x=b[p];p+=1;n|=(x&127)<<s
  if not x&128:return n,p
  s+=7
 fail("","invalid CID")
def cid(v,p):
 s=string(v,p)
 if not re.fullmatch(r"b[a-z2-7]+",s):fail(p,"invalid CID")
 try:b=base64.b32decode(s[1:].upper()+"="*((8-len(s[1:])%8)%8))
 except Exception:fail(p,"invalid CID")
 ver,z=varint(b,0);_,z=varint(b,z);mh,z=varint(b,z);ln,z=varint(b,z)
 if (ver,mh,ln)!=(1,18,32) or z+ln!=len(b):fail(p,"CID must be CIDv1 sha2-256")
def arr(v,p,lo,hi):
 if not isinstance(v,list) or not lo<=len(v)<=hi:fail(p,"invalid array")
 return v
def aset(v,p,lo,hi,check):
 a=arr(v,p,lo,hi)
 for n,x in enumerate(a):check(x,f"{p}/{n}")
 for n in range(1,len(a)):
  if a[n-1].encode()>=a[n].encode():fail(f"{p}/{n}","not sorted unique")
 return a
def cids(v,p,lo,hi):return aset(v,p,lo,hi,cid)
def mil(v,p):return integer(v,p,0,1000000)

def canonical_profile_g_bytes(v):
 def walk(x,p=""):
  if x is None or isinstance(x,(str,bool)):return
  if isinstance(x,int):integer(x,p,-MAX,MAX);return
  if isinstance(x,list):
   for n,y in enumerate(x):walk(y,f"{p}/{n}")
   return
  if isinstance(x,dict):
   for k,y in x.items():
    if not isinstance(k,str):fail(p,"invalid key")
    walk(y,f"{p}/{k}")
   return
  fail(p,"not canonical JSON")
 walk(v);return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def profile_g_artifact_cid(v):return "b"+base64.b32encode(b"\x01\xa9\x02\x12\x20"+hashlib.sha256(canonical_profile_g_bytes(v)).digest()).decode().lower().rstrip("=")

def validate_profile_g_artifact(k,v,limits=None):
 if k not in SCHEMAS:fail("/kind","unknown kind")
 l={**LIMITS,**(limits or {})}
 if not isinstance(v,dict):fail("","not object")
 allowed=set("schema created_at_ms parents correlation_id".split()+FIELDS[k].split())
 for x in v:
  if x not in allowed:fail("/"+x,"unknown field")
 for x in allowed:
  if x not in v:fail("/"+x,"missing field")
 if v["schema"]!="mcp++/profile-g/"+SCHEMAS[k]+"@1":fail("/schema","wrong schema")
 integer(v["created_at_ms"],"/created_at_ms");cids(v["parents"],"/parents",0,l["max_parents"]);string(v["correlation_id"],"/correlation_id",128)
 specific(k,v,l)
 if len(canonical_profile_g_bytes(v))>l["max_artifact_bytes"]:fail("","too large","G_LIMIT_EXCEEDED")
 return profile_g_artifact_cid(v)

def specific(k,o,l):
 c=lambda n:cid(o[n],"/"+n);d=lambda n:did(o[n],"/"+n);i=lambda n,a=0,b=MAX:integer(o[n],"/"+n,a,b);s=lambda n,z=4096:string(o[n],"/"+n,z)
 if k=="Goal":d("owner_did");c("objective_cid");c("policy_cid");cids(o["parent_goal_cids"],"/parent_goal_cids",0,32);aset(o["labels"],"/labels",0,32,lambda x,p:string(x,p,64))
 elif k=="Subgoal":c("goal_cid");o["parent_subgoal_cid"] is None or c("parent_subgoal_cid");c("objective_cid");s("decomposition_method",128);c("decomposer_cid");o["selection_cid"] is None or c("selection_cid")
 elif k=="PlanBranch":c("subgoal_cid");cids(o["candidate_input_cids"],"/candidate_input_cids",0,64);cids(o["task_template_cids"],"/task_template_cids",1,256);c("evaluator_cid");mil(o["score_millionths"],"/score_millionths");c("explanation_cid")
 elif k=="PlanSelection":c("subgoal_cid");c("plan_branch_cid");d("selector_did");c("proof_cid");c("policy_decision_cid");c("reason_cid")
 elif k=="TaskSpec":
  for n in "subgoal_cid plan_branch_cid selection_cid interface_cid input_cid".split():c(n)
  s("tool",256);cids(o["dependency_task_cids"],"/dependency_task_cids",0,l["max_dependencies"]);s("idempotency_key",128);s("resource_class",128);o["deadline_ms"] is None or i("deadline_ms");mil(o["expected_value_millionths"],"/expected_value_millionths");i("max_attempts",1,100);enum(o["execution_mode"],"/execution_mode",("idempotent","compensatable","exclusive"))
 elif k=="RiskModel":
  s("name");s("version");names=aset(o["factor_names"],"/factor_names",1,64,lambda x,p:string(x,p,128))
  if sorted(o["weight_millionths"])!=names:fail("/weight_millionths","keys mismatch")
  if sorted(o["saturation_millionths"])!=names:fail("/saturation_millionths","keys mismatch")
  if not any(mil(o["weight_millionths"][n],f"/weight_millionths/{n}") for n in names):fail("/weight_millionths","zero weights")
  for n in names:integer(o["saturation_millionths"][n],f"/saturation_millionths/{n}",1,1000000)
  enum(o["algorithm"],"/algorithm",("weighted-saturated-sum-v1",));enum(o["missing_evidence"],"/missing_evidence",("deny","challenge","max-risk"));i("max_history_events",1,l["max_evidence"]);r=arr(o["risk_buckets"],"/risk_buckets",1,64)
  if any(mil(x,f"/risk_buckets/{n}")<=r[n-1] for n,x in enumerate(r) if n) or r[-1]!=1000000:fail("/risk_buckets","bad thresholds")
 elif k=="RiskEvidence":c("subject_cid");enum(o["evidence_type"],"/evidence_type",("policy-denial","authority-failure","obligation-overdue","execution-failure","timeout","resource-overrun","dispute","rollback","archive-inclusion","capacity-health"));cids(o["observed_cids"],"/observed_cids",1,l["max_evidence"]);d("observer_did");i("observed_at_ms");i("expires_at_ms");o["expires_at_ms"]>o["observed_at_ms"] or fail("/expires_at_ms","bad expiry");enum(o["classification"],"/classification",("public","trust-domain","confidential","restricted"));o["redacted_cid"] is None or c("redacted_cid");d("signer_did");s("signature_alg",128);s("signature")
 elif k=="RiskAssessment":c("task_cid");d("subject_did");c("model_cid");cids(o["evidence_cids"],"/evidence_cids",0,l["max_evidence"]);[mil(x,f"/factor_millionths/{n}") for n,x in o["factor_millionths"].items()];mil(o["score_millionths"],"/score_millionths");mil(o["confidence_millionths"],"/confidence_millionths");enum(o["action"],"/action",("allow","challenge","review","deny"));i("assessed_at_ms");i("expires_at_ms")
 elif k=="NeighborhoodRecord":d("peer_did");cids(o["interface_cids"],"/interface_cids",1,128);aset(o["resource_classes"],"/resource_classes",1,64,lambda x,p:string(x,p,128));mil(o["capacity_millionths"],"/capacity_millionths");c("health_evidence_cid");c("trust_domain_cid");cids(o["reachable_artifact_cids"],"/reachable_artifact_cids",0,128);i("valid_from_ms");i("expires_at_ms");d("signer_did");s("signature_alg",128);s("signature")
 elif k=="NeighborhoodAttestation":c("proposal_cid");d("attester_did");c("record_cid");enum(o["verdict"],"/verdict",("support","challenge","abstain"));s("reason_code",128);o["evidence_cid"] is None or c("evidence_cid");i("observed_epoch",1);i("expires_at_ms");d("signer_did");s("signature_alg",128);s("signature")
 elif k=="ScheduleProposal":
  for n in "task_cid risk_assessment_cid selection_policy_cid policy_decision_cid".split():c(n)
  i("logical_epoch",1);p=arr(o["priority_tuple"],"/priority_tuple",8,8);[integer(x,f"/priority_tuple/{n}",-MAX,MAX) for n,x in enumerate(p[:7])];cid(p[7],"/priority_tuple/7");a=arr(o["candidates"],"/candidates",1,l["max_neighbors"])
  for n,x in enumerate(a):
   did(x["peer_did"],f"/candidates/{n}/peer_did");cid(x["record_cid"],f"/candidates/{n}/record_cid");mil(x["capability_fit_millionths"],f"/candidates/{n}/capability_fit_millionths")
   if n and candidate_key(a[n-1])>=candidate_key(x):fail(f"/candidates/{n}","wrong order")
 elif k=="TaskClaim":c("task_cid");c("proposal_cid");d("claimant_did");c("record_cid");i("logical_epoch",1);i("requested_lease_ms");(l["min_lease_ms"]<=o["requested_lease_ms"]<=l["max_lease_ms"]) or fail("/requested_lease_ms","lease limit","G_LIMIT_EXCEEDED");i("risk_bucket");mil(o["capability_fit_millionths"],"/capability_fit_millionths");i("expected_finish_ms");c("proof_cid");c("policy_decision_cid");i("attempt",1,100)
 elif k=="ClaimResolution":
  c("task_cid");i("logical_epoch",1);cids(o["considered_claim_cids"],"/considered_claim_cids",1,l["max_neighbors"]);enum(o["outcome"],"/outcome",("accepted","conflict","released","expired","completed"));i("fencing_token",1)
  if o["outcome"]=="accepted" and (o["accepted_claim_cid"] is None or o["lease_expires_at_ms"] is None):fail("/accepted_claim_cid","lease required")
  o["accepted_claim_cid"] is None or c("accepted_claim_cid");o["lease_expires_at_ms"] is None or i("lease_expires_at_ms");cids(o["attestation_cids"],"/attestation_cids",0,l["max_neighbors"]);c("quorum_policy_cid");c("policy_decision_cid");o["coordination_receipt_cid"] is None or c("coordination_receipt_cid");i("retry_not_before_ms");d("resolver_did")
 elif k=="TaskReceipt":
  for n in "task_cid claim_cid resolution_cid".split():c(n)
  i("fencing_token",1);c("profile_b_receipt_cid");o["output_cid"] is None or c("output_cid");enum(o["status"],"/status",("succeeded","failed","cancelled","compensated"));enum(o["failure_class"],"/failure_class",("none","retryable","permanent","policy","authority","fenced","resource"));i("attempt",1,100);i("started_at_ms");i("finished_at_ms");c("resource_use_cid");s("provider",128);s("provider_version",128);enum(o["next_state"],"/next_state",("complete","ready","blocked","compensation-required"))
  if o["status"]=="succeeded" and o["output_cid"] is None:fail("/output_cid","output required")
def candidate_key(x):return(x["risk_bucket"],-x["capability_fit_millionths"],x["expected_finish_ms"],x["peer_did"].encode(),x["record_cid"].encode())
def derive_priority_tuple(*,ready,deadline_class,risk_action,age_bucket,expected_value_millionths,resource_fit_millionths,retry_not_before_ms,task_cid):cid(task_cid,"/task_cid");return(0 if ready else 1,integer(deadline_class,"/deadline_class"),{"allow":0,"challenge":1,"review":2,"deny":3}[risk_action],-integer(age_bucket,"/age_bucket"),-mil(expected_value_millionths,"/expected_value_millionths"),-mil(resource_fit_millionths,"/resource_fit_millionths"),integer(retry_not_before_ms,"/retry_not_before_ms"),task_cid)
def evaluate_risk(model,factors):
 validate_profile_g_artifact("RiskModel",model);total=weighted=0
 for n in model["factor_names"]:w=model["weight_millionths"][n];weighted+=w*min(1000000,mil(factors[n],"/factor_millionths/"+n)*1000000//model["saturation_millionths"][n]);total+=w
 score=min(1000000,weighted//total);return score,next(i for i,x in enumerate(model["risk_buckets"]) if score<=x)
def claim_order_key(x):return(-x["logical_epoch"],x["risk_bucket"],-x["capability_fit_millionths"],x["expected_finish_ms"],x["claimant_did"].encode(),x["claim_cid"].encode())

# --- Claims, leases, logical epochs, and fencing tokens (MCPP-067) ---
# Protocol codes used by renew / takeover / completion enforcement.
G_LEASE_EXPIRED="G_LEASE_EXPIRED";G_STALE_FENCE="G_STALE_FENCE";G_CLAIM_CONFLICT="G_CLAIM_CONFLICT"

def next_fencing_token(logical_epoch,prior_fencing_token=0):
 """Strictly increasing fence: max(epoch, prior+1); prior is 0 when none exists."""
 return max(integer(logical_epoch,"/logical_epoch",1),integer(prior_fencing_token,"/prior_fencing_token",0)+1)

def select_winning_claim(claims):
 """Deterministic same-epoch winner under claim_order_key (minimum key wins)."""
 a=arr(list(claims),"/claims",1,LIMITS["max_neighbors"])
 for n,x in enumerate(a):
  for f in "logical_epoch risk_bucket capability_fit_millionths expected_finish_ms claimant_did claim_cid".split():
   if f not in x:fail(f"/claims/{n}/{f}","missing field")
  integer(x["logical_epoch"],f"/claims/{n}/logical_epoch",1);integer(x["risk_bucket"],f"/claims/{n}/risk_bucket")
  mil(x["capability_fit_millionths"],f"/claims/{n}/capability_fit_millionths");integer(x["expected_finish_ms"],f"/claims/{n}/expected_finish_ms")
  did(x["claimant_did"],f"/claims/{n}/claimant_did");cid(x["claim_cid"],f"/claims/{n}/claim_cid")
 return min(a,key=claim_order_key)

def lease_is_live(lease_expires_at_ms,now_ms):
 """True while wall/logical clock is still strictly before the exclusive bound."""
 return integer(now_ms,"/now_ms")<integer(lease_expires_at_ms,"/lease_expires_at_ms")

def lease_is_expired(lease_expires_at_ms,now_ms):
 """True when renew/takeover must treat the lease as past its bound (now > expires)."""
 return integer(now_ms,"/now_ms")>integer(lease_expires_at_ms,"/lease_expires_at_ms")

def require_lease_renewable(lease_expires_at_ms,now_ms):
 """Reject renew after expiry with G_LEASE_EXPIRED (protocol vector renew-after-expiry)."""
 if lease_is_expired(lease_expires_at_ms,now_ms):fail("/lease_expires_at_ms","lease expired",G_LEASE_EXPIRED)
 return True

def require_current_fence(presented_token,current_token):
 """Reject any presented fence that is not exactly the current accepted token."""
 p=integer(presented_token,"/fencing_token",1);c=integer(current_token,"/current_fencing_token",1)
 if p!=c:fail("/fencing_token","stale fencing token",G_STALE_FENCE)
 return True

def expected_claim_epoch(latest_terminal_epoch=0):
 """Next legal logical epoch after the latest terminal/accepted epoch (0 => first claim)."""
 return integer(latest_terminal_epoch,"/latest_terminal_epoch",0)+1

def require_claim_epoch(*,submitted_epoch,latest_terminal_epoch=0,prior_lease_expires_at_ms=None,now_ms=None,prior_epoch_expired=False):
 """Admit a claim epoch: no jumps, and takeover only after prior lease expiry + expiry record."""
 submitted=integer(submitted_epoch,"/logical_epoch",1)
 expected=expected_claim_epoch(latest_terminal_epoch)
 if submitted!=expected:fail("/logical_epoch","epoch jump", "G_INVALID_ARTIFACT")
 if submitted==1:return True
 if not prior_epoch_expired:fail("/logical_epoch","takeover requires prior expiry",G_CLAIM_CONFLICT)
 if prior_lease_expires_at_ms is not None and now_ms is not None and not lease_is_expired(prior_lease_expires_at_ms,now_ms):
  fail("/logical_epoch","takeover before expiry",G_CLAIM_CONFLICT)
 return True

def require_completion_authority(*,claim_cid,fencing_token,accepted_claim_cid,current_fencing_token,lease_expires_at_ms,now_ms):
 """Authorize exclusive completion; expired leases and stale fences fail closed."""
 cid(claim_cid,"/claim_cid");cid(accepted_claim_cid,"/accepted_claim_cid")
 presented=integer(fencing_token,"/fencing_token",1);current=integer(current_fencing_token,"/current_fencing_token",1)
 if not lease_is_live(lease_expires_at_ms,now_ms):fail("/lease_expires_at_ms","expired lease cannot complete",G_STALE_FENCE)
 if presented<current:fail("/fencing_token","stale fencing token",G_STALE_FENCE)
 if claim_cid!=accepted_claim_cid or presented!=current:fail("/claim_cid","claim conflict",G_CLAIM_CONFLICT)
 return True

def resolve_claims(claims,*,logical_epoch,prior_fencing_token=0,now_ms,requested_lease_ms=None,resolver_did="did:web:resolver.example"):
 """Pick the winner, issue fence+lease fields for an accepted ClaimResolution payload fragment."""
 winner=select_winning_claim(claims)
 epoch=integer(logical_epoch,"/logical_epoch",1)
 if winner["logical_epoch"]!=epoch:fail("/logical_epoch","mixed epoch claims")
 lease_ms=integer(requested_lease_ms if requested_lease_ms is not None else winner.get("requested_lease_ms",LIMITS["min_lease_ms"]),"/requested_lease_ms",LIMITS["min_lease_ms"],LIMITS["max_lease_ms"])
 fence=next_fencing_token(epoch,prior_fencing_token)
 return {"accepted_claim_cid":winner["claim_cid"],"logical_epoch":epoch,"fencing_token":fence,"lease_expires_at_ms":integer(now_ms,"/now_ms")+lease_ms,"outcome":"accepted","resolver_did":string(resolver_did,"/resolver_did"),"considered_claim_cids":sorted(x["claim_cid"] for x in claims)}
