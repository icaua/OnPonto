# ADR 0002 — núcleo puro de apuração e contrato incompleto

Estado: aceito. Pacote 01, dependência 00 validada em `17c366c`.

## Decisão

Extrair o cálculo diário para `app/dominio/apuracao.py`, com dataclasses imutáveis para regra, marcações, calendário, funcionário e ocorrências. A orquestração carrega ORM e os adaptadores convertem seus valores antes da chamada. O módulo do núcleo importa sem site-packages, SQLAlchemy ou FastAPI. Interpretação de ocorrências e validação de batidas já puras são reutilizadas; classificação do dia é compartilhada com o backend.

Minutos são inteiros. O resultado novo distingue completo/incompleto/indisponível e usa `None` para durações não apuráveis. O adaptador de compatibilidade preserva os zeros e campos da API antiga, acompanhados das pendências existentes. Não trocar o contrato público nem reinterpretar duas batidas nesta fase. Horários previstos continuam exclusivamente na regra; nenhum helper grava marcações sintéticas.

Jornada com meia-noite permanece sem suporte: sequência invertida é incompleta/rejeitada, sem adicionar 24 horas. O frontend já rejeita ordem invertida e suas suites permanecem obrigatórias. Configuração de fuso, dia trabalhado e política noturna exige iniciativa futura.

Distribuição de HE/folha/banco segue no módulo de regras puro já existente; ledger, calendário mensal e queries continuam nos orquestradores. DSR ainda não implementado; decisão do pacote 04 permanece pendente.

## Aceite e rollback

Golden master do pacote 00 deve passar **sem regeneração**. Fixtures adicionais cobrem limites de tolerância, cronologia, falta, ocorrência, feriado e ausência de escala. Qualquer divergência bloqueia avanço. Nenhuma migração ou dado persistido é alterado; rollback consiste em reverter o commit.
