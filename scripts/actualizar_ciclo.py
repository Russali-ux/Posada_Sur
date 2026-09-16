#!/usr/bin/env python3
"""
Recalcula la etapa, peso estimado y fecha de rastro de cada lote guardado en
Supabase, y registra un evento en `cerdo_lotes_eventos` cuando un lote cruza
a una nueva etapa desde la última corrida.

Variables de entorno requeridas:
  SUPABASE_URL                 -> https://<ref>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    -> clave service_role (NUNCA la anon/publishable)

Se ejecuta diariamente vía .github/workflows/actualizar-ciclo.yml
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_KEY:
    print("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en el entorno.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Debe coincidir con DEFAULT_STAGES en index.html (mismo orden y significado).
DEFAULT_STAGES = [
    {"id": "lactancia", "name": "Lactancia", "duration": 21, "end_weight": 5.5, "feed": None, "start_weight": 1.4},
    {"id": "preiniciador", "name": "Preiniciador", "duration": 28, "end_weight": 15, "feed": 12},
    {"id": "iniciador", "name": "Iniciador", "duration": 21, "end_weight": 30, "feed": 22},
    {"id": "crecimiento", "name": "Crecimiento", "duration": 28, "end_weight": 50, "feed": 49},
    {"id": "desarrollo", "name": "Desarrollo", "duration": 28, "end_weight": 75, "feed": 65},
    {"id": "finalizacion", "name": "Finalización", "duration": 28, "end_weight": 100, "feed": 84},
]


def with_cumulative_days(stages):
    acc = 0
    out = []
    for i, s in enumerate(stages):
        start_day = acc
        acc += int(s["duration"])
        start_weight = s.get("start_weight") if i == 0 else stages[i - 1]["end_weight"]
        out.append({**s, "start_day": start_day, "end_day": acc, "start_weight": start_weight})
    return out


def compute_status(birth_date_str, stage_settings):
    stages = with_cumulative_days(stage_settings or DEFAULT_STAGES)
    birth = date.fromisoformat(birth_date_str)
    today = date.today()
    age_days = (today - birth).days

    total_days = stages[-1]["end_day"]
    active = stages[-1]
    for s in stages:
        if age_days < s["end_day"]:
            active = s
            break

    span = active["end_day"] - active["start_day"]
    into = min(max(age_days - active["start_day"], 0), span)
    frac = (into / span) if span else 1
    est_weight = active["start_weight"] + (active["end_weight"] - active["start_weight"]) * frac

    slaughter_date = birth + timedelta(days=total_days)
    days_to_slaughter = (slaughter_date - today).days

    return {
        "current_stage_id": active["id"],
        "current_stage_name": active["name"],
        "age_days": age_days,
        "estimated_weight": round(est_weight, 2),
        "slaughter_date": slaughter_date.isoformat(),
        "days_to_slaughter": days_to_slaughter,
    }


def fetch_lotes():
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/cerdo_lotes?select=*", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def log_event(lote_id, previous_stage, new_stage):
    payload = {
        "lote_id": lote_id,
        "previous_stage": previous_stage,
        "new_stage": new_stage,
        "occurred_on": date.today().isoformat(),
    }
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/cerdo_lotes_eventos",
        headers={**HEADERS, "Prefer": "return=minimal"},
        data=json.dumps(payload),
        timeout=30,
    )
    resp.raise_for_status()


def update_lote(lote_id, status):
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/cerdo_lotes?id=eq.{lote_id}",
        headers={**HEADERS, "Prefer": "return=minimal"},
        data=json.dumps(status),
        timeout=30,
    )
    resp.raise_for_status()


def main():
    lotes = fetch_lotes()
    if not lotes:
        print("No hay lotes registrados todavía.")
        return

    updated, stage_changes = 0, 0
    for lote in lotes:
        status = compute_status(lote["birth_date"], lote.get("stage_settings"))
        status["last_calculated_at"] = datetime.now(timezone.utc).isoformat()

        previous_stage = lote.get("current_stage_id")
        if previous_stage and previous_stage != status["current_stage_id"]:
            log_event(lote["id"], previous_stage, status["current_stage_id"])
            stage_changes += 1
            print(f"  → {lote['name']}: {previous_stage} → {status['current_stage_id']}")

        update_lote(lote["id"], status)
        updated += 1

    print(f"Lotes actualizados: {updated}. Cambios de etapa detectados hoy: {stage_changes}.")
    if stage_changes:
        # Código de salida distinto solo informativo; no falla el workflow.
        # Un paso posterior (correo/Slack) puede filtrar por este texto o
        # consultar directamente `cerdo_lotes_eventos where notified = false`.
        print("Hay eventos pendientes de notificar en cerdo_lotes_eventos.")


if __name__ == "__main__":
    main()
