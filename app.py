import os
import re
import fitz
from flask import Flask, request, jsonify

app = Flask(__name__, static_folder='public', static_url_path='')

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/analizar-masivo', methods=['POST'])
def analizar_masivo():
    if 'recibo' not in request.files:
        return "No se recibio archivo", 400

    file = request.files['recibo']
    os.makedirs('uploads', exist_ok=True)
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    resultados = []
    catalogo_percepciones = {}

    try:
        with fitz.open(file_path) as pdf:
            for page in pdf:
                words = page.get_text("words")
                if not words:
                    continue

                words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
                lineas_visuales = []
                linea_actual = []
                y_actual = None

                for w in words:
                    y_centro = (w[1] + w[3]) / 2
                    if y_actual is None:
                        y_actual = y_centro

                    if abs(y_centro - y_actual) <= 3.5:
                        linea_actual.append((w[0], w[4]))
                    else:
                        linea_actual.sort(key=lambda item: item[0])
                        lineas_visuales.append(" ".join(item[1] for item in linea_actual))
                        linea_actual = [(w[0], w[4])]
                        y_actual = y_centro

                if linea_actual:
                    linea_actual.sort(key=lambda item: item[0])
                    lineas_visuales.append(" ".join(item[1] for item in linea_actual))

                texto_pagina = "\n".join(lineas_visuales)

                bloques_pagina = re.split(r'No\.\s*Trab\.:', texto_pagina, flags=re.IGNORECASE)
                if len(bloques_pagina) < 2:
                    continue

                texto_original = "No.Trab.:" + bloques_pagina[1]

                no_trab_match = re.search(r'No\.Trab\.:\s*([A-Z0-9]+)', texto_original, re.IGNORECASE)
                if not no_trab_match:
                    continue
                no_trab = no_trab_match.group(1).strip()

                nombre_match = re.search(r'Nombre:\s*(.+?)(?=\s+D[ií]as|\s+N\.S\.S|\s+R\.F\.C|$)', texto_original, re.IGNORECASE | re.MULTILINE)
                nombre = nombre_match.group(1).strip() if nombre_match else "Desconocido"

                depto_match = re.search(r'Depto\.:\s*(.+?)(?=\s+Per[ií]odo|\s+Fecha|\s+Faltas|\s+Puesto|$)', texto_original, re.IGNORECASE | re.MULTILINE)
                depto = depto_match.group(1).strip() if depto_match else "General"

                puesto_match = re.search(r'Puesto:\s*(.+?)(?=\s+Fecha\s*Pa[gq]o|\s+Per[ií]odo|\s+C\.U\.R\.P|$)', texto_original, re.IGNORECASE | re.MULTILINE)
                puesto = puesto_match.group(1).strip() if puesto_match else "Sin Puesto"

                dias_match = re.search(r'D[ií]as\s+Trabajados:\s*(\d+(?:\.\d+)?)', texto_original, re.IGNORECASE)
                dias_trab = f"{float(dias_match.group(1)):g}" if dias_match else "0"

                faltas_match = re.search(r'Faltas:\s*(\d+(?:\.\d+)?)', texto_original, re.IGNORECASE)
                faltas = f"{float(faltas_match.group(1)):g}" if faltas_match else "0"

                periodo_match = re.search(r'Per[ií]odo:?\s+(\d+)', texto_original, re.IGNORECASE)
                periodo = periodo_match.group(1).strip() if periodo_match else "-"

                fecha_pago_match = re.search(r'Fecha\s*Pa[gq]o:\s*(\d{2}/\d{2}/\d{4})', texto_original, re.IGNORECASE)
                fecha_pago = fecha_pago_match.group(1).strip() if fecha_pago_match else "-"

                del_match = re.search(r'Per[ií]odo\s+Del:\s*(\d{2}/\d{2}/\d{4})', texto_original, re.IGNORECASE)
                al_match = re.search(r'\bAl:\s*(\d{2}/\d{2}/\d{4})', texto_original, re.IGNORECASE)
                rango_periodo = f"{del_match.group(1)} al {al_match.group(1)}" if (del_match and al_match) else "-"

                bruto_match = re.search(r'Total\s+Percepciones\s+([\d,]+\.\d{2})', texto_original, re.IGNORECASE)
                bruto_final = bruto_match.group(1) if bruto_match else "0.00"

                ded_match = re.search(r'Total\s+Deducciones\s+([\d,]+\.\d{2})', texto_original, re.IGNORECASE)
                ded_final = ded_match.group(1) if ded_match else "0.00"

                neto_match = re.search(r'Neto\s+Pagado\s+([\d,]+\.\d{2})', texto_original, re.IGNORECASE)
                neto_final = neto_match.group(1) if neto_match else "0.00"

                percepciones_emp = {}
                horas_dobles = "0"
                horas_triples = "0"
                monto_dobles = "0.00"
                monto_triples = "0.00"

                for linea in texto_original.split("\n"):
                    linea_limpia = linea.strip()
                    parte_izq = re.split(r'\b2\d{3}\s+[A-ZÑÁÉÍÓÚÜ]', linea_limpia)[0].strip()

                    match_perc = re.match(
                        r'^(1\d{3})\s+(.+?)\s+(?:([\d,]+(?:\.\d{1,2})?)\s+)?([\d,]+\.\d{2})$',
                        parte_izq,
                        re.IGNORECASE
                    )
                    if match_perc:
                        codigo = match_perc.group(1)
                        concepto = re.sub(r'\s+', ' ', match_perc.group(2)).strip().upper()
                        cantidad_str = match_perc.group(3)
                        monto_str = match_perc.group(4)

                        monto_val = float(monto_str.replace(',', ''))
                        etiqueta = f"{codigo} {concepto}"
                        catalogo_percepciones[codigo] = etiqueta
                        percepciones_emp[etiqueta] = f"{monto_val:,.2f}"

                        if "HORAS EXTRA" in concepto and "DOBLE" in concepto:
                            monto_dobles = f"{monto_val:,.2f}"
                            if cantidad_str:
                                cant_val = float(cantidad_str.replace(',', ''))
                                horas_dobles = f"{cant_val:g}"
                        elif "HORAS EXTRA" in concepto and "TRIPLE" in concepto:
                            monto_triples = f"{monto_val:,.2f}"
                            if cantidad_str:
                                cant_val = float(cantidad_str.replace(',', ''))
                                horas_triples = f"{cant_val:g}"

                if horas_dobles == "0":
                    dobles_match = re.search(r'HORAS EXTRA(?:S)? DOBLES\s+([\d,]+(?:\.\d{1,2})?)\s+([\d,]+\.\d{2})', texto_original, re.IGNORECASE)
                    if dobles_match:
                        cantidad = float(dobles_match.group(1).replace(',', ''))
                        monto_d = float(dobles_match.group(2).replace(',', ''))
                        horas_dobles = f"{cantidad:g}"
                        monto_dobles = f"{monto_d:,.2f}"

                if horas_triples == "0":
                    triples_match = re.search(r'HORAS EXTRA(?:S)? TRIPLES\s+([\d,]+(?:\.\d{1,2})?)\s+([\d,]+\.\d{2})', texto_original, re.IGNORECASE)
                    if triples_match:
                        cantidad = float(triples_match.group(1).replace(',', ''))
                        monto_t = float(triples_match.group(2).replace(',', ''))
                        horas_triples = f"{cantidad:g}"
                        monto_triples = f"{monto_t:,.2f}"

                resultados.append({
                    "noTrab": no_trab,
                    "nombre": nombre,
                    "depto": depto,
                    "puesto": puesto,
                    "diasTrab": dias_trab,
                    "faltas": faltas,
                    "periodo": periodo,
                    "fechaPago": fecha_pago,
                    "rangoPeriodo": rango_periodo,
                    "horasDobles": horas_dobles,
                    "montoDobles": monto_dobles,
                    "horasTriples": horas_triples,
                    "montoTriples": monto_triples,
                    "bruto": bruto_final,
                    "deducciones": ded_final,
                    "neto": neto_final,
                    "percepciones": percepciones_emp
                })

        codigos_ordenados = sorted(catalogo_percepciones.keys())
        columnas_percepciones = [catalogo_percepciones[c] for c in codigos_ordenados]

        for emp in resultados:
            mapa_completo = {}
            for col in columnas_percepciones:
                mapa_completo[col] = emp["percepciones"].get(col, "0.00")
            emp["percepciones"] = mapa_completo
            emp["columnasPercepciones"] = columnas_percepciones

    except Exception as e:
        return "Error procesando el PDF", 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return jsonify(resultados)

if __name__ == '__main__':
    app.run(port=3000, debug=True)