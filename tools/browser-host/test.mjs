import test from 'node:test';
import assert from 'node:assert/strict';
import zlib from 'node:zlib';
import {parseSitevault} from './server.mjs';
function vault({origin='https://chatgpt.com',encrypted=false}={}){const h={version:3,name:'Unit',createdAt:new Date().toISOString(),encrypted,codec:'gzip',source:{origin}},v={source:{origin},cookies:[{name:'unit',value:'secret-value',domain:'chatgpt.com',path:'/',secure:true,httpOnly:true,sameSite:'lax',hostOnly:true}],frames:[]},hb=Buffer.from(JSON.stringify(h)),payload=zlib.gzipSync(Buffer.from(JSON.stringify(v))),head=Buffer.alloc(15);head.write('SITEVAULT3\n',0);head.writeUInt32LE(hb.length,11);return Buffer.concat([head,hb,payload])}
test('parses direct ChatGPT SiteVault and maps usable cookies',()=>{const x=parseSitevault(vault());assert.equal(x.cookies.length,1);assert.equal(x.cookies[0].name,'unit');assert.equal(x.cookies[0].url,'https://chatgpt.com/');assert.equal(x.cookies[0].httpOnly,true)});
test('rejects foreign and encrypted SiteVaults',()=>{assert.throws(()=>parseSitevault(vault({origin:'https://example.com'})));assert.throws(()=>parseSitevault(vault({encrypted:true})))});
