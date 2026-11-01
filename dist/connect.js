'use strict';
function hostOrigin(value){
  const url=new URL(value);
  if(url.protocol!=='https:' || url.username || url.password || url.search || url.hash || !['','/'].includes(url.pathname))throw new Error('Enter an HTTPS origin only, without credentials, paths, pairing codes or owner tokens.');
  if(['localhost','127.0.0.1','[::1]'].includes(url.hostname))throw new Error('Use your computer’s trusted HTTPS address. A phone’s localhost points to the phone.');
  return url.origin+'/';
}
document.getElementById('connect-form').addEventListener('submit',event=>{
  event.preventDefault();
  try{location.assign(hostOrigin(document.getElementById('host-url').value.trim()));}
  catch(error){document.getElementById('connect-error').textContent=error.message;}
});
