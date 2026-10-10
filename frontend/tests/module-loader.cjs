const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function context(value){
 for(const target of new Set([value,value.root,value.window].filter(v=>v && typeof v==='object'))){
  let fetch=target.fetch;
  Object.defineProperty(target,'fetch',{configurable:true,get(){return function(url,options){
   if(String(url).endsWith('/sessao/local'))return Promise.resolve({ok:true,status:200,text:async()=>JSON.stringify({csrf:'FICTICIO-CSRF-APENAS-TESTES-UNITARIOS'})});
   return fetch.call(this,url,options);
  };},set(fn){fetch=fn;}});
 }
 const ctx=vm.createContext(value);
 for(const f of fs.readdirSync(path.join(__dirname,'../js/features')).filter(f=>f.endsWith('.js')))
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/features',f),'utf8'),ctx);
 ctx.apiFeature=()=>ctx.OnPontoApi.create(ctx);
 ctx.navigationFeature=()=>ctx.OnPontoNavigation.create(ctx);
 ctx.importacaoFeature=()=>ctx.OnPontoImportacao.create(ctx);
 ctx.storeFeature=()=>ctx.OnPontoStore.create(ctx);
 ctx.conferenciaFeature=()=>ctx.OnPontoConferencia.create(ctx);
 ctx.relatoriosFeature=()=>ctx.OnPontoRelatorios.create(ctx);
 ctx.escalasFeature=()=>ctx.OnPontoEscalas.create(ctx);
 ctx.screenEscalasFeature=()=>ctx.OnPontoScreenEscalas.create(ctx);
 ctx.screenImportacaoFeature=()=>ctx.OnPontoScreenImportacao.create(ctx);
 ctx.screenConferenciaFeature=()=>ctx.OnPontoScreenConferencia.create(ctx);
 ctx.screenRelatoriosFeature=()=>ctx.OnPontoScreenRelatorios.create(ctx);
 return ctx;
}
module.exports={context};
