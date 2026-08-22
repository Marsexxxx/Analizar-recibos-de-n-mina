// server.js
const express = require('express');
const multer = require('multer');
const fs = require('fs');
const pdf = require('pdf-extraction');

const app = express();
const upload = multer({ dest: 'uploads/' });

app.use(express.static('public'));

app.post('/analizar-masivo', upload.single('recibo'), async (req, res) => {
    try {
        if (!req.file) return res.status(400).send("No se recibió el archivo PDF.");

        const dataBuffer = fs.readFileSync(req.file.path);
        const data = await pdf(dataBuffer);
        const textoCompleto = data.text;

        // Dividimos el texto, pero esta vez NO vamos a saltarnos nada
        const fragmentos = textoCompleto.split("No.Trab.:");
        
        // El Mapa unirá todos los fragmentos dispersos del mismo empleado en un solo bloque
        const mapaEmpleados = new Map();
        let currentNoTrab = null;
        let currentNombre = null;

        for (let i = 1; i < fragmentos.length; i++) {
            const bloque = fragmentos[i];

            // Buscamos a quién pertenece este fragmento usando el RFC
            const empRegex = /\b([A-Z0-9]+)\s+([A-ZÑ\s]+?)\s+([A-Z]{4}\d{6}[A-Z0-9]{2,3})\b/;
            const empMatch = bloque.match(empRegex);

            if (empMatch) {
                currentNoTrab = empMatch[1];
                currentNombre = empMatch[2].trim();
            }

            // Si sabemos de quién es, FUSIONAMOS el texto en lugar de ignorarlo
            if (currentNoTrab) {
                if (!mapaEmpleados.has(currentNoTrab)) {
                    mapaEmpleados.set(currentNoTrab, { nombre: currentNombre, texto: bloque });
                } else {
                    mapaEmpleados.get(currentNoTrab).texto += " \n " + bloque; // ¡Aquí ocurre la magia!
                }
            }
        }

        const resultados = [];
        const formatearDinero = (num) => num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

        // Ahora leemos la información de los bloques ya fusionados y completos
        for (const [noTrab, datos] of mapaEmpleados.entries()) {
            const bloque = datos.texto;
            const nombre = datos.nombre;

            // EXTRACCIÓN MATEMÁTICA DE CONCEPTOS
            const regexConceptos = /\b(1\d{3}|2\d{3})\s+([^0-9\r\n]+?)\s+([\d,]+(?:\.\d{1,2})?)(?:\s+([\d,]+(?:\.\d{1,2})?))?\b/g;
            let match;
            
            let percepcionesDetalle = [];
            let deduccionesDetalle = [];
            let totalP = 0; 
            let totalD = 0; 
            let horasExtra = "0.00";

            while ((match = regexConceptos.exec(bloque)) !== null) {
                const codigo = parseInt(match[1]);
                const concepto = match[2].trim();
                
                const num1 = parseFloat(match[3].replace(/,/g, ''));
                const num2 = match[4] ? parseFloat(match[4].replace(/,/g, '')) : 0;

                // El dinero siempre es la cifra mayor
                const monto = Math.max(num1, num2);
                const montoFormateado = formatearDinero(monto);

                if (codigo >= 1000 && codigo < 2000) { 
                    percepcionesDetalle.push(`${concepto}: $${montoFormateado}`);
                    totalP += monto;
                    if (concepto.includes("HORAS EXTRA DOBLES")) {
                        horasExtra = montoFormateado;
                    }
                } else if (codigo >= 2000 && codigo < 3000) { 
                    deduccionesDetalle.push(`${concepto}: $${montoFormateado}`);
                    totalD += monto;
                }
            }

            const netoFinal = totalP - totalD;

            resultados.push({ 
                noTrab, 
                nombre, 
                percepciones: formatearDinero(totalP), 
                deducciones: formatearDinero(totalD), 
                horasExtra, 
                neto: formatearDinero(netoFinal),
                detalleP: percepcionesDetalle.length > 0 ? percepcionesDetalle.join(" | ") : "Sin detalles extraídos", 
                detalleD: deduccionesDetalle.length > 0 ? deduccionesDetalle.join(" | ") : "Sin detalles extraídos"
            });
        }
        
        fs.unlinkSync(req.file.path);
        res.json(resultados);

    } catch (error) {
        console.error("Error detallado:", error);
        if (req.file && fs.existsSync(req.file.path)) fs.unlinkSync(req.file.path);
        res.status(500).send("Hubo un error al procesar el PDF.");
    }
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`¡Servidor de Fusión de Textos listo en el puerto ${PORT}!`);
});