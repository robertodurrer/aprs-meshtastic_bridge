# APRS ↔ Meshtastic Bridge

Gateway bidirecional entre redes Meshtastic e o ecossistema APRS, permitindo que operadores de radioamador licenciados troquem posição e mensagens entre os dois mundos através do APRS-IS.

Projeto experimental em desenvolvimento, validado em campo com hardware real (Heltec V3, T-Beam V0.7) e testado contra o APRS-IS público.

## Motivação

O Meshtastic resolve muito bem o problema de mesh local em LoRa, mas vive isolado do ecossistema APRS — que tem décadas de infraestrutura, milhares de estações, e o padrão consolidado entre radioamadores para rastreamento e mensagens. Este projeto constrói uma ponte entre os dois, restrita a operadores com indicativo de radioamador válido, respeitando a exigência de licenciamento do APRS.

## Arquitetura

```
[Nós Meshtastic]                    [Raspberry Pi — gateway]                  [Ecossistema APRS]
                                                                              
  OZHX (USB) ◄──RF mesh──┐                                                  
  OZHY (RF only)         │                                                  
  outros nós...          │                                                  
                          ▼                                                  
                  ┌───────────────┐         TCP/IP          ┌──────────────┐
                  │  gateway.py    │ ───────────────────────►│   APRS-IS    │
                  │  (Python)      │ ◄───────────────────────│ rotate.aprs2 │
                  └───────┬────────┘                          └──────┬───────┘
                          │                                          │
                          ▼                                          ▼
                  ┌───────────────┐                          ┌──────────────┐
                  │  SQLite        │                          │ iGate / Tracker│
                  │  operadores,   │                          │  RF 433MHz    │
                  │  posições,     │                          │  (CA2RXU)     │
                  │  mensagens     │                          └──────────────┘
                  └────────────────┘
```

Um único nó Meshtastic ("nó-ponte") fica permanentemente conectado ao Raspberry Pi via USB. Todos os demais nós participam apenas via RF mesh — o nó-ponte ouve o tráfego do canal dedicado e repassa ao gateway pela porta serial.

## Por que um canal dedicado

O tráfego da bridge não usa o canal público `LongFast` (PSK padrão `AQ==`). Um canal secundário, com PSK própria, isola o tráfego destinado à bridge do tráfego geral da malha, e permite políticas de uso distintas — por exemplo, restringir esse canal a operadores licenciados.

## Identidade e licenciamento

Apenas operadores com indicativo de radioamador válido participam da bridge. O cadastro exige:

- indicativo + SSID (ex: `PU2OZH-10`)
- passcode APRS-IS correspondente, validado contra o algoritmo padrão e, quando há conectividade, contra o próprio servidor APRS-IS antes de ativar o operador

Nós Meshtastic sem operador cadastrado são ignorados pela bridge — continuam funcionando normalmente na malha, apenas não participam do lado APRS.

## Funcionalidades implementadas

- Conexão resiliente ao nó Meshtastic via serial, com reconexão automática
- Cadastro de operadores com validação de passcode (CLI `manage.py`)
- Banco SQLite para operadores, posições e mensagens
- Publicação de posição Meshtastic → APRS-IS, em formato APRS padrão
- Envio de mensagens Meshtastic → APRS-IS, com reconhecimento de destino por callsign, controle de ACK e retry automático (até 3 tentativas)
- Ferramentas de diagnóstico: detecção de porta serial, escuta de pacotes em tempo real, envio de mensagem de teste

## Em desenvolvimento / próximos passos

- Mensagens APRS → Meshtastic (caminho de volta, ainda não implementado)
- Interface web de gerenciamento (cadastro, status em tempo real, log de mensagens)
- Hardening para operação 24/7 (systemd, watchdog, testes de campo prolongados)
- Possível bridge RF direta via TNC do iGate, para operação sem depender de internet

## Requisitos

- Raspberry Pi (testado em RPi 5, Debian 13 Trixie) ou qualquer Linux com Python 3.11+
- Nó Meshtastic conectado via USB, com um canal secundário dedicado configurado (PSK própria, diferente da PSK padrão do LongFast)
- Indicativo de radioamador válido e respectivo passcode APRS-IS

## Instalação

```bash
git clone git@github.com:robertodurrer/aprs-meshtastic_bridge.git
cd aprs-meshtastic_bridge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copie `config/config.example.json` para `config/config.json` e preencha com seu indicativo, passcode e índice do canal APRS dedicado.

## Uso básico

Cadastrar um operador:

```bash
python manage.py add SEU-CALL --passcode 12345 --node '!xxxxxxxx' --nome "Seu Nome"
```

Listar operadores cadastrados:

```bash
python manage.py list
```

Rodar o gateway:

```bash
python main.py
```

Ferramentas de diagnóstico:

```bash
python tools/detect_serial.py        # detecta a porta do nó Meshtastic
python tools/listen_packets.py       # escuta pacotes em tempo real
python tools/send_test_message.py "CALLSIGN corpo da mensagem"
```

## Testes

Cada módulo tem testes incrementais, organizados por etapa de desenvolvimento:

```bash
python tests/test_etapa1.py   # ambiente
python tests/test_etapa2.py --com-no    # interface Meshtastic
python tests/test_etapa3.py --online    # banco de dados e validação APRS-IS
python tests/test_etapa4.py --online --com-no   # posição → APRS-IS
python tests/test_etapa5.py --online --end-to-end SEU-CALL   # mensagens
```

## Aviso

Este é um projeto experimental, não afiliado à comunidade Meshtastic nem a nenhum projeto APRS oficial. O uso da bridge exige indicativo de radioamador válido na sua região. Verifique as regulamentações locais antes de operar.

## Créditos

Este projeto se integra ao ecossistema [LoRa APRS iGate](https://github.com/richonguzman/LoRa_APRS_iGate) e [LoRa APRS Tracker](https://github.com/richonguzman/LoRa_APRS_Tracker), de CA2RXU, usados nos testes de campo.

## Licença

A definir.
