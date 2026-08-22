import os
import re
import fitz
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

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

                    if abs(y_centro - y_actual) <= 5:
                        linea_actual.append(w[4])
                    else:
                        lineas_visuales.append(" ".join(linea_actual))
                        linea_actual = [w[4]]
                        y_actual = y_centro

                if linea_actual:
                    lineas_visuales.append(" ".join(linea_actual))

                texto_pagina = "\n".join(lineas_visuales)

                no_trab_match = re.search(r'No\.Trab\.:\s*([A-Z0-9]+)', texto_pagina)
                nombre_match = re.search(r'Nombre:\s*(.+?)(?=\s+Dias|\s+N\.S\.S|$)', texto_pagina)
                
                depto_match = re.search(r'Depto\.:\s*(.+?)(?=\s+Periodo|\n|$)', texto_pagina, re.IGNORECASE)
                puesto_match = re.search(r'Puesto:\s*(.+?)(?=\s+Fecha|\s+Periodo|\n|$)', texto_pagina, re.IGNORECASE)
                faltas_match = re.search(r'Faltas:\s*(\d+)', texto_pagina, re.IGNORECASE)

                if not no_trab_match:
                    continue

                no_trab = no_trab_match.group(1)
                nombre = nombre_match.group(1).strip() if nombre_match else "Desconocido"
                depto = depto_match.group(1).strip() if depto_match else "Sin Depto"
                puesto = puesto_match.group(1).strip() if puesto_match else "Sin Puesto"
                faltas = faltas_match.group(1).strip() if faltas_match else "0"

                neto_match = re.search(r'Neto Pagado\s+([\d,]+\.\d{2})', texto_pagina, re.IGNORECASE)
                neto_final = neto_match.group(1) if neto_match else "0.00"

                dobles_match = re.search(r'HORAS EXTRA(?:S)? DOBLES\s+([\d,]+(?:\.\d{1,2})?)', texto_pagina, re.IGNORECASE)
                horas_dobles = "0"
                if dobles_match:
                    cantidad = float(dobles_match.group(1).replace(',', ''))
                    horas_dobles = f"{cantidad:g}"

                triples_match = re.search(r'HORAS EXTRA(?:S)? TRIPLES\s+([\d,]+(?:\.\d{1,2})?)', texto_pagina, re.IGNORECASE)
                horas_triples = "0"
                if triples_match:
                    cantidad = float(triples_match.group(1).replace(',', ''))
                    horas_triples = f"{cantidad:g}"

                resultados.append({
                    "noTrab": no_trab,
                    "nombre": nombre,
                    "depto": depto,
                    "puesto": puesto,
                    "faltas": faltas,
                    "horasDobles": horas_dobles,
                    "horasTriples": horas_triples,
                    "neto": neto_final
                })

    except Exception as e:
        return "Error procesando el PDF", 500
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return jsonify(resultados)

if __name__ == '__main__':
    app.run(port=3000, debug=False)