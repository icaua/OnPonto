# Backend On Ponto

API FastAPI para o MVP do On Ponto.

## Instalação

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Execução

```bash
uvicorn app.main:app --reload
```

A API ficará disponível em:

- http://127.0.0.1:8000
- http://127.0.0.1:8000/docs

O SQLite será criado automaticamente em `backend/onponto.db`.
Os arquivos enviados serão salvos em `backend/uploads/`.
