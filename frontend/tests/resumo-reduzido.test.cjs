const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
test('painel não busca dias; conferência não reutiliza resumo sem detalhes',async()=>{
 const urls=[];
 const c={URLSearchParams,setTimeout,clearTimeout,AbortController,localStorage:{getItem:()=>null},fetch:async url=>{
  urls.push(url);const body=url.includes('/apuracao')?{resumo:[],resumo_geral:{},competencia:{id:1,empresa_id:1,ano:2026,mes:9,status:'aberta'},
   ...(url.includes('/resumo')?{}:{marcacoes:[]})}:[];
  return {ok:true,text:async()=>JSON.stringify(body)};
 }};c.window=c;vm.createContext(c);
 for(const f of ['mocks','utils','components','screens'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+f+'.js'),'utf8'),c);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../app.js'),'utf8').replace('\n  init();','\n root.testApi={state,loadCompetenceData};'),c);
 c.testApi.state.apiMode='online';c.testApi.state.route='competency-summary';
 await c.testApi.loadCompetenceData(1);
 assert.equal(urls.length,1);assert.match(urls[0],/\/apuracao\/resumo\?/);
 c.testApi.state.route='review';await c.testApi.loadCompetenceData(1);
 assert.ok(urls.some(u=>/\/apuracao\?/.test(u)));assert.ok(urls.some(u=>/\/marcacoes\?/.test(u)));
});
