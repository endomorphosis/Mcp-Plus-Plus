/** Machine-readable TypeScript side of the Profile H cross-runtime gate. */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { canonicalProfileHBytes, decodeX402Header, encodeX402Header, ProfileHValidationError, validateProfileHArtifact, validateReplay, validateRequestBinding } from './src/profileH.js';
const root=process.argv[2]; if(!root)throw new Error('vector directory argument required');
const load=(name:string)=>JSON.parse(readFileSync(join(root,name),'utf8'));
const valid=load('profile_h_artifacts_valid.json'),transport=load('profile_h_transport_valid.json'),invalid=load('profile_h_invalid.json');
const byId=new Map(valid.cases.map((x:any)=>[x.id,x])),report:any={artifacts:{},transport:{},invalid:{}};
for(const x of valid.cases)report.artifacts[x.id]={canonical:Buffer.from(canonicalProfileHBytes(x.payload)).toString('base64'),cid:validateProfileHArtifact(x.kind,x.payload,{},x.now_ms)};
for(const x of transport.cases){const header=encodeX402Header(x.kind,x.payload);report.transport[x.id]={canonical:Buffer.from(canonicalProfileHBytes(x.payload)).toString('base64'),header,decoded:decodeX402Header(x.kind,header)};}
for(const x of invalid.cases){try{invoke(x);report.invalid[x.id]={accepted:true};}catch(e){if(!(e instanceof ProfileHValidationError))throw e;report.invalid[x.id]={code:e.code,path:e.path};}}
process.stdout.write(JSON.stringify(report));
function invoke(x:any):void{if(x.operation==='decode'){decodeX402Header(x.kind,x.encoded);return;}if(x.operation==='replay'){validateReplay(new Set([x.commitment]),x.commitment);return;}const source=structuredClone(byId.get(x.source) as any),payload=source.payload;if(x.operation==='artifact-mutate')payload[x.mutation.path]=x.mutation.value;if(x.operation==='artifact-redaction')payload.requirements[0].extra.walletAddress='0xsecret';if(x.append_requirement)payload.requirements.push(structuredClone(payload.requirements[0]));if(['artifact','artifact-mutate','artifact-redaction'].includes(x.operation))validateProfileHArtifact(source.kind,payload,x.limits??{},x.now_ms);else if(x.operation==='binding')validateRequestBinding(x.expected_request_cid,payload);}
