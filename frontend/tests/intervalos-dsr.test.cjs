const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app.js'),'utf8');
function extract(name){const start=source.indexOf('  function '+name+'(');return source.slice(start,source.indexOf('\n  function ',start+1));}
function dialogFor(entity){
 let dialog,request;
 const ctx={currentCompany:()=>({id:1}),state:{apiMode:'online'},loadedCompanyScales:{1:true},companyScales:()=>entity?[entity]:[],
  idsEqual:(a,b)=>a===b,normalizedTime:x=>x||'',showDialog:d=>dialog=d,hourPolicyFields:()=>[],hourPolicyPayload:()=>null,
  nullableDialogNumber:x=>x==null||x===''?null:Number(x),dialogTimeMinutes:x=>Number(x.slice(0,2))*60+Number(x.slice(3,5)),
  apiRequest:async(url,config)=>{request=config.body;return config.body;},upsertEntity(){},scales:()=>[],normalizeScale:x=>x,
  compareEntityNames(){},invalidateCompanyCompetenceData(){},render(){},showToast(){}};
 require('./module-loader.cjs').context(ctx);vm.runInContext(extract('openScaleDialog'),ctx);ctx.openScaleDialog(entity?.id);
 return {dialog,request:()=>request};
}
test('edição preserva intervalo, DSR e jornada diária sem converter sábado salvo',async()=>{
 const entity={id:2,nome:'FICTÍCIA',modo_apuracao:'horario_fixo',horario_entrada_prevista:'09:00',horario_saida_prevista:'18:00',
  horario_saida_almoco_prevista:'12:00',horario_retorno_almoco_prevista:'13:00',tipo_intervalo:'fixo',registro_intervalo:'pre_assinalado',
  duracao_intervalo_minutos:60,regime_sabado:'trabalha',politica_dsr:{dia_descanso:0,descontar_feriados:false,referencia:'Política aprovada'},
  jornadas_semana:{'5':{jornada_minutos:240,horario_entrada_prevista:'08:00',horario_saida_prevista:'12:00',tipo_intervalo:'sem_intervalo',registro_intervalo:'batidas',duracao_intervalo_minutos:0}}};
 const a=dialogFor(entity),values=Object.fromEntries(a.dialog.fields.map(f=>[f.name,f.value]));
 assert.equal(values.sabado_proprio,'preservar');await a.dialog.onConfirm(values);
 const r=a.request();assert.equal(r.registro_intervalo,'pre_assinalado');assert.equal(r.duracao_intervalo_minutos,60);
 assert.equal(r.politica_dsr.dia_descanso,0);assert.equal(r.politica_dsr.descontar_feriados,false);assert.equal(r.politica_dsr.referencia,'Política aprovada');
 assert.equal(JSON.stringify(r.jornadas_semana),JSON.stringify(entity.jornadas_semana));
});
test('escala legada não recebe intervalo ou desconto DSR ao salvar',async()=>{
 const a=dialogFor({id:2,nome:'FICTÍCIA',modo_apuracao:'carga_horaria',jornada_seg_sex_horas:8});
 await a.dialog.onConfirm(Object.fromEntries(a.dialog.fields.map(f=>[f.name,f.value])));
 assert.equal(a.request().tipo_intervalo,null);assert.equal(a.request().politica_dsr,null);
});
test('resumo DSR preserva desconto pendente e renderiza dias disponíveis',()=>{
 const c={URLSearchParams,localStorage:{getItem:()=>null}};c.window=c;require('./module-loader.cjs').context(c);
 for(const f of ['mocks','utils','components','screens','banco-horas'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+f+'.js'),'utf8'),c);
 vm.runInContext(source.replace('\n  init();','\n root.testApi={normalizeCompetenceSummary};'),c);
 const summary=c.testApi.normalizeCompetenceSummary({resumo:[{funcionario_id:1,funcionario:'FICTÍCIO',dsr_dias:5,dsr_desconto_dias:null}]});
 assert.equal(summary.rows[0].dsrDiscount,null);assert.equal(summary.rows[0].dsrDays,5);
 const html=c.OnPontoScreens.renderCompetencySummary({apiMode:'online',selectedCompanyId:1,selectedCompetenceId:1},
  {companies:[{id:1,name:'FICTÍCIA'}],competencies:[{id:1,companyId:1,month:9,year:2026}],competenceSummaries:{1:summary}},c.OnPontoComponents);
 assert.match(html,/DSR/);assert.doesNotMatch(html,/NaN|undefined|null/);
});
