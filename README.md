# Portal de Montagem de Fichas — Espaço Viva

Interface web (Streamlit) para montar fichas de treino usando os blocos modulares cadastrados no Actuar.

## Como rodar

```powershell
cd C:\musculação
& "C:\Users\labcl\AppData\Local\Programs\Python\Python312\python.exe" -m pip install -r portal/requirements.txt
& "C:\Users\labcl\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run portal/app.py --server.headless true
```

Acesse `http://localhost:8501`.

## Funcionalidades

1. **Montar Ficha** — preencha dados do aluno e receba blocos recomendados.
2. **Catálogo de Blocos** — navegue pelos 104 blocos por categoria.
3. **Exercícios** — consulte a biblioteca de 404 exercícios do Actuar.

## Autenticação

O portal lê o token JWT de `C:\musculação\scripts\token_state.json`. Se expirar, rode:

```powershell
python scripts/capturar_token.py
```

## Limitações físicas suportadas

- Joelho, coluna, lombar, quadril, tornozelo
- Ombro, punho, hernia de disco, tendinite, bursite, LER/DORT
- Hipertensao, diabetes, cardiopatia, asma
- Gestacao, obesidade, idoso 60+
