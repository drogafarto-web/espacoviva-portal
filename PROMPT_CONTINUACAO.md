# Prompt de Continuacao — App Montagem de Fichas Espaco Viva

## Escopo
Voce esta trabalhando em um portal Streamlit (`C:/musculacao/portal/app.py`) conectado ao sistema Actuar da Academia Espaco Viva.

## Contexto imediato
- O app ja esta funcional em `http://localhost:8501`.
- 104 blocos modulares estao cadastrados no Actuar como `PredefinedTraining`.
- A logica de montagem de ficha (`montar_ficha`) ja funciona com tabela de decisao + heuristica.

## Antes de qualquer alteracao
1. Carregue `portal/CONTEXTO_APP.md`.
2. Verifique o token em `scripts/token_state.json` (campo `token`). Se estiver expirado, rode `python scripts/capturar_token.py`.
3. Teste a ultima versao do portal: use Python 3.12 (`C:/Users/labcl/AppData/Local/Programs/Python/Python312/python.exe`) porque o streamlit so esta instalado la.

## Comandos uteis
```powershell
python scripts/capturar_token.py
& "C:/Users/labcl/AppData/Local/Programs/Python/Python312/python.exe" -m py_compile portal/app.py
& "C:/Users/labcl/AppData/Local/Programs/Python/Python312/python.exe" -m streamlit run portal/app.py --server.headless true
```

## Restricoes de codigo
- Nao use emojis na saida do terminal/logs; Streamlit consegue renderizar alguns, mas o console Windows (cp1252) quebra.
- Duplique/adapte sempre `mcp_servers/actuar_treino/client.py` para chamadas raw TLS + DoH ao Actuar.
- A API do Actuar usa OData V4. `PredefinedTrainingItems` eh propriedade de navegacao: nao use em `$select`.

## Proxima funcionalidade provavel (quando o usuario pedir evoluir)
Salvar a ficha montada no aluno (criar `StudentTrainingSheet` via API), nao apenas recomendar blocos.
