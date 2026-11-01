const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context=vm.createContext({URL,document:{getElementById:()=>({addEventListener(){}})}});
vm.runInContext(fs.readFileSync(__dirname+'/dist/connect.js','utf8'),context);
assert.equal(context.hostOrigin('https://my-aterus.example'),'https://my-aterus.example/');
for(const value of ['http://example.com','https://user:pass@example.com','https://example.com/#owner=secret','https://example.com/?code=x','https://example.com/path','https://127.0.0.1:4380'])assert.throws(()=>context.hostOrigin(value));
const html=fs.readFileSync(__dirname+'/dist/index.html','utf8');
for(const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)){const ref=match[1];if(!ref.startsWith('http') && ref!=='./')assert(fs.existsSync(__dirname+'/dist/'+ref),ref+' must exist');}
console.log('PASS: host navigation rejects credentials/tokens/non-HTTPS; portal links resolve');
