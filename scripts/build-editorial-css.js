const fs=require('fs'),path=require('path'),root=path.resolve(__dirname,'..'),V=JSON.parse(fs.readFileSync(path.join(root,'assets','blogfa-runtime-manifest.json'),'utf8')).version;
const files=[1,2,3,4,5,6].map(i=>path.join(root,'assets',`rev-editorial-${i}.css`)),css=`/* Project Rev Editorial ${V} merged */\n`+files.map(f=>fs.readFileSync(f,'utf8').replace(/\r\n/g,'\n').trimEnd()).join('\n')+'\n';
fs.writeFileSync(path.join(root,'assets','rev-editorial.css'),css);console.log(`Editorial CSS merged: ${Buffer.byteLength(css)}B / ${files.length} sources / ${V}`);
