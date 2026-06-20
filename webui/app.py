"""FastAPI Web UI para o Mesh↔APRS Gateway."""
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Adiciona o diretório pai ao path para importar módulos
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from modules.config_loader import load as load_config
    from modules.database import Database
    from modules.logger import get_logger
    
    # Carrega configuração
    cfg = load_config()
    log = get_logger("webui", cfg)
    db = Database(cfg)
except Exception as e:
    print(f"ERRO: Falha ao inicializar aplicação: {e}")
    print("Verifique se o arquivo config/config.json existe e está válido")
    sys.exit(1)

app = FastAPI(
    title="Mesh↔APRS Gateway",
    description="Interface web para gerenciar o gateway Meshtastic ↔ APRS",
    version="0.1.0"
)

# Templates e arquivos estáticos - paths relativos ao diretório do projeto
webui_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(webui_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(webui_dir / "static")), name="static")

# Modelos Pydantic
class OperatorCreate(BaseModel):
    callsign: str
    ssid: str
    passcode: int
    node_id: str = None
    long_name: str = ""
    short_name: str = ""
    aprs_icon: str = "/>"
    aprs_comment: str = "via Mesh/APRS-GW"
    channel_index: int = 1
    pub_position: bool = True
    rx_aprs: bool = True
    tx_aprs: bool = True
    rf_local: bool = False

class OperatorUpdate(BaseModel):
    node_id: str = None
    long_name: str = None
    short_name: str = None
    aprs_icon: str = None
    aprs_comment: str = None
    pub_position: bool = None
    rx_aprs: bool = None
    tx_aprs: bool = None
    rf_local: bool = None
    active: bool = None

# Rotas da interface web
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard principal."""
    try:
        operators = db.list_operators()
        messages = db.list_messages(limit=20)
        
        # Convert to plain dicts to avoid Jinja2 caching issues
        operators = [dict(op) for op in operators] if operators else []
        messages = [dict(msg) for msg in messages] if messages else []
        
        stats = {
            "total_operators": len(operators),
            "active_operators": len([op for op in operators if op.get("active", True)]),
            "total_messages": len(messages),
            "pending_messages": len([msg for msg in messages if msg.get("status") == "pending"]),
        }
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": stats,
            "operators": operators[:10],  # Últimos 10
            "messages": messages[:10],    # Últimas 10
            "config": cfg
        })
    except Exception as e:
        log.error(f"Erro no dashboard: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": {"total_operators": 0, "active_operators": 0, "total_messages": 0, "pending_messages": 0},
            "operators": [],
            "messages": [],
            "config": cfg
        })

@app.get("/operators", response_class=HTMLResponse)
async def operators_page(request: Request):
    """Página de gerenciamento de operadores."""
    try:
        operators = db.list_operators(active_only=False)
        # Convert to plain dicts to avoid Jinja2 caching issues
        operators = [dict(op) for op in operators] if operators else []
        return templates.TemplateResponse("operators.html", {
            "request": request,
            "operators": operators
        })
    except Exception as e:
        log.error(f"Erro na página de operadores: {e}")
        return templates.TemplateResponse("operators.html", {
            "request": request,
            "operators": []
        })

@app.get("/messages", response_class=HTMLResponse)
async def messages_page(request: Request):
    """Página de mensagens."""
    try:
        messages = db.list_messages(limit=100)
        # Convert to plain dicts to avoid Jinja2 caching issues
        messages = [dict(msg) for msg in messages] if messages else []
        return templates.TemplateResponse("messages.html", {
            "request": request,
            "messages": messages
        })
    except Exception as e:
        log.error(f"Erro na página de mensagens: {e}")
        return templates.TemplateResponse("messages.html", {
            "request": request,
            "messages": []
        })

@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Página de configuração."""
    return templates.TemplateResponse("config.html", {
        "request": request,
        "config": cfg
    })

# API REST
@app.get("/api/operators")
async def get_operators() -> List[Dict[str, Any]]:
    """Lista todos os operadores."""
    try:
        operators = db.list_operators(active_only=False)
        return [dict(op) for op in operators]
    except Exception as e:
        log.error(f"Erro ao listar operadores via API: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@app.post("/api/operators")
async def create_operator(operator: OperatorCreate) -> Dict[str, Any]:
    """Cria um novo operador."""
    success = db.add_operator(
        callsign=operator.callsign,
        ssid=operator.ssid,
        passcode=operator.passcode,
        node_id=operator.node_id,
        long_name=operator.long_name,
        short_name=operator.short_name,
        aprs_icon=operator.aprs_icon,
        aprs_comment=operator.aprs_comment,
        channel_index=operator.channel_index,
        pub_position=operator.pub_position,
        rx_aprs=operator.rx_aprs,
        tx_aprs=operator.tx_aprs,
        rf_local=operator.rf_local
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Erro ao criar operador")
    
    return {"message": "Operador criado com sucesso"}

@app.put("/api/operators/{callsign}")
async def update_operator(callsign: str, operator: OperatorUpdate) -> Dict[str, Any]:
    """Atualiza um operador."""
    # Remove campos None
    updates = {k: v for k, v in operator.dict().items() if v is not None}
    
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    
    success = db.update_operator(callsign, **updates)
    
    if not success:
        raise HTTPException(status_code=404, detail="Operador não encontrado")
    
    return {"message": "Operador atualizado com sucesso"}

@app.delete("/api/operators/{callsign}")
async def delete_operator(callsign: str) -> Dict[str, Any]:
    """Remove (desativa) um operador."""
    success = db.remove_operator(callsign)
    
    if not success:
        raise HTTPException(status_code=404, detail="Operador não encontrado")
    
    return {"message": "Operador removido com sucesso"}

@app.get("/api/messages")
async def get_messages(limit: int = 100) -> List[Dict[str, Any]]:
    """Lista mensagens."""
    try:
        messages = db.list_messages(limit=limit)
        return [dict(msg) for msg in messages]
    except Exception as e:
        log.error(f"Erro ao listar mensagens via API: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")

@app.get("/api/stats")
async def get_stats() -> Dict[str, Any]:
    """Estatísticas do gateway."""
    try:
        operators = db.list_operators(active_only=False)
        messages = db.list_messages(limit=1000)
        
        # Convert to plain dicts to avoid issues
        operators = [dict(op) for op in operators] if operators else []
        messages = [dict(msg) for msg in messages] if messages else []
        
        return {
            "operators": {
                "total": len(operators),
                "active": len([op for op in operators if op.get("active", True)]),
                "inactive": len([op for op in operators if not op.get("active", True)])
            },
            "messages": {
                "total": len(messages),
                "pending": len([msg for msg in messages if msg.get("status") == "pending"]),
                "delivered": len([msg for msg in messages if msg.get("status") == "delivered"]),
                "failed": len([msg for msg in messages if msg.get("status") == "failed"])
            }
        }
    except Exception as e:
        log.error(f"Erro ao obter estatísticas: {e}")
        return {
            "operators": {"total": 0, "active": 0, "inactive": 0},
            "messages": {"total": 0, "pending": 0, "delivered": 0, "failed": 0}
        }

if __name__ == "__main__":
    import uvicorn
    
    host = cfg.get("webui", {}).get("host", "0.0.0.0")
    port = cfg.get("webui", {}).get("port", 8080)
    
    log.info(f"Iniciando Web UI em http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
