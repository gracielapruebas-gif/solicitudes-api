import base64
import json
import os

import httpx
from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="Solicitudes API", version="1.0.0")

# Claim del token que identifica al usuario (se ajusta con /whoami).
OWNER_CLAIM = "azp"
OWNER_A = "oAZgRJD8dYeXUfnX_HK6Xc2ho0wa"
OWNER_B = "JlwKwGWv92yP9aHK6h1Vbfka7hga"

SOLICITUDES = {
    "SOL-1001": {"owner": OWNER_A, "estado": "En revisión", "fecha_estimada": "2026-12-10", "responsable_id": 1},
    "SOL-1002": {"owner": OWNER_A, "estado": "Aprobada", "fecha_estimada": "2026-12-02", "responsable_id": 2},
    "SOL-1003": {"owner": OWNER_A, "estado": "Pendiente de documentos", "fecha_estimada": "2026-12-18", "responsable_id": 3},
    "SOL-2001": {"owner": OWNER_B, "estado": "Auditoría interna confidencial", "fecha_estimada": "2026-12-20", "responsable_id": 4},
}

# Solo se usa si la fuente externa falla.
RESPALDO = {1: "Leanne Graham", 2: "Ervin Howell", 3: "Clementine Bauch", 4: "Patricia Lebsack"}


def leer_claims(authorization, jwt_assertion):
    crudo = jwt_assertion
    if not crudo and authorization and authorization.lower().startswith("bearer "):
        crudo = authorization.split(" ", 1)[1]
    if not crudo:
        raise HTTPException(status_code=401, detail="Falta el token")
    try:
        parte = crudo.split(".")[1]
        parte += "=" * (-len(parte) % 4)
        return json.loads(base64.urlsafe_b64decode(parte))
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")


async def buscar_responsable(uid):
    base = os.getenv("ENRICH_URL")
    url = f"{base}/area/{uid}" if base else f"https://jsonplaceholder.typicode.com/users/{uid}"
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(url)
            r.raise_for_status()
            datos = r.json()
            nombre = datos.get("responsable") or datos.get("name")
            if nombre:
                return nombre, "externa"
    except Exception:
        pass
    return RESPALDO.get(uid, "No disponible"), "respaldo"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/whoami")
def whoami(authorization: str | None = Header(default=None),
           x_jwt_assertion: str | None = Header(default=None)):
    claims = leer_claims(authorization, x_jwt_assertion)
    return {"claims": claims}


@app.get("/solicitudes/{solicitud_id}")
async def consultar(solicitud_id: str,
                    authorization: str | None = Header(default=None),
                    x_jwt_assertion: str | None = Header(default=None)):
    claims = leer_claims(authorization, x_jwt_assertion)
    quien = claims.get(OWNER_CLAIM)
    s = SOLICITUDES.get(solicitud_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    if s["owner"] != quien:
        raise HTTPException(status_code=403, detail="No autorizado para esta solicitud")
    responsable, fuente = await buscar_responsable(s["responsable_id"])
    return {
        "id": solicitud_id,
        "estado": s["estado"],
        "fecha_estimada": s["fecha_estimada"],
        "responsable": responsable,
        "fuente_responsable": fuente,
    }