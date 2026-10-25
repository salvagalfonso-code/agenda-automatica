import os, json, time
from datetime import datetime
import pytz
import gspread
from google.oauth2.service_account import Credentials
from duckduckgo_search import DDGS
from google import genai
from google.genai import types

MADRID_TZ = pytz.timezone("Europe/Madrid")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(creds)

sh_agenda = gc.open_by_key("1Ne30TTLbK5qePu_l6EutLGsZjxqgedBHHe7eib0tiXg")
sh_entitats = gc.open_by_key("1o9vR0_aYNT9GpMXn8HvYKNjksBGAzjDsE6HsajIs7JU")
sh_cataleg = gc.open_by_key("12Y3TnEtn1gkd6Q_44qlBCpJC5TF6zTr55WB8zaeDmow")

ws_control = sh_agenda.worksheet("CONTROL_ALIMENTADOR")
ws_events = sh_agenda.worksheet("ESDEVENIMENTS")
ws_report = sh_agenda.worksheet("Report")
ws_entitats = sh_entitats.worksheet("Entitats")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def obtenir_cursor():
    valors = ws_control.get_all_values()
    for fila_idx, fila in enumerate(valors, start=1):
        for col_idx, cella in enumerate(fila):
            if str(cella).strip() == "NEXT_ENTITY_ROW":
                if col_idx + 1 < len(fila) and str(fila[col_idx + 1]).strip().isdigit():
                    return int(fila[col_idx + 1]), fila_idx, col_idx + 2
                if fila_idx < len(valors) and str(valors[fila_idx][col_idx]).strip().isdigit():
                    return int(valors[fila_idx][col_idx]), fila_idx + 1, col_idx + 1
    return 2, 2, 2

def buscar_internet_gratis(nom_artista):
    resultats = []
    queries = [
        f'"{nom_artista}" concerts 2026 OR 2027 entrades',
        f'"{nom_artista}" agenda actuacions gira Catalunya OR Valencià OR Balears'
    ]
    with DDGS() as ddgs:
        for q in queries:
            try:
                for r in ddgs.text(q, max_results=6):
                    resultats.append(f"Títol: {r['title']} | URL: {r['href']} | Text: {r['body']}")
            except Exception:
                pass
    return "\n".join(resultats)

def analitzar_artista(nom, text_cerca, avui):
    prompt = f"""
    Data d'avui: {avui}. Artista: {nom}
    Resultats de cerca a internet:
    {text_cerca}

    Extreu ÚNICAMENT concerts futurs verificables (>= {avui}) dins dels Països Catalans (PV, CAT, IB, AD, CN, FR, CX, AL).
    Retorna un JSON amb aquesta estructura:
    {{
      "estat": "REVISAT_SENSE_NOVETATS" o "AMB_ACTUACIONS",
      "concerts": [
        {{
          "titol": "...",
          "data": "YYYY-MM-DD",
          "hora": "HH:MM o buit",
          "municipi": "...",
          "territori": "PV/CAT/IB/AD/CN/FR/CX/AL",
          "recinte": "...",
          "preu": "import o PENDENT",
          "url_entrades": "url directa o PENDENT",
          "url_cartell": "url o PENDENT",
          "url_font": "url on s'ha trobat"
        }}
      ]
    }}
    """
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    return json.loads(resp.text)

def executar_passada():
    ara = datetime.now(MADRID_TZ)
    avui_str = ara.strftime("%Y-%m-%d")
    cursor_actual, c_row, c_col = obtenir_cursor()
    
    totes_files_entitats = ws_entitats.get_all_values()
    esdeveniments_existents = ws_events.get_all_values()

    seleccionats = 0
    fila = max(2, cursor_actual)
    nous_afegits = 0

    while seleccionats < 20 and (fila - 1) < len(totes_files_entitats):
        dades_fila = totes_files_entitats[fila - 1]
        fila_text = " ".join(dades_fila).upper()

        if any(t in fila_text for t in ["VENUE", "TOWN", "ORGANIZER"]) or not any(dades_fila):
            fila += 1
            continue

        nom = dades_fila[1] if len(dades_fila) > 1 and dades_fila[1].strip() else dades_fila[0]
        print(f"Investigant ({seleccionats+1}/20): {nom} (Fila {fila})")

        info_web = buscar_internet_gratis(nom)
        if info_web.strip():
            try:
                resultat = analitzar_artista(nom, info_web, avui_str)
                for c in resultat.get("concerts", []):
                    ja_existeix = any(
                        nom.lower() in " ".join(ev).lower() and c.get("data", "") in " ".join(ev)
                        for ev in esdeveniments_existents
                    )
                    if not ja_existeix and c.get("data"):
                        ws_events.append_row([
                            f"EVT-{int(time.time())}", c.get("titol", ""), nom, c.get("data", ""),
                            c.get("hora", ""), c.get("municipi", ""), c.get("territori", ""), c.get("recinte", ""),
                            c.get("preu", "PENDENT"), c.get("url_entrades", "PENDENT"),
                            c.get("url_cartell", "PENDENT"), c.get("url_font", ""), "PENDING_AUDIT"
                        ], value_input_option="USER_ENTERED")
                        nous_afegits += 1
                        time.sleep(1)
            except Exception as e:
                print(f"Error en {nom}: {e}")

        seleccionats += 1
        fila += 1
        time.sleep(5)

    ws_control.update_cell(c_row, c_col, str(fila))
    ws_report.append_row([
        ara.strftime("%Y-%m-%d %H:%M:%S"),
        "TASCA_00",
        "COMPLETE" if seleccionats == 20 else "PARTIAL",
        str(cursor_actual),
        str(fila),
        str(seleccionats),
        str(nous_afegits)
    ], value_input_option="USER_ENTERED")
    print("Passada completada!")

if __name__ == "__main__":
    executar_passada()
