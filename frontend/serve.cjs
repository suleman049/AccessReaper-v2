// Dependency-free local server. Serves the website and assets, not project secrets.
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=__dirname,port=Number(process.env.PORT||4173);
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml','.ico':'image/x-icon'};
const allowed=new Set(fs.readdirSync(root).filter(name=>/\.(html|css|js)$/.test(name)));
if(!Number.isInteger(port)||port<1024||port>65535)throw new Error('Choose a local port between 1024 and 65535.');
const server=http.createServer((req,res)=>{
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{Allow:'GET, HEAD'});res.end();return;}
  let pathname;try{pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);}catch{res.writeHead(400);res.end('Invalid address');return;}
  if(pathname==='/')pathname='/index.html';
  const relative=pathname.replace(/^\/+/,''),file=path.resolve(root,relative),extension=path.extname(file).toLowerCase();
  if(!file.startsWith(root+path.sep)||!mime[extension]||(!allowed.has(relative)&&!relative.startsWith('assets/'))){res.writeHead(404);res.end('Not found');return;}
  fs.realpath(file,(err,real)=>{
    if(err||!real.startsWith(root+path.sep)){res.writeHead(404);res.end('Not found');return;}
    fs.stat(real,(err,stat)=>{
      if(err||!stat.isFile()){res.writeHead(404);res.end('Not found');return;}
      res.writeHead(200,{'Content-Type':mime[extension],'Content-Length':stat.size,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
      if(req.method==='HEAD'){res.end();return;}
      fs.createReadStream(real).on('error',()=>res.destroy()).pipe(res);
    });
  });
});
server.on('error',error=>{console.error(error.code==='EADDRINUSE'?`Port ${port} is already in use. Close the other server or choose a different PORT.`:'Could not start the local website.');process.exitCode=1;});
server.listen(port,'127.0.0.1',()=>console.log(`AccessReaper: http://localhost:${port}/#login\nKeep this window open. Press Ctrl+C to stop.`));
