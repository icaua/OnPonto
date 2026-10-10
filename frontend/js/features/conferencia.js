(function(root,factory){
  var api=factory();
  if(typeof module === "object" && module.exports) module.exports=api;
  root.OnPontoConferencia=api;
})(typeof window !== "undefined" ? window : globalThis,function(){
  "use strict";
  function create(deps){
    deps=deps || {};
    var Utils=deps.Utils;
    var currentSlots=deps.currentSlots;
    var state=deps.state;
  function dayIsConfirmed(day) {
    if (!day) return false;
    return day.confirmed === true || day.conferido === true || day.reviewState === "confirmed" || (day.review && day.review.state === "confirmed");
  }
  function dayHasProblem(day) {
    if (day.problema !== undefined) return day.problema === true;
    return day.pendingCalculation === true || day.pendente_calculo === true || (day.issues || []).some(function (i) { return !i.resolved && i.type !== "review" && i.type !== "manual_change"; });
  }
  function captureReviewScroll(main, key) {
    if (!key || main.dataset.reviewKey !== key) return null;
    return [".attendance-table-wrap", ".review-context"].map(function (selector) {
      var element = main.querySelector(selector);
      return { selector: selector, top: element ? element.scrollTop : 0, left: element ? element.scrollLeft : 0 };
    });
  }
  function restoreReviewScroll(main, positions) {
    (positions || []).forEach(function (position) {
      var element = main.querySelector(position.selector);
      if (element) { element.scrollTop = position.top; element.scrollLeft = position.left; }
    });
  }
  function recalculateDay(day) {
    var result = Utils.calculateJourney(currentSlots(day), day.expectedMinutes || day.jornadaPrevistaMinutos);
    // O saldo definitivo depende das tolerâncias e ocorrências apuradas na API.
    if (state.apiMode === "online") { result.balanceMinutes = null;result.workedMinutes = null;day.calculoProvisorio=true; }
    day.workedMinutes = result.workedMinutes;
    day.jornadaApuradaMinutos = result.workedMinutes;
    day.balanceMinutes = result.balanceMinutes;
    day.saldoMinutos = result.balanceMinutes;
    if (day.current) {
      day.current.workedMinutes = result.workedMinutes;
      day.current.expectedMinutes = result.expectedMinutes;
      day.current.balanceMinutes = result.balanceMinutes;
    }
  }
    return Object.freeze({dayIsConfirmed:dayIsConfirmed,dayHasProblem:dayHasProblem,captureReviewScroll:captureReviewScroll,restoreReviewScroll:restoreReviewScroll,recalculateDay:recalculateDay});
  }
  function patchReview(main,markup){
    var template=main.ownerDocument.createElement("template");template.innerHTML=markup;
    function key(node){return node.nodeType===1 && node.getAttribute("data-day-id") ? node.nodeName+":"+node.getAttribute("data-day-id")+":"+(node.getAttribute("data-field") || "") : null;}
    function patch(current,next){
      if(current.nodeType!==next.nodeType || current.nodeName!==next.nodeName){current.replaceWith(next.cloneNode(true));return;}
      if(current.nodeType!==1){if(current.nodeValue!==next.nodeValue) current.nodeValue=next.nodeValue;return;}
      Array.from(current.attributes).forEach(function(a){if(!next.hasAttribute(a.name)) current.removeAttribute(a.name);});
      Array.from(next.attributes).forEach(function(a){if(current.getAttribute(a.name)!==a.value) current.setAttribute(a.name,a.value);});
      if(current.nodeName==="INPUT" || current.nodeName==="TEXTAREA"){
        if(current!==main.ownerDocument.activeElement && current.value!==next.value) current.value=next.value;
        if(current.type==="checkbox") current.checked=next.checked;
      }
      children(current,next);
    }
    function children(current,next){
      var existing=Array.from(current.childNodes), byKey=new Map();
      existing.forEach(function(n){if(key(n)) byKey.set(key(n),n);});
      var desired=Array.from(next.childNodes);
      desired.forEach(function(n,i){
        var previous=key(n) ? byKey.get(key(n)) : current.childNodes[i];
        if(previous && key(previous) && key(previous)!==key(n)) previous=null;
        if(!previous){current.insertBefore(n.cloneNode(true),current.childNodes[i] || null);return;}
        if(previous!==current.childNodes[i]) current.insertBefore(previous,current.childNodes[i] || null);
        patch(previous,n);
      });
      while(current.childNodes.length>desired.length) current.lastChild.remove();
    }
    children(main,template.content);
  }
  return Object.freeze({create:create,patchReview:patchReview});
});
