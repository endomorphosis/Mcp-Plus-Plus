import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { derivePriorityTuple, ProfileGValidationError, validateProfileGArtifact } from '../profileG';
const vectors=(name:string)=>JSON.parse(readFileSync(join(__dirname,'../../../conformance/vectors',name),'utf8'));
describe('Profile G canonical codec',()=>{
 it.each(vectors('profile_g_artifacts_valid.json').cases)('$id has its canonical CID',(v:any)=>expect(validateProfileGArtifact(v.kind,v.payload,v.negotiated_limits)).toBe(v.expected_cid));
 it.each(vectors('profile_g_artifacts_invalid.json').cases)('$id fails deterministically',(v:any)=>{try{validateProfileGArtifact(v.kind,v.payload,v.negotiated_limits);throw Error('accepted')}catch(e){expect(e).toBeInstanceOf(ProfileGValidationError);expect([(e as any).code,(e as any).path]).toEqual([v.expected_error,v.expected_path]);}});
 it('derives priority',()=>{const c=vectors('profile_g_artifacts_valid.json').cases.find((x:any)=>x.kind==='TaskSpec').expected_cid;expect(derivePriorityTuple({ready:true,deadline_class:1,risk_action:'allow',age_bucket:12,expected_value_millionths:700000,resource_fit_millionths:900000,retry_not_before_ms:0,task_cid:c})).toEqual([0,1,0,-12,-700000,-900000,0,c]);});
});
