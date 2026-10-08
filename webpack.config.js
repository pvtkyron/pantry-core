const path=require('path');

module.exports=(env={},argv={})=>{const prod=argv.mode==='production';return{
  mode:prod?'production':'development',
  cache:{type:'filesystem',buildDependencies:{config:[__filename]}},
  module:{rules:[{test:/\.ts$/,exclude:/node_modules/,loader:'ts-loader'}]},
  resolve:{extensions:['.ts','.js'],alias:{'@framework':path.resolve(__dirname,'src/SDKv4/Framework/src')}},
  entry:['./src/SDKv4/main.ts','./src/SDKv2/mainV2.js'],
  output:{path:path.resolve(__dirname,'dist'),filename:'live2d_bundle.js',publicPath:'./dist/',hashFunction:'sha256',clean:true},
  optimization:{minimize:prod},
  devtool:prod?false:'inline-source-map',
  performance:{hints:'error',maxEntrypointSize:600000,maxAssetSize:600000},
  devServer:{contentBase:path.resolve(__dirname,'.'),watchContentBase:true,inline:true,hot:true,port:5001,host:'0.0.0.0',compress:true,useLocalIp:true,writeToDisk:true}
}};
