from flask import Flask, request, jsonify, render_template, redirect, url_for
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def fetch_all(sql, params=None):
    db = get_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return rows

def fetch_one(sql, params=None):
    db = get_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    row = cursor.fetchone()
    cursor.close()
    db.close()
    return row

def execute(sql, params=None):
    db = get_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute(sql, params or ())
    db.commit()
    last_id = cursor.lastrowid
    cursor.close()
    db.close()
    return last_id

@app.route("/")
def dashboard():
    resumo = fetch_one("""
        SELECT
            COUNT(DISTINCT m.id_maquina) AS total_maquinas,
            COUNT(md.id) AS total_medicoes,
            COALESCE(ROUND(AVG(md.tensao), 2), 0) AS tensao_media,
            COALESCE(ROUND(AVG(md.corrente), 2), 0) AS corrente_media,
            COALESCE(ROUND(AVG(md.potencia), 2), 0) AS potencia_media,
            COALESCE(ROUND(SUM(md.energia), 2), 0) AS energia_total,
            COALESCE(ROUND(MAX(md.potencia), 2), 0) AS pico_potencia
        FROM maquinas m
        LEFT JOIN medicoes md ON m.id_maquina = md.id_maquina
    """)

    maquinas = fetch_all("""
        SELECT 
            m.id_maquina, m.nome, m.tipo, m.setor, m.potencia_nominal,
            COALESCE(ROUND(AVG(md.tensao), 2), 0) AS tensao_media,
            COALESCE(ROUND(AVG(md.corrente), 2), 0) AS corrente_media,
            COALESCE(ROUND(AVG(md.potencia), 2), 0) AS potencia_media,
            COALESCE(ROUND(SUM(md.energia), 2), 0) AS energia_total,
            COALESCE(ROUND(MAX(md.potencia), 2), 0) AS pico_potencia,
            COUNT(md.id) AS total_medicoes
        FROM maquinas m
        LEFT JOIN medicoes md ON m.id_maquina = md.id_maquina
        GROUP BY m.id_maquina, m.nome, m.tipo, m.setor, m.potencia_nominal
        ORDER BY m.nome
    """)

    ultimas = fetch_all("""
        SELECT id, nome_maquina, tensao, corrente, potencia, energia, timestamp
        FROM medicoes
        ORDER BY timestamp DESC
        LIMIT 8
    """)

    return render_template("dashboard.html", resumo=resumo, maquinas=maquinas, ultimas=ultimas)

@app.route("/maquinas")
def maquinas():
    lista = fetch_all("""
        SELECT 
            m.id_maquina, m.nome, m.tipo, m.setor, m.potencia_nominal,
            COUNT(md.id) AS total_medicoes,
            COALESCE(ROUND(SUM(md.energia), 2), 0) AS energia_total
        FROM maquinas m
        LEFT JOIN medicoes md ON m.id_maquina = md.id_maquina
        GROUP BY m.id_maquina, m.nome, m.tipo, m.setor, m.potencia_nominal
        ORDER BY m.id_maquina
    """)
    return render_template("maquinas.html", maquinas=lista)

@app.route("/nova_maquina", methods=["POST"])
def nova_maquina():
    nome = request.form.get("nome", "").strip()
    tipo = request.form.get("tipo", "").strip() or "Não informado"
    setor = request.form.get("setor", "").strip() or "Não informado"
    potencia = request.form.get("potencia", "").strip() or 0

    if nome:
        existente = fetch_one("SELECT id_maquina FROM maquinas WHERE nome = %s", (nome,))
        if not existente:
            execute("""
                INSERT INTO maquinas (nome, tipo, setor, potencia_nominal)
                VALUES (%s, %s, %s, %s)
            """, (nome, tipo, setor, potencia))

    return redirect(url_for("maquinas"))

