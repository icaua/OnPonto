(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoEscalas=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var data=deps.data;
  function dialogTimeMinutes(value) {
    var match = String(value || "").match(/^(\d{2}):(\d{2})$/);
    if (!match) return null;
    return Number(match[1]) * 60 + Number(match[2]);
  }
  function nullableDialogNumber(value) {
    return value === "" || value === null || value === undefined ? null : Number(value);
  }
  function hourPolicyFields(entity) {
    var p = entity && entity.politica_horas || {};
    var explicit = function(v){ return v.politica_modo !== "legado"; };
    var bank = function(v){ return explicit(v) && v.politica_modo !== "folha"; };
    var choices = function(items){ return items.map(function(i){return {value:i[0],label:i[1]};}); };
    var field = function(name,label,type,value,extra){return Object.assign({name:"politica_"+name,label:label,type:type,value:value == null ? "" : value,visibleWhen:explicit},extra || {});};
    var fields = [
      field("modo","Destino das horas extras","select",p.modo || "legado",{fullWidth:true,visibleWhen:null,options:choices([["legado","Manter configuração anterior"],["folha","100% folha"],["banco","100% banco"],["misto","Dividir entre folha e banco"]]),help:"Políticas explícitas se aplicam às competências abertas. Fechamentos preservam a regra usada."}),
      field("referencia","Referência da regra (opcional)","text",p.referencia,{fullWidth:true,maxlength:240}),
      field("percentual_folha","Parcela destinada à folha (%)","number",p.percentual_folha == null ? 50 : p.percentual_folha,{required:true,min:0.0001,max:99.9999,step:0.0001,visibleWhen:function(v){return v.politica_modo === "misto";},help:"O restante, até 100%, será destinado ao banco. Atrasos são tratados separadamente."}),
      field("adicional_folha_percentual","Adicional da folha (%)","number",p.adicional_folha_percentual,{min:0,max:1000,step:0.01,help:"Informe o adicional aplicável. Sem definição, dias com HE para folha exigirão revisão."}),
      field("ciclo_dias","Duração do ciclo (dias)","number",p.ciclo_dias,{visibleWhen:bank,required:true,min:1,max:3660,step:1}),
      field("inicio_ciclo","Início de um ciclo de referência","date",p.inicio_ciclo,{visibleWhen:bank,required:true,help:"Define períodos consecutivos com a duração informada, inclusive antes desta data."}),
      field("debitar_atrasos","Atrasos geram débito no banco?","select",String(p.debitar_atrasos !== false),{visibleWhen:bank,options:choices([["true","Sim"],["false","Não"]])}),
      field("permite_saldo_negativo","Permitir saldo negativo no ciclo?","select",String(p.permite_saldo_negativo !== false),{visibleWhen:bank,options:choices([["true","Sim"],["false","Não"]])})
    ];
    [["normal","Dia normal"],["sabado","Sábado"],["domingo","Domingo"],["feriado","Feriado"]].forEach(function(entry){
      var key=entry[0],label=entry[1],rule=p[key] || {};
      fields.push(field(key+"_fator",label+": fator de crédito","number",rule.fator_banco == null ? 1 : rule.fator_banco,{visibleWhen:bank,required:true,min:0.0001,max:10,step:0.0001}),
        field(key+"_base",label+": base do fator","select",rule.base_fator || "decidir",{visibleWhen:bank,options:choices([["decidir","Definir antes de apurar fator diferente de 1"],["parcela_banco","Aplicar sobre a parcela destinada ao banco"],["extra_integral","Aplicar sobre toda a HE apurada"]])}),
        field(key+"_adicional",label+": adicional específico (%)","number",rule.adicional_folha_percentual,{min:0,max:1000,step:0.01,help:"Em branco, segue o adicional da folha acima."}));
    });
    [["fim_ciclo_credor","Crédito restante no fim do ciclo",[["decidir","Decisão humana pendente"],["pagar","Encaminhar horas para pagamento"]]],
      ["fim_ciclo_devedor","Débito restante no fim do ciclo",[["decidir","Decisão humana pendente"],["transportar","Sinalizar transporte para outro ciclo"]]],
      ["desligamento_credor","Crédito no desligamento",[["decidir","Decisão humana pendente"],["pagar","Encaminhar horas para pagamento"]]],
      ["desligamento_devedor","Débito no desligamento",[["decidir","Decisão humana pendente"],["descontar","Encaminhar para desconto"],["dispensar","Sinalizar dispensa do débito"]]]].forEach(function(entry){
        fields.push(field(entry[0],entry[1],"select",p[entry[0]] || "decidir",{visibleWhen:bank,options:choices(entry[2]),help:"Gera indicação para conferência; qualquer baixa ou transporte exige ajuste justificado."}));
      });
    fields.push(field("adicional_saldo_percentual","Adicional do saldo credor a pagar (%)","number",p.adicional_saldo_percentual,{visibleWhen:bank,min:0,max:1000,step:0.01}));
    return fields;
  }
  function hourPolicyPayload(v) {
    if (v.politica_modo === "legado") return null;
    var folha = v.politica_modo === "folha" ? 100 : v.politica_modo === "banco" ? 0 : Number(v.politica_percentual_folha);
    var p={versao:1,modo:v.politica_modo,referencia:v.politica_referencia || null,percentual_folha:folha,
      percentual_banco:Number((100-folha).toFixed(4)),adicional_folha_percentual:nullableDialogNumber(v.politica_adicional_folha_percentual),
      debitar_atrasos:v.politica_debitar_atrasos === "true",permite_saldo_negativo:v.politica_permite_saldo_negativo === "true",
      ciclo_dias:folha === 100 ? null : Number(v.politica_ciclo_dias),inicio_ciclo:folha === 100 ? null : v.politica_inicio_ciclo,
      adicional_saldo_percentual:nullableDialogNumber(v.politica_adicional_saldo_percentual)};
    ["normal","sabado","domingo","feriado"].forEach(function(key){p[key]={fator_banco:folha === 100 ? 1 : Number(v["politica_"+key+"_fator"]),base_fator:v["politica_"+key+"_base"] || "decidir",adicional_folha_percentual:nullableDialogNumber(v["politica_"+key+"_adicional"])};});
    ["fim_ciclo_credor","fim_ciclo_devedor","desligamento_credor","desligamento_devedor"].forEach(function(key){p[key]=v["politica_"+key] || "decidir";});
    return p;
  }
    return Object.freeze({dialogTimeMinutes:dialogTimeMinutes,nullableDialogNumber:nullableDialogNumber,hourPolicyFields:hourPolicyFields,hourPolicyPayload:hourPolicyPayload});
  }
  return Object.freeze({create:create});
});
