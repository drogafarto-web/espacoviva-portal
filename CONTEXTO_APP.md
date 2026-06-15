# Contexto do App — Montagem de Fichas Espaço Viva

## Visão geral

Portal web (Streamlit) + backend de decisão para montar fichas de treino a partir de **104 blocos modulares** previamente cadastrados no Actuar (`PredefinedTraining`).

Localização: `C:\musculação\portal\app.py`

## Componentes principais

| Componente | Função |
|---|---|
| `portal/app.py` | Interface Streamlit (3 abas) + lógica de montagem |
| `mcp_servers/actuar_treino/` | MCP server com 11 tools (`montar_ficha`, query/mutation) |
| `scripts/populate_blocos.py` | Popula/renova os blocos no Actuar |
| `scripts/capturar_token.py` | Renova o JWT Bearer usado pelo portal |

## Como rodar

Requer **Python 3.12** (streamlit instalado apenas lá).

```powershell
cd C:\musculação
python scripts/capturar_token.py
& "C:\Users\labcl\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run portal/app.py --server.headless true
```

Acesse `http://localhost:8501`.

## Lógica de montagem (`montar_ficha`)

1. TABELA_DECISAO com 12 perfis fixos cobre os casos comuns por sexo/objetivo/nível.
2. Se não houver match, `_montar_heuristico()` escolhe por divisão e volume.
3. Busca blocos compatíveis na API (`/Odata/PredefinedsTrainings`) usando prefixo de categoria.
4. `_filtrar_limitacoes()` remove blocos inadequados (ex: agachamento para joelho).
5. `_verificar_volume()` garante séries e duração dentro dos limites do nível.
6. Adiciona recomendações de cardio/abdômen quando aplicável.

### Divisão preferida

- **Automatica**: deixa o algoritmo escolher.
- **Full Body / Upper/Lower / PPL / A-B-C / Funcional**: força a divisão escolhida via `_ajustar_blocos_para_divisao`.

## Limitações físicas suportadas

As 19 opções atuais cobrem as principais restrições de alunos brasileiros: joelho, coluna, lombar, quadril, tornozelo, ombro, punho, hérnia de disco, tendinite, bursite, LER/DORT, hipertensão, diabetes, cardiopatia, asma, gestação, obesidade, idoso 60+.

A análise automatizada das inscrições no `PersonsList` não foi possível porque esse endpoint retorna chunks truncados; a lista foi baseada nas condições mais frequentes em academias.

## Problemas conhecidos

1. **Token expira em ~2h**: rode `scripts/capturar_token.py`.
2. **PersonsList truncado**: endpoint retorna resposta chunked incompleta; use `Odata/Persons` para leituras maiores.
3. **Emojis removidos da UI**: console Windows (cp1252) quebra com emojis; o app usa labels sem emoji.

## Próximos passos sugeridos

- [ ] Implementar persistência de fichas montadas no Actuar (salvar `StudentTrainingSheet`).
- [ ] Integrar tela de seleção de alunos com `PersonsList`/Persons.
- [ ] Criar relatório de uso por treinador/bloco.
- [ ] Melhorar o algoritmo heurístico com feedback dos treinadores.