@app.route("/excluir_maquina/<int:id_maquina>", methods=["POST"])
def excluir_maquina(id_maquina):
    execute("DELETE FROM indicadores WHERE id_maquina = %s", (id_maquina,))
    execute("DELETE FROM medicoes WHERE id_maquina = %s", (id_maquina,))
    execute("DELETE FROM maquinas WHERE id_maquina = %s", (id_maquina,))
    return redirect(url_for("maquinas"))

@app.route("/medicoes")
def medicoes():
    lista = fetch_all("""
        SELECT 
            md.id, md.id_maquina, COALESCE(m.nome, md.nome_maquina) AS nome_maquina,
            md.tensao, md.corrente, md.potencia, md.energia, md.timestamp
        FROM medicoes md
        LEFT JOIN maquinas m ON md.id_maquina = m.id_maquina
        ORDER BY md.timestamp DESC
        LIMIT 100
    """)
    maquinas = fetch_all("SELECT id_maquina, nome FROM maquinas ORDER BY nome")
    return render_template("medicoes.html", medicoes=lista, maquinas=maquinas)

@app.route("/nova_medicao", methods=["POST"])
def nova_medicao():
    id_maquina = request.form.get("id_maquina")
    tensao = request.form.get("tensao")
    corrente = request.form.get("corrente")
    potencia = request.form.get("potencia")
    energia = request.form.get("energia")

    maquina = fetch_one("SELECT nome FROM maquinas WHERE id_maquina = %s", (id_maquina,))
    if maquina:
        execute("""
            INSERT INTO medicoes (id_maquina, nome_maquina, tensao, corrente, potencia, energia)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (id_maquina, maquina["nome"], tensao, corrente, potencia, energia))

    return redirect(url_for("medicoes"))

@app.route("/excluir_medicao/<int:id_medicao>", methods=["POST"])
def excluir_medicao(id_medicao):
    execute("DELETE FROM medicoes WHERE id = %s", (id_medicao,))
    return redirect(url_for("medicoes"))

@app.route("/indicadores")
def indicadores():
    lista = fetch_all("""
        SELECT 
            m.id_maquina, m.nome, m.tipo, m.setor,
            COUNT(md.id) AS total_medicoes,
            COALESCE(ROUND(SUM(md.energia), 2), 0) AS consumo_total,
            COALESCE(ROUND(AVG(md.energia), 2), 0) AS consumo_medio,
            COALESCE(ROUND(MAX(md.potencia), 2), 0) AS pico_consumo,
            COALESCE(ROUND(AVG(md.potencia), 2), 0) AS potencia_media,
            COALESCE(ROUND(AVG(md.corrente), 2), 0) AS corrente_media
        FROM maquinas m
        LEFT JOIN medicoes md ON m.id_maquina = md.id_maquina
        GROUP BY m.id_maquina, m.nome, m.tipo, m.setor
        ORDER BY consumo_total DESC
    """)
    return render_template("indicadores.html", indicadores=lista)

@app.route("/dados", methods=["POST"])
def receber_dados():
    data = request.json or {}

    nome_maquina = data.get("maquina")
    tensao = data.get("tensao")
    corrente = data.get("corrente")
    potencia = data.get("potencia")
    energia = data.get("energia")

    if not nome_maquina:
        return jsonify({"status": "erro", "mensagem": "nome da maquina nao enviado"}), 400

    resultado = fetch_one("SELECT id_maquina FROM maquinas WHERE nome = %s", (nome_maquina,))

    if resultado:
        id_maquina = resultado["id_maquina"]
    else:
        id_maquina = execute("""
            INSERT INTO maquinas (nome, tipo, setor, potencia_nominal)
            VALUES (%s, %s, %s, %s)
        """, (nome_maquina, "Automática", "Não informado", 0))

    execute("""
        INSERT INTO medicoes 
        (id_maquina, nome_maquina, tensao, corrente, potencia, energia)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (id_maquina, nome_maquina, tensao, corrente, potencia, energia))

    return jsonify({"status": "ok", "maquina": nome_maquina})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
