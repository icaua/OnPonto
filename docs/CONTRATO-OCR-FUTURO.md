# Contrato para branch futura de OCR

Não há OCR nesta iniciativa: nenhum endpoint, modelo, biblioteca ou serviço externo. DTOs em `backend/app/evidencias/ocr_contrato.py` reservam contrato sem efeitos. JPG/PNG representam página 1; PDF pode ter várias páginas. Documento identifica evidência preservada no DB; funcionário e competência são escolhas humanas explícitas.

```json
{
  "documento_id": 17,
  "funcionario_id": 4,
  "competencia_id": 9,
  "pagina": 2,
  "campos": [{
    "campo": "entrada",
    "valor": null,
    "confianca": null,
    "origem": "região ilegível",
    "recorte": {"x": 0.1, "y": 0.2, "largura": 0.25, "altura": 0.1},
    "revisao_humana": "pendente"
  }],
  "revisao_humana": "pendente"
}
```

Recorte usa coordenadas normalizadas dentro da página; confiança é 0–1 ou desconhecida. Valor ilegível fica vazio e pendente. A revisão futura apresentará imagem e sugestão lado a lado, preservando origem por campo. Aceitar uma sugestão não equivale a conferir/fechar um dia: confirmação transacional, revisão otimista e regras oficiais continuam obrigatórias. Desenvolvimento funcional ocorrerá somente em branch futura autorizada.
