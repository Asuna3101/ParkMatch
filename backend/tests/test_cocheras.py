"""Publicación, búsqueda y detalle (US-05, US-06, US-07, US-09, US-12, US-18)."""
from tests.conftest import DATOS_COCHERA, proximo, publicar, registrar


def test_publicar_crea_el_anuncio_completo(cliente):
    cabeceras, usuario = registrar(cliente, "arrendador")
    r = publicar(cliente, cabeceras)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["titulo"] == DATOS_COCHERA["titulo"]
    assert c["arrendador_id"] == usuario["id"]
    assert len(c["fotos"]) == 3
    assert len(c["disponibilidad"]) == 5
    assert c["tarifas"][0]["precio_hora"] == 9.0
    assert c["ubicacion"]["distrito"] == "Miraflores"
    # la foto queda accesible
    assert cliente.get(c["fotos"][0]).status_code == 200


def test_exige_minimo_tres_fotos(cliente):
    cabeceras, _ = registrar(cliente, "arrendador")
    r = publicar(cliente, cabeceras, fotos=2)
    assert r.status_code == 422
    assert "al menos 3" in r.json()["detail"]


def test_solo_un_arrendador_puede_publicar(cliente):
    cabeceras, _ = registrar(cliente, "arrendatario")
    assert publicar(cliente, cabeceras).status_code == 403
    assert publicar(cliente, {}).status_code == 401


def test_rechaza_archivos_que_no_son_imagen(cliente):
    import json
    cabeceras, _ = registrar(cliente, "arrendador")
    archivos = [("fotos", (f"doc{i}.pdf", b"%PDF-1.4", "application/pdf")) for i in range(3)]
    r = cliente.post("/api/cocheras", data={"datos": json.dumps(DATOS_COCHERA)}, files=archivos, headers=cabeceras)
    assert r.status_code == 422


def test_rechaza_calendario_con_franjas_cruzadas(cliente):
    cabeceras, _ = registrar(cliente, "arrendador")
    cruzado = [{"dia_semana": 0, "hora_inicio": "08:00", "hora_fin": "12:00"},
               {"dia_semana": 0, "hora_inicio": "11:00", "hora_fin": "15:00"}]
    r = publicar(cliente, cabeceras, disponibilidad=cruzado)
    assert r.status_code == 422
    assert "se cruzan" in r.json()["detail"]


def test_busqueda_ordena_por_cercania_y_respeta_el_radio(cliente):
    cabeceras, _ = registrar(cliente, "arrendador")
    cerca = publicar(cliente, cabeceras, titulo="Cochera cerca del parque").json()
    medio = publicar(cliente, cabeceras, titulo="Cochera a un kilómetro",
                     latitud=-12.1300, longitud=-77.0297).json()
    publicar(cliente, cabeceras, titulo="Cochera en otro distrito", latitud=-12.0464, longitud=-77.0428)

    r = cliente.get("/api/cocheras/buscar", params={"lat": -12.1211, "lng": -77.0297, "radio_km": 3})
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert ids == [cerca["id"], medio["id"]]          # la lejana queda fuera del radio
    assert r.json()[0]["distancia_km"] < 0.05
    assert 0.9 < r.json()[1]["distancia_km"] < 1.1     # ~0.99 km al sur


def test_una_cochera_pausada_no_aparece_en_la_busqueda(cliente):
    cabeceras, _ = registrar(cliente, "arrendador")
    c = publicar(cliente, cabeceras).json()
    cliente.patch(f"/api/cocheras/{c['id']}/estado", json={"activa": False}, headers=cabeceras)
    r = cliente.get("/api/cocheras/buscar", params={"lat": -12.1211, "lng": -77.0297})
    assert r.json() == []
    # el dueño la sigue viendo en su lista
    assert len(cliente.get("/api/cocheras/mias", headers=cabeceras).json()) == 1


def test_no_se_puede_modificar_la_cochera_de_otro(cliente):
    cab_a, _ = registrar(cliente, "arrendador", "Ana Uno")
    cab_b, _ = registrar(cliente, "arrendador", "Beto Dos")
    c = publicar(cliente, cab_a).json()
    r = cliente.patch(f"/api/cocheras/{c['id']}/estado", json={"activa": False}, headers=cab_b)
    assert r.status_code == 403


def test_cotizar_calcula_el_costo_con_las_franjas(cliente, escenario):
    cid = escenario["cochera"]["id"]
    # lunes 17:00–20:00 → 1 h a S/ 6 + 2 h a S/ 9 = S/ 24
    r = cliente.get(f"/api/cocheras/{cid}/cotizar",
                    params={"inicio": proximo(0, 17).isoformat(), "fin": proximo(0, 20).isoformat()})
    assert r.status_code == 200
    assert r.json() == {"disponible": True, "motivo": None, "minutos": 180, "costo_total": 24.0}


def test_cotizar_avisa_si_esta_fuera_del_calendario(cliente, escenario):
    cid = escenario["cochera"]["id"]
    # el sábado no está en el calendario
    r = cliente.get(f"/api/cocheras/{cid}/cotizar",
                    params={"inicio": proximo(5, 10).isoformat(), "fin": proximo(5, 12).isoformat()})
    assert r.json()["disponible"] is False
    assert "no está disponible" in r.json()["motivo"]


def test_cambiar_tarifas_aplica_de_inmediato(cliente, escenario):
    cid, cab = escenario["cochera"]["id"], escenario["cab_dueno"]
    r = cliente.put(f"/api/cocheras/{cid}/tarifas", json={"precio_hora": 10, "tarifas": []}, headers=cab)
    assert r.status_code == 200
    r = cliente.get(f"/api/cocheras/{cid}/cotizar",
                    params={"inicio": proximo(0, 17).isoformat(), "fin": proximo(0, 20).isoformat()})
    assert r.json()["costo_total"] == 30.0
