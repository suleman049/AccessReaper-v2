// Build an explicit, clean static deployment directory. Never publish repository internals.
const fs=require('node:fs'),path=require('node:path');
const root=fs.realpathSync(__dirname),output=path.resolve(root,'dist');
if(output!==path.join(root,'dist')||!output.startsWith(root+path.sep))throw new Error('Unsafe output directory.');
if(fs.existsSync(output)&&fs.lstatSync(output).isSymbolicLink())throw new Error('Build output must not be a link.');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const files=new Set(['index.html','assets/accessreaper-logo.png']);
for(const match of html.matchAll(/(?:src|href)="([^"]+)"/g)){
  const name=match[1];if(/^(?:https?:|#|data:)/.test(name))continue;
  if(!/^(?:[a-z0-9-]+\.(?:js|css)|assets\/[a-z0-9-]+\.(?:png|jpg|svg|ico))$/i.test(name))throw new Error('Unexpected site reference: '+name);
  files.add(name);
}
for(const file of files){const real=fs.realpathSync(path.join(root,file));if(!real.startsWith(root+path.sep)||!fs.statSync(real).isFile())throw new Error('Invalid site file: '+file);}
// The resolved path above is a dedicated generated directory within this checkout.
fs.rmSync(output,{recursive:true,force:true});fs.mkdirSync(output,{recursive:true});
for(const file of files){const destination=path.join(output,file);fs.mkdirSync(path.dirname(destination),{recursive:true});fs.copyFileSync(path.join(root,file),destination);}
console.log(`Hosting build ready: ${files.size} site files in dist/.`);
