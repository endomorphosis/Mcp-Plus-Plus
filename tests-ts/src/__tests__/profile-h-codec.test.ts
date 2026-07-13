import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { canonicalProfileHBytes, decodeX402Header, encodeX402Header, ProfileHValidationError, validateProfileHArtifact, validateReplay, validateRequestBinding } from '../profileH';
const load=(name:string)=>JSON.parse(readFileSync(join(__dirname,'../../../conformance/vectors',name),'utf8'));
const valid=load('profile_h_artifacts_valid.json'), transport=load('profile_h_transport_valid.json'), invalid=load('profile_h_invalid.json');
const byId=new Map(valid.cases.map((x:any)=>[x.id,x]));

describe('Profile H canonical codec',()=>{
 it.each(valid.cases)('$id has pinned canonical bytes and CID',(x:any)=>{
  expect(validateProfileHArtifact(x.kind,x.payload,{},x.now_ms)).toBe(valid.expected_cids[x.id]);
  expect(Buffer.from(canonicalProfileHBytes(x.payload)).length).toBeGreaterThan(0);
 });
 it.each(transport.cases)('$id has pinned x402 bytes',(x:any)=>{const e=transport.expected_outputs?.[x.id]??{};const canonical=x.expected_canonical||e.canonical,header=x.expected_header||e.header;expect(Buffer.from(canonicalProfileHBytes(x.payload)).toString()).toBe(canonical);expect(encodeX402Header(x.kind,x.payload)).toBe(header);expect(decodeX402Header(x.kind,header)).toEqual(x.payload);});
 it.each(invalid.cases)('$id fails with a stable code and path',(x:any)=>{let thrown:unknown;try{invoke(x);}catch(e){thrown=e;}expect(thrown).toBeInstanceOf(ProfileHValidationError);expect([(thrown as ProfileHValidationError).code,(thrown as ProfileHValidationError).path]).toEqual([x.expected_error,x.expected_path]);});
});
function invoke(x:any):void{if(x.operation==='decode'){decodeX402Header(x.kind,x.encoded);return;}if(x.operation==='replay'){validateReplay(new Set([x.commitment]),x.commitment);return;}const source=structuredClone(byId.get(x.source) as any),payload=source?.payload;if(x.operation==='artifact-mutate')payload[x.mutation.path]=x.mutation.value;if(x.operation==='artifact-redaction')payload.requirements[0].extra.walletAddress='0xsecret';if(x.append_requirement)payload.requirements.push(structuredClone(payload.requirements[0]));if(['artifact','artifact-mutate','artifact-redaction'].includes(x.operation))validateProfileHArtifact(source.kind,payload,x.limits??{},x.now_ms);else if(x.operation==='binding')validateRequestBinding(x.expected_request_cid,payload);}
