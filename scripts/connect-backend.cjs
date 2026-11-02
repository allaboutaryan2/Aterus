// Run after Render returns the actual URL. No unowned hostname is assumed.
const fs=require('node:fs'),path=require('node:path');
function configure(value){
  const url=new URL(value);
  if(url.protocol!=='https:' || url.username || url.password || url.search || url.hash || !['','/'].includes(url.pathname) || url.port)throw new Error('Supply the actual Render HTTPS origin only');
  if(!/^[a-z0-9-]+\.onrender\.com$/.test(url.hostname))throw new Error('Expected the deployed Render service hostname');
  const file=path.join(__dirname,'../vercel.json'),config=JSON.parse(fs.readFileSync(file));
  config.rewrites=[{source:'/api/releases',destination:url.origin+'/v1/releases'}];
  fs.writeFileSync(file,JSON.stringify(config,null,2)+'\n');
}
if(require.main===module){try{configure(process.argv[2]);console.log('Configured public release API; redeploy Vercel to apply.')}catch(e){console.error(e.message);process.exitCode=1}}
module.exports={configure};
