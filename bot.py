import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(creds)

sh_agenda = gc.open_by_key("1Ne30TTLbK5qePu_l6EutLGsZjxqgedBHHe7eib0tiXg")
sh_entitats = gc.open_by_key("1o9vR0_aYNT9GpMXn8HvYKNjksBGAzjDsE6HsajIs7JU")
sh_cataleg = gc.open_by_key("12Y3TnEtn1gkd6Q_44qlBCpJC5TF6zTr55WB8zaeDmow")

def inspeccionar(nom_llibre, sh):
    print(f"\n================ {nom_llibre} ================")
    for ws in sh.worksheets():
        files = ws.get_all_values()
        capcalera = files[0] if len(files) > 0 else []
        mostra = files[1] if len(files) > 1 else []
        print(f"\n--- Pestanya: {ws.title} ---")
        print(f"FILA 1 (Columnes): {capcalera}")
        if ws.title in ["CONTROL_ALIMENTADOR", "CONTROL"]:
            print(f"CONTINGUT COMPLET: {files[:15]}")
        else:
            print(f"FILA 2 (Exemple): {mostra[:10]}")

inspeccionar("AGENDA", sh_agenda)
inspeccionar("ENTITATS", sh_entitats)
inspeccionar("CATALEG", sh_cataleg)
