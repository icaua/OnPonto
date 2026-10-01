const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup() {
  const c={URLSearchParams, localStorage:{getItem:()=>null}}; c.window=c;
  vm.createContext(c);
  for (const file of ['mocks','utils','components','screens']) vm.runInContext(fs.readFileSync(path.join(__dirname,'../js/'+file+'.js'),'utf8'),c);
  return c;
}
const count=(html,re)=>(html.match(re)||[]).length;
const day={id:1,date:'2026-09-08',originalPunches:['08:00:00','12:00:00','17:00:00'],current:{entry:'08:00'}};

test('desconsiderar batida aparece so em dia com problema e edicao aberta',()=>{
  const C=setup().OnPontoComponents;
  assert.equal(count(C.DayDetailsPanel({day}),/data-action="discard-original-punch"/g),0);
  assert.equal(count(C.DayDetailsPanel({day:{...day,problema:true}}),/data-action="discard-original-punch"/g),3);
  assert.equal(count(C.DayDetailsPanel({day:{...day,problema:true},readonly:true}),/discard-original-punch|assign-original-punch/g),0);
  assert.equal(count(C.DayDetailsPanel({day:{...day,problema:true,confirmed:true}}),/discard-original-punch|assign-original-punch/g),0);
});

test('ocorrencia integral nao oferece atribuicao nem desconsideracao; parcial mantem',()=>{
  const C=setup().OnPontoComponents;
  const integral={...day,problema:true,occurrences:[{id:1,tipo:'ATESTADO',hora_inicio:null}]};
  assert.equal(count(C.DayDetailsPanel({day:integral}),/discard-original-punch|assign-original-punch/g),0);
  const parcial={...day,problema:true,occurrences:[{id:1,tipo:'ATESTADO',hora_inicio:'08:00:00'}]};
  assert.equal(count(C.DayDetailsPanel({day:parcial}),/assign-original-punch/g),2);
});

test('batida desconsiderada fica riscada, com motivo escapado e restauracao',()=>{
  const C=setup().OnPontoComponents;
  const html=C.DayDetailsPanel({day:{...day,problema:true,batidas_desconsideradas:[{indice:1,horario:'12:00:00',justificativa:'Duplicada <b>x</b>'}]}});
  assert.match(html,/is-discarded/); assert.match(html,/<s>12:00:00<\/s>/);
  assert.match(html,/data-action="restore-original-punch" data-day-id="1" data-punch-index="1"/);
  assert.doesNotMatch(html,/<b>x<\/b>/);
  assert.equal(count(html,/assign-original-punch/g),1);
  const cinco=C.DayDetailsPanel({day:{...day,originalPunches:['07:00:00','08:00:00','12:00:00','13:00:00','17:00:00'],batidas_desconsideradas:[{indice:0,horario:'07:00:00',justificativa:'Duplicada no relógio'}]}});
  assert.equal(count(cinco,/assign-original-punch/g),3);
});

test('importacoes agrupam pendencias por pessoa e listam ignorados',()=>{
  const c=setup(), data=c.OnPontoMocks.getFreshData(), company=data.companies[0];
  const competence=data.competencies.find(item=>String(item.companyId)===String(company.id));
  const registros=[{registro_id:'a',data:'2026-09-01',mensagem:'Funcionário não cadastrado para esta empresa'},{registro_id:'b',data:'2026-09-02',mensagem:'Quantidade ímpar de marcações; Funcionário não cadastrado para esta empresa'}];
  const file={id:77,competenceId:competence.id,competencia_id:competence.id,name:'relogio.txt',controle_importacao:{estado:'confirmada',pendencias:registros}};
  data.files=(data.files||[]).filter(f=>String(f.competenceId)!==String(competence.id)).concat([file]); data.arquivos=data.files;
  const state={route:'imports',selectedCompanyId:company.id,selectedCompetenceId:competence.id,apiMode:'online'};
  assert.match(c.OnPontoScreens.render('imports',state,data,c.OnPontoComponents),/Agrupando pendências por pessoa/);
  data.importGroups={77:{key:'a,b',groups:[{codigo_origem:'900',nome_origem:'Diretora <Fictícia>',funcionario_encontrado:false,registros}]}};
  data.ignoredPeople={[company.id]:[{id:5,codigo_origem:'1',nome_origem:'Gestão Fictícia',justificativa:'Sócia, não controla jornada.',criada_em:'2026-09-30T12:00:00'}]};
  const html=c.OnPontoScreens.render('imports',state,data,c.OnPontoComponents);
  assert.match(html,/2 registros pendentes impedem o fechamento/);
  assert.match(html,/data-action="ignore-import-person" data-file-id="77" data-group-index="0"/);
  assert.match(html,/Excluir 2 deste arquivo/);
  assert.match(html,/import-pending-group__what">2 registros pendentes · Quantidade ímpar de marcações</);
  assert.doesNotMatch(html,/<Fictícia>/);
  assert.match(html,/Pessoas ignoradas nas importações desta empresa \(1\)/);
  assert.match(html,/data-action="unignore-import-person" data-rule-id="5"/);
});
