// Harness de layout: anexado apenas aos HTMLs fictícios de validação.
window.addEventListener('load', function () {
  var blocks = Array.from(document.querySelectorAll('.espelho-pagina'));
  if (!blocks.length) blocks = [document.querySelector('main')];
  var results = blocks.map(function (block) {
    var header = block.querySelector('header').getBoundingClientRect();
    var footer = block.querySelector('footer').getBoundingClientRect();
    var rows = Array.from(block.querySelectorAll('tr.dia'));
    var mm = function (px) { return Math.round(px * 25.4 / 96 * 100) / 100; };
    return {
      linhas: rows.length,
      notas: block.querySelectorAll('.notas li').length,
      largura_mm: mm(block.querySelector('.dias').getBoundingClientRect().width),
      altura_conteudo_mm: mm(footer.bottom - header.top),
      altura_media_linha_mm: rows.length ? mm(rows.reduce(function (n,r) { return n + r.getBoundingClientRect().height; },0) / rows.length) : 0,
      altura_util_mm: 277,
      cabe_em_uma_pagina: mm(footer.bottom - header.top) <= 277,
      campos_assinatura: block.querySelectorAll('.data-assinatura').length,
    };
  });
  var output = document.createElement('pre');
  output.id = 'validacao-layout';
  output.textContent = JSON.stringify(results, null, 2);
  document.body.appendChild(output);
  document.title = results.every(function (r) { return r.cabe_em_uma_pagina && r.largura_mm <= 190.1; }) ? 'LAYOUT APROVADO' : 'LAYOUT COM CONTINUAÇÃO';
});
