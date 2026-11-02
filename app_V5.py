# ==============================================================================
# BASS ENGINE — APP COMPLETA (Streamlit)
# ==============================================================================
# Avvio:       streamlit run app.py          (Python 3.10+, pacchetti in requirements.txt)
# Contenuto:   Blocco1-BF-V3.py, Blocco2-BF-V2.py, Blocco3-BF-V3.py, Blocco4-BF-V4.py, Blocco5-BF-V5.py, in quest'ordine,
#              copiati senza modifiche salvo `_b0_magia = ` davanti alle espressioni isolate (vedi build_app.py).
#              Per cambiare un blocco: modificare il suo file e rigenerare app.py con build_app.py. Ogni blocco
#              inizia con una riga "# >>> BLOCCO: <file>".
# Richiede:    .streamlit/config.toml nella cartella da cui si avvia l'app (tema scuro); il logo (facoltativo)
#              nella cartella Logo accanto a questo file oppure direttamente accanto a questo file.
# ==============================================================================
import math
import requests
import streamlit as st


# >>> BLOCCO: Blocco1-BF-V3.py <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ==============================================================================
# BASS ENGINE — BLOCCO 1 (v3): DATI METEO, MODELLO TERMICO, OSSIGENO, STATO BIOLOGICO
# ==============================================================================
_b0_magia = """
v3 (29/10/2026), rispetto alla v2: storico meteo dalla Historical Forecast API di Open-Meteo (la Forecast API
restituiva null oltre ~49 giorni); nel bilancio di calore vento riportato all'acqua aperta (l'acqua risultava in
media +1.8 °C troppo calda su 18 laghi misurati); nuovo spot "Grande Lago Profondo"; ossigeno con ampiezze del
ciclo giorno-notte realistiche ed effetto del caldo oltre 25 °C; stato biologico con l'ossigeno 4-5 mg/L citato a
ogni temperatura. Interfaccia invariata. Dettagli e verifiche in CHANGELOG_Blocco1.md, sezioni 6 e 7.
02/11/2026: se la Historical Forecast API è sovraccarica (429, 5xx) o non risponde, i dati arrivano dalla Forecast
API (storia più corta, con un avviso e affidabilità ridotta) invece di fermare l'app (PARAMS["api_url_fallback"]).

Blocco 1 dell'app Streamlit "Bass Engine": dalla posizione e dalla data alla serie oraria che leggono i
Blocchi 2, 3, 4 e 5. File unico, ottenuto da tre parti:
    PARTE A  dati meteo Open-Meteo: ora locale corretta con zoneinfo, 24 ore esatte per giorno, buchi
             brevi interpolati, variazioni di pressione a 3 h e 12 h da pressure_msl;
    PARTE B  modello termico: bilancio energetico di superficie (onde corte, onde lunghe, calore sensibile e
             latente con correzione di stabilità), simulazione giornaliera su tutta la storia e curva oraria;
    PARTE C  ossigeno disciolto (Benson & Krause 1984, come USGS TM 2011.03), stato biologico, interfaccia
             pubblica fetch_thermal_and_weather_series.

INTERFACCIA PUBBLICA (letta dai Blocchi 2, 4 e 5)
    fetch_thermal_and_weather_series(lat, lon, day_offset, spot_morphology, target_date=None) -> dict
        Con cache Streamlit (ttl 1800 s). target_date "AAAA-MM-GG" ha la precedenza su day_offset
        (giorni da oggi nel fuso del luogo). Eccezioni: solo requests.* (rete, HTTP) e ValueError (dati).
    Chiavi: base_water_temp (°C, 1 decimale), macro_trend_14d, micro_trend_72h, biological_state,
        hourly (24 dict, ore 0-23), thermal_trend_3d (= micro_trend_72h), mean_7d_air;
        facoltative: data_gaps, ice_risk, low_confidence, elevation_m, più diagnostica (warnings, ...).
    Riga oraria: hour, time_label "HH:00", date_str, air_temp, water_temp (1 decimale), pressure (= pressure_msl,
        hPa), pressure_delta (hPa in 3 h), pressure_trend_12h (hPa in 12 h), clouds (int %), wind (km/h),
        radiation (int W/m²), do_saturation_index (0-1), surface_pressure, humidity, do_sat_mg_l, do_actual_mg_l.
    SPOT_TYPES: le quattro morfologie (le prime tre con le chiavi del Blocco 1 originale, più "Grande Lago
        Profondo" dalla v3), con "desc".
    classify_biological_state(t, macro_14d, micro_72h, do_mg_l=None) -> str  (riusabile con la sonda)

FUNZIONI PURE (senza rete, per test e diagnosi)
    build_thermal_series(data, spot_morphology, target_date=None, day_offset=0, now_utc=None)
    parse_weather_payload, compute_water_temperature, heat_fluxes, stability_factor, do_saturation_mg_l, ...

USO NELL'APP
    Incollare questo file al posto del vecchio Blocco 1, prima dei Blocchi 2-5. Gli import necessari sono qui
    sotto; se `requests` o `st` sono già definiti (import in cima al file dell'app, o moduli finti di un test)
    vengono usati quelli. Senza Streamlit installato la cache diventa una funzione normale.

COSTANTI: tutte nel dizionario PARAMS qui sotto, con valore, unità, fonte e tipo
    ([MISURATO] valore documentato o misurato da una fonte citata; [INFERENZA] dedotto; [EURISTICA] scelta di
    progetto). Le chiavi della parte B iniziano con th_, quelle della parte C con ox_ / bio_ / out_.
    Elenco delle modifiche rispetto al Blocco 1 originale: CHANGELOG_Blocco1.md.

Requisiti: Python 3.10+, requests, streamlit (facoltativo per i test), zoneinfo con il database dei fusi
(su Windows il pacchetto `tzdata`).
"""
import datetime as _b1_dt
import math
import math as _b1_math
import zoneinfo as _b1_zoneinfo
import datetime as _b1b_dt
import math as _b1b_math

try:                    # già importato dall'app o fornito da un test (modulo finto): si usa quello
    _b0_magia = requests
except NameError:
    import requests


class _B1StreamlitShim:
    """Sostituto minimo di streamlit quando non è installato: cache_data diventa un decoratore neutro."""

    @staticmethod
    def cache_data(*_args, **_kwargs):
        def decorate(func):
            func.clear = lambda *a, **k: None
            return func
        return decorate


try:                    # già importato dall'app o fornito da un test
    _b0_magia = st
except NameError:
    try:
        import streamlit as st
    except ImportError:
        st = _B1StreamlitShim()



# ==============================================================================
# PARAMETRI — tutte le costanti del Blocco 1 (parte A, poi B, poi C)
# ==============================================================================
# Etichette: [MISURATO] = valore documentato o misurato da una fonte citata;
#            [INFERENZA] = dedotto da fatti documentati; [EURISTICA] = scelta di progetto.
# Le fonti sulla API sono state consultate il 29/10/2026. La pagina ufficiale
# open-meteo.com/en/docs non era leggibile da questo ambiente (accesso automatico negato):
# i limiti vengono da copie dello schema OpenAPI e da SDK che lo replicano.
PARAMS = {
    # --- Endpoint e richiesta --------------------------------------------------------------
    # URL della Historical Forecast API: stessi parametri (past_days, forecast_days) e stessi valori della
    # Weather Forecast API, ma con lo storico completo. La Forecast API (api.open-meteo.com/v1/forecast)
    # accetta past_days fino a 92 ma conserva dati solo per ~49 giorni in Italia e ~33 negli USA: prima
    # restituisce null in tutte le variabili. Verificato il 29/10/2026 con chiamate reali (Trasimeno, Taupo,
    # Okeechobee; past_days 63, forecast_days 2-16): 0 ore con null qui, 325-738 ore con null nella Forecast
    # API; valori identici dove entrambe hanno dati. [MISURATO]
    "api_url": "https://historical-forecast-api.open-meteo.com/v1/forecast",
    # Riserva se la Historical Forecast API non risponde (timeout, rete) o risponde 429/5xx: la Forecast API,
    # stessi parametri, storia più corta (le ore iniziali tutte null vengono tolte). Il 02/11/2026 la Historical
    # rispondeva a ogni chiamata 429 "Too many concurrent requests" mentre la Forecast dava 52 giorni di storia
    # per il Trasimeno. [MISURATO]
    "api_url_fallback": "https://api.open-meteo.com/v1/forecast",
    # Timeout HTTP, secondi. Fonte: Blocco 1 originale. [EURISTICA]
    "http_timeout_s": 15,
    # Variabili orarie richieste -> chiave nel record. Unità con i parametri sotto: °C, %, hPa, hPa, %,
    # km/h, W/m². shortwave_radiation è indicata da Open-Meteo come media dell'ora precedente:
    # DA VERIFICARE sulla pagina ufficiale (rilevante per la parte B). [MISURATO]
    "hourly_vars": {
        "temperature_2m": "air_temp",
        "relative_humidity_2m": "humidity",
        "pressure_msl": "pressure_msl",
        "surface_pressure": "surface_pressure",
        "cloud_cover": "clouds",
        "wind_speed_10m": "wind",
        "shortwave_radiation": "radiation",
    },
    # Unità richieste esplicitamente (sono anche i default dell'API). Fonte: schema OpenAPI Open-Meteo
    # (wind_speed_unit default "kmh", temperature_unit default "celsius"). [MISURATO]
    "temperature_unit": "celsius",
    "wind_speed_unit": "kmh",
    # Orari in secondi UNIX (sempre GMT+0 secondo la documentazione): li convertiamo noi con zoneinfo.
    # Fonte: schema OpenAPI Open-Meteo, parametro timeformat. [MISURATO]
    "timeformat": "unixtime",
    # Fuso risolto dall'API dalle coordinate; la risposta contiene il nome IANA ("timezone") e un solo
    # utc_offset_seconds. Fonte: schema OpenAPI Open-Meteo. [MISURATO]
    "timezone": "auto",
    # Massimo past_days accettato dalla Forecast API, giorni. Fonte: schema OpenAPI (docs.anysite.io,
    # copia dello schema), SDK openmeteo-rs (MAX_PAST_DAYS = 92), attori Apify (0-92). [MISURATO]
    "api_past_days_max": 92,
    # Massimo forecast_days, giorni. Stesse fonti (MAX_FORECAST_DAYS = 16; 0-16). [MISURATO]
    "api_forecast_days_max": 16,

    # --- Storia -----------------------------------------------------------------------------
    # Giorni di storia da chiedere almeno (prima del giorno richiesto); sotto questa soglia
    # low_confidence = True. Fonte: requisito del progetto. [EURISTICA]
    "history_days_target": 60,
    # Minimo assoluto di giorni di storia: sotto si solleva ValueError (servono i trend a 14 giorni).
    # Fonte: requisito del progetto. [EURISTICA]
    "history_days_min": 14,
    # Giorni di margine per la differenza tra data UTC e data locale (fusi da -12 h a +14 h). [INFERENZA]
    "date_margin_days": 1,
    # Giorno di margine per il primo giorno della finestra, che può arrivare incompleto: la risposta ha un
    # solo offset UTC, quindi se la finestra attraversa un cambio d'ora il primo giorno locale perde
    # un'ora e viene scartato. Comportamento esatto dell'API DA VERIFICARE con una chiamata reale. [INFERENZA]
    "edge_margin_days": 1,

    # --- Pulizia ---------------------------------------------------------------------------
    # Lunghezza massima di un buco (ore consecutive mancanti) colmato per interpolazione lineare, ore.
    # Fonte: requisito del progetto. [EURISTICA]
    "max_gap_hours": 3,
    # Ore locali mancanti consecutive ricostruibili per interpolazione (giorno da 23 ore: 1 ora).
    # Fonte: il cambio d'ora in Europa sposta l'orologio di 1 h (Direttiva 2000/84/CE). [MISURATO]
    "max_structural_gap_slots": 1,
    # Variabili che devono essere tutte presenti in ognuna delle 24 ore del giorno richiesto. [EURISTICA]
    "required_keys": ("air_temp", "humidity", "pressure_msl", "surface_pressure", "clouds", "wind", "radiation"),
    # Intervalli plausibili (estremi inclusi); un valore fuori intervallo è trattato come mancante.
    # Limiti volutamente larghi, oltre i record noti. [EURISTICA]
    "valid_ranges": {
        # °C. Record mondiali citati dal WMO: 56.7 °C (Furnace Creek, 1913), -89.2 °C (Vostok, 1983)
        # — DA VERIFICARE i valori esatti.
        "air_temp": (-90.0, 60.0),
        # %: umidità relativa per definizione 0-100. [MISURATO]
        "humidity": (0.0, 100.0),
        # hPa al livello del mare. Record citati: ~870 hPa (tifone Tip, 1979), ~1084 hPa (Siberia/Mongolia)
        # — DA VERIFICARE.
        "pressure_msl": (850.0, 1090.0),
        # hPa al suolo: 300 hPa ~ quota 9000 m (atmosfera standard ICAO, valore arrotondato), 1090 come sopra.
        "surface_pressure": (300.0, 1090.0),
        # %: copertura nuvolosa per definizione 0-100. [MISURATO]
        "clouds": (0.0, 100.0),
        # km/h a 10 m. Raffica record citata ~408 km/h (Barrow Island, 1996) — DA VERIFICARE.
        "wind": (0.0, 410.0),
        # W/m². Costante solare ~1361 W/m² (Kopp & Lean 2011); margine per l'aumento da nubi — DA VERIFICARE.
        "radiation": (0.0, 1500.0),
    },
    # Decimali per valori interpolati e variazioni di pressione. [EURISTICA]
    "round_decimals": 2,
    # Massimo numero di ore in una risposta (92 + 16 giorni + margini stanno sotto): oltre, la risposta
    # è considerata incoerente. [EURISTICA]
    "max_series_hours": 24 * 120,

    # --- Pressione ---------------------------------------------------------------------------
    # Intervalli per pressure_delta e pressure_trend_12h, ore. Fonte: requisito + Blocco 2 (3h x 12h). [EURISTICA]
    "pressure_lag_short_h": 3,
    "pressure_lag_long_h": 12,

    # --- Cache Streamlit ------------------------------------------------------------------------
    # Durata della cache dei dati scaricati, secondi. Fonte: Blocco 1 originale (ttl=1800). [EURISTICA]
    "cache_ttl_s": 1800,
}

# --- PARTE B: modello termico --------------------------------------------------------------------
PARAMS.update({
    # --- Costanti fisiche -------------------------------------------------------------------
    # Costante di Stefan-Boltzmann, W m-2 K-4. Fonte: CODATA 2018. [MISURATO]
    "th_sigma_sb": 5.670374419e-8,
    # Zero assoluto in °C, K. Fonte: definizione SI. [MISURATO]
    "th_kelvin": 273.15,
    # Capacità termica volumica dell'acqua rho_w*c_w, J m-3 K-1 (~1000 kg/m³ x ~4180 J/kg/K).
    # Fonte: requisito del progetto, valore standard da manuale. [MISURATO]
    "th_rho_c_water": 4.18e6,
    # Calore specifico dell'aria secca a pressione costante, J kg-1 K-1. Valore da manuale. [MISURATO, DA VERIFICARE]
    "th_cp_air": 1005.0,
    # Costante dei gas per l'aria secca, J kg-1 K-1. Valore da manuale. [MISURATO]
    "th_r_dry_air": 287.05,
    # Rapporto Rd/Rv per l'umidità specifica q = 0.622 e / (p - 0.378 e). Valore da manuale. [MISURATO]
    "th_eps_rd_rv": 0.622,
    # Calore latente di vaporizzazione L_v = 2.501e6 - 2361 * T[°C], J/kg. Fonte: FAO-56, Allen et al. 1998,
    # allegato 3 (da Harrison 1963). [MISURATO, DA VERIFICARE]
    "th_lv0": 2.501e6,
    "th_lv_slope": 2361.0,
    # Pressione di vapore saturo e_s = 6.108 * exp(17.27 T / (T + 237.3)) hPa, T in °C. Fonte: FAO-56,
    # Allen et al. 1998 (formula in kPa: 0.6108). Usata anche sotto 0 °C (sopra acqua). [MISURATO]
    "th_esat_a_hpa": 6.108,
    "th_esat_b": 17.27,
    "th_esat_c_c": 237.3,
    # Pressione standard, hPa: usata se il record non ha pressione. Fonte: atmosfera standard ICAO. [MISURATO]
    "th_default_pressure_hpa": 1013.25,
    # Conversione km/h -> m/s. [MISURATO]
    "th_kmh_to_ms": 1.0 / 3.6,

    # --- Parametri del bilancio ----------------------------------------------------------------
    # Albedo dell'acqua per la radiazione solare (valore medio; dipende dall'altezza del sole).
    # Fonte: requisito del progetto, intervallo 0.06-0.08. [MISURATO, DA VERIFICARE]
    "th_albedo_water": 0.07,
    # Emissività dell'acqua nell'infrarosso; per la legge di Kirchhoff è anche la frazione assorbita
    # dell'infrarosso in arrivo (il resto è riflesso). Fonte: requisito del progetto. [MISURATO, DA VERIFICARE]
    "th_eps_water": 0.97,
    # Brutsaert (1975), Water Resources Research 11(5): eps_sereno = 1.24 * (e_a / T_a)^(1/7), e_a in hPa,
    # T_a in K. Coefficiente e forma confermati in Carmona et al. 2012 (HESS 16, eq. 7, con e in kPa x 10). [MISURATO]
    "th_brutsaert_coeff": 1.24,
    "th_brutsaert_exp": 1.0 / 7.0,
    # Correzione per le nuvole di Brutsaert (1982): eps_a = eps_sereno * (1 + 0.22 c^2), c frazione di cielo
    # coperto 0-1. Forma e coefficiente originale riportati in Carmona et al. 2012 (HESS 16, eq. 8). Sostituisce
    # la forma di Crawford & Duchon (1999), che vuole c ricavata dalla radiazione misurata e, usata con la
    # copertura di Open-Meteo, sovrastimava l'infrarosso in arrivo. [MISURATO, DA VERIFICARE sul testo originale]
    "th_cloud_lw_coeff": 0.22,
    # Emissività massima dell'atmosfera (corpo nero alla temperatura dell'aria). [INFERENZA]
    "th_eps_air_max": 1.0,
    # Coefficiente di scambio neutro per il calore sensibile, vento a 10 m. Adimensionale. Fonte: requisito del
    # progetto; Guseva et al. 2023 (JGR Atmospheres 128, >30 laghi) misurano ~1.4e-3 a vento forte e valori più alti
    # sotto 3 m/s. [DA VERIFICARE]
    "th_c_h": 1.3e-3,
    # Coefficiente di scambio neutro per l'evaporazione. Adimensionale. Fonte: requisito; Guseva et al. 2023
    # ~1.0e-3 a vento forte. [DA VERIFICARE]
    "th_c_e": 1.3e-3,
    # Coefficiente di attrito neutro a 10 m: serve solo alla correzione di stabilità (rugosità). Fonte: Guseva et
    # al. 2023, ~1.6e-3 a vento forte sui laghi (abstract). [MISURATO, DA VERIFICARE]
    "th_c_d": 1.6e-3,

    # --- Stabilità atmosferica (Monin-Obukhov) -----------------------------------------------------------
    # True: C_H e C_E corretti per la stabilità (default). False: coefficienti neutri come nella specifica
    # iniziale. [EURISTICA]
    "th_use_stability": True,
    # Costante di von Kármán. Valore da manuale (0.40-0.41). [MISURATO]
    "th_kappa": 0.40,
    # Accelerazione di gravità, m/s². [MISURATO]
    "th_gravity": 9.81,
    # Quota di riferimento del vento e dei coefficienti, m (vento a 10 m di Open-Meteo). Temperatura e umidità
    # sono a 2 m: la differenza di quota è trascurata. [INFERENZA]
    "th_ref_height_m": 10.0,
    # Funzioni di stabilità: instabile x = (1 - 16 zeta)^(1/4) (Businger-Dyer, integrate da Paulson 1970);
    # stabile psi = -5 zeta (Webb 1970, Dyer 1974). Valori da manuale di strato limite. [MISURATO, DA VERIFICARE]
    "th_bd_unstable": 16.0,
    "th_bd_stable": 5.0,
    # Limiti di zeta = z/L: sotto -10 convezione libera piena; nello stabile la forma lineare si usa fino a 1
    # (oltre è poco affidabile e spegnerebbe del tutto gli scambi). [EURISTICA]
    "th_zeta_min": -10.0,
    "th_zeta_stable_max": 1.0,
    # Iterazioni per trovare zeta (converge in 3-5). [EURISTICA]
    "th_mo_iterations": 6,
    # Vento minimo, m/s: tiene conto della convezione libera con aria calma. Fonte: requisito. [EURISTICA]
    "th_wind_min_ms": 0.5,
    # --- Vento sull'acqua (v3) -----------------------------------------------------------------------------
    # Il vento di Open-Meteo è quello a 10 m dei modelli meteo sulla terraferma (rugosità di campi, alberi,
    # rilievi): sull'acqua libera soffia più forte, e le brezze di lago e di valle (Ora del Garda, Breva) sono
    # sottostimate dalla griglia. Con il vento grezzo l'evaporazione era troppo bassa e l'acqua troppo calda:
    # su 18 laghi (11 USGS 2025 misurati ogni 15 min, 7 italiani 2022 da satellite ESA CCI Lakes) lo scarto medio
    # era +1.76 °C, con solo il 26 % dei giorni entro ±1 °C. Nei flussi di calore (e solo lì: il vento mostrato e
    # usato dagli altri blocchi resta quello di Open-Meteo) si usa U = sqrt((f U_10)^2 + U_g^2).
    # f: rapporto vento sull'acqua / vento sulla terra, ~1.2-1.5 per venti deboli e moderati (Coastal Engineering
    # Manual EM 1110-2-1100 parte II, fig. II-2-7, da Resio & Vincent 1977: valori DA VERIFICARE sulla figura).
    # [INFERENZA]
    "th_wind_water_factor": 1.3,
    # U_g, m/s: vento minimo efficace per raffiche, brezze locali e convezione libera che la media oraria della
    # griglia non contiene (stesso ruolo della "gustiness" delle formule di bulk, Fairall et al. 1996, ma più
    # ampio). Con f = 1.3 e U_g = 2.5-3.0 lo scarto medio sui 18 laghi scende a circa 0 °C; il risultato varia
    # poco tra 2.5 e 3.0 (MAE 0.84-0.88 °C su laghi bassi e medi). [EURISTICA tarata su misure]
    "th_wind_gust_ms": 3.0,

    # --- Valori di riserva per input mancanti (solo se la serie non ne fornisce uno valido) ---------------
    # Temperatura usata se mancano sia aria sia acqua, °C. [EURISTICA]
    "th_default_temp_c": 15.0,
    # Umidità relativa, %. [EURISTICA]
    "th_default_rh": 70.0,
    # Copertura nuvolosa, %. [EURISTICA]
    "th_default_clouds": 50.0,

    # --- Simulazione ----------------------------------------------------------------------------
    # Sotto questa temperatura dell'acqua si usa h_eff invernale, °C. Fonte: requisito. [EURISTICA]
    "th_h_winter_below_c": 10.0,
    # Sopra questa temperatura si usa h_eff estivo, °C; in mezzo interpolazione lineare. Fonte: requisito. [EURISTICA]
    "th_h_summer_above_c": 18.0,
    # Limite inferiore della temperatura dell'acqua, °C: punto di congelamento a 1 atm. Il calore latente
    # di fusione e la copertura di ghiaccio non sono modellati. [MISURATO]
    "th_floor_c": 0.0,
    # Soglia per ice_risk, °C. Fonte: requisito. [EURISTICA]
    "th_ice_risk_c": 0.5,
    # Giorni iniziali usati per il seme (media dell'aria). Fonte: requisito. [EURISTICA]
    "th_seed_days": 7,
    # Durata massima di un sotto-passo di integrazione, s. Con h >= 1.5 m e vento fino a ~400 km/h il passo
    # resta molto sotto il limite di stabilità del metodo di Eulero esplicito (verificato nei test). [EURISTICA]
    "th_substep_s": 900,
    # Oltre questa distanza tra due record si segnala un salto nella serie, s. [EURISTICA]
    "th_gap_warn_s": 7200,
    # Giorni minimi di storia prima del giorno richiesto (come la parte A). [EURISTICA]
    "th_history_min_days": 14,
    # Sotto questi giorni di storia il seme pesa ancora sul risultato (costante di tempo dello strato fino a
    # ~2-4 settimane per 6-10 m d'inverno): avviso e low_confidence. [INFERENZA]
    "th_spinup_days": 30,

    # --- Trend ------------------------------------------------------------------------------------
    # macro_trend_14d = media degli ultimi 3 giorni - media dei 3 giorni che finiscono 14 giorni prima. [EURISTICA]
    "th_trend_window_days": 3,
    "th_trend_shift_days": 14,
    # micro_trend_72h = temperatura giornaliera del giorno richiesto - quella di 3 giorni prima. [EURISTICA]
    "th_micro_days": 3,
    # Decimali dei valori restituiti. [EURISTICA]
    "th_round": 2,
})

# Morfologia dello spot. Le prime tre chiavi sono identiche al Blocco 1 originale (le usa il Blocco 5); la quarta
# (Grande Lago Profondo) è nuova nella v3.
# Tutti i valori numerici sono [EURISTICA dichiarata] (requisito del progetto), salvo dove indicato.
#   mean_depth_m, max_depth_m  profondità tipiche, solo descrittive (non entrano nel bilancio)
#   h_eff_summer_m / h_eff_winter_m  spessore rimescolato per la simulazione giornaliera
#   h_diurnal_m  spessore che risponde nell'arco del giorno; equivale ai vecchi rad_factor:
#                h = 3600 s * (1 - albedo) * 1000 W/m² / (rho_w c_w * rad_factor)
#                -> 0.48 -> 1.67 m, 0.30 -> 2.67 m, 0.16 -> 5.0 m [INFERENZA]
#   max_swing    escursione massima della curva oraria, °C: valori del Blocco 1 originale, ora solo limite
#                di sicurezza
PARAMS["th_spot_types"] = {
    "Cava / Lago Profondo (Sassaie, Drop-off)": {
        "mean_depth_m": 12.0,
        "max_depth_m": 30.0,
        "h_eff_summer_m": 6.0,
        "h_eff_winter_m": 10.0,
        "h_diurnal_m": 4.8,
        "max_swing": 1.10,
        "desc": "Cave e laghi profondi fino a circa 30 m. Alta inerzia termica: strato rimescolato di circa 6 m "
                "d'estate e 10 m d'inverno, risente poco degli sbalzi giornalieri.",
    },
    "Lago Medio / Bacino Misto (Canneti, Punte, Legnaie)": {
        "mean_depth_m": 6.0,
        "max_depth_m": 15.0,
        "h_eff_summer_m": 3.0,
        "h_eff_winter_m": 6.0,
        "h_diurnal_m": 2.6,
        "max_swing": 2.10,
        "desc": "Inerzia termica media: strato rimescolato di circa 3 m d'estate e 6 m d'inverno, "
                "equilibrio tra acqua aperta e zone basse.",
    },
    "Acqua Bassa / Canale / Palude / Bozzo (< 2.5m)": {
        "mean_depth_m": 1.5,
        "max_depth_m": 2.5,
        "h_eff_summer_m": 1.5,
        "h_eff_winter_m": 1.5,
        "h_diurnal_m": 1.6,
        "max_swing": 3.40,
        "desc": "Bassa inerzia termica: tutta la colonna (circa 1.5 m) risponde in fretta al sole "
                "e ai fronti freddi.",
    },
    # v3: grandi laghi profondi (profondità media di decine o centinaia di metri). D'inverno si rimescolano molto
    # più a fondo di una cava e conservano il calore; con lo spot "Cava" (10/6 m) risultavano troppo freddi
    # d'inverno (-2/-3 °C) e troppo caldi in primavera ed estate (fino a +6 °C). Spessori 20 m (inverno) e 10 m
    # (estate) scelti su Garda, Maggiore, Como, Bolsena e Bracciano (satellite ESA CCI Lakes, 2022) con lo stesso
    # calcolo dell'app (63 giorni di storia per data): MAE medio 1.43 °C; provati anche 25-120 m d'inverno e 8-16 m
    # d'estate. Limite noto: un solo strato non segue bene l'inizio della stratificazione, quindi in aprile-maggio
    # il modello resta 1-3 °C sotto e in piena estate 1-2 °C sopra nei laghi alpini. [EURISTICA tarata]
    "Grande Lago Profondo (Garda, Maggiore, Como, Iseo, Bolsena, Bracciano)": {
        "mean_depth_m": 100.0,
        "max_depth_m": 100.0,
        "h_eff_summer_m": 10.0,
        "h_eff_winter_m": 20.0,
        "h_diurnal_m": 4.8,
        "max_swing": 1.10,
        "desc": "Inerzia termica molto alta: d'inverno il lago si rimescola in profondità e resta tiepido; "
                "in primavera si scalda lentamente, d'estate lo strato superficiale è di circa 10 m.",
    },
}
# Spot usato se il nome passato non esiste (stessa scelta del Blocco 1 originale). [EURISTICA]
PARAMS["th_default_spot"] = "Lago Medio / Bacino Misto (Canneti, Punte, Legnaie)"

SPOT_TYPES = PARAMS["th_spot_types"]

# --- PARTE C: ossigeno disciolto ------------------------------------------------------------------
PARAMS.update({
    # Benson & Krause (1984), solubilità dell'ossigeno in acqua dolce a 1 atm, mg/L, T in K:
    # ln C* = c0 + c1/T + c2/T^2 + c3/T^3 + c4/T^4. Fonte: USGS Office of Water Quality Technical
    # Memorandum 2011.03 (13/07/2011), eq. 7. [MISURATO]
    "ox_bk_coeffs": (-139.34411, 1.575701e5, -6.642308e7, 1.243800e10, -8.621949e11),
    # Pressione di vapore dell'acqua, atm: ln u = a + b/T + c/T^2. Fonte: USGS TM 2011.03, eq. 11. [MISURATO]
    "ox_pwv_coeffs": (11.8571, -3840.70, -216961.0),
    # Termine theta della correzione di pressione: theta = a + b t + c t^2, t in °C. Fonte: USGS TM 2011.03,
    # eq. 10. Correzione: Cp = C* (P - u)(1 - theta P) / ((1 - u)(1 - theta)), P in atm (eq. 9). [MISURATO]
    "ox_theta_coeffs": (0.000975, -1.426e-5, 6.436e-8),
    # Atmosfera standard, hPa per atm. [MISURATO]
    "ox_hpa_per_atm": 1013.25,
    # Intervallo di temperatura in cui si applica la formula, °C (fuori si usa il valore al limite). [INFERENZA]
    "ox_t_range_c": (0.0, 40.0),
    # Ciclo giornaliero della saturazione (fotosintesi di giorno, respirazione di notte), per morfologia:
    # (sovrasaturazione massima del pomeriggio, deficit massimo all'alba), come frazione della saturazione, a 25 °C,
    # con poco vento e giornata serena. v3: le ampiezze della v2 (0.10/0.25, 0.075/0.15, 0.05/0.05) davano
    # un'escursione giorno-notte 3-5 volte più piccola di quella misurata (USGS 2025, 11 laghi, aprile-ottobre:
    # in media 3.5 mg/L nei laghi bassi e medi, minimo all'alba ~80 % e massimo pomeridiano ~125-135 % della
    # saturazione; fino a 4 mg/L anche nel Ticino con piante sommerse, Perna & Demilio 1986 citati da FAO).
    # Valori scelti sulle medie per tipo di spot, non lago per lago. [EURISTICA tarata su misure]
    "ox_diel_amplitude": {
        "Cava / Lago Profondo (Sassaie, Drop-off)": (0.13, 0.05),
        "Lago Medio / Bacino Misto (Canneti, Punte, Legnaie)": (0.43, 0.31),
        "Acqua Bassa / Canale / Palude / Bozzo (< 2.5m)": (0.65, 0.30),
        "Grande Lago Profondo (Garda, Maggiore, Como, Iseo, Bolsena, Bracciano)": (0.13, 0.05),
    },
    # Effetto della temperatura sul ciclo: 0 a ox_bio_t_low_c, 1 a ox_bio_t_high_c, lineare, fino a ox_bio_t_cap.
    # v3: prima 10-25 °C con tetto 1 (sopra 25 °C nessun effetto in più). La respirazione invece continua a
    # crescere con il caldo più della fotosintesi (energie di attivazione ~0.65 contro ~0.32 eV, Allen, Gillooly &
    # Brown 2005, Functional Ecology 19:202): il tetto 1.4 (raggiunto a 33 °C) è prudente rispetto al rapporto
    # ~1.9 della sola respirazione tra 25 e 33 °C. Senza questo, i cali d'ossigeno delle giornate calde e calme
    # non comparivano mai (0 % dei giorni sotto 5 mg/L contro 7-16 % misurati). [INFERENZA + EURISTICA]
    "ox_bio_t_low_c": 5.0,
    "ox_bio_t_high_c": 25.0,
    "ox_bio_t_cap": 1.4,
    # Vento che dimezza l'ampiezza del ciclo (il moto ondoso riporta l'acqua verso la saturazione), km/h:
    # fattore 1 / (1 + (U / U_ref)^2). [EURISTICA]
    "ox_wind_ref_kmh": 15.0,
    # Radiazione media del giorno che dà fotosintesi piena (giornata serena estiva), W/m². [EURISTICA]
    "ox_light_ref_wm2": 250.0,

    # --- PARTE C: stato biologico (temperatura dell'acqua in °C, ossigeno in mg/L) ---------------------
    # Soglie di temperatura per il persico trota (Micropterus salmoides). Fonte indicata dal progetto:
    # Wright et al. 1999 (TAFS 128:603), Rice et al. 1983 (tramite fonti secondarie) — entrambe DA VERIFICARE;
    # il CTmax di 37.3 °C (acclimatazione 24 °C, Fields et al. 1987, TAFS 116:856) conferma che la soglia di
    # stress resta sotto il limite letale. [INFERENZA]
    "bio_t_minimal_c": 6.0,      # sotto: attività minima
    "bio_t_reduced_c": 12.0,     # 6-12: attività ridotta
    "bio_t_growing_c": 20.0,     # 12-20: attività in crescita; 20-30: ottimale
    "bio_t_hot_c": 30.0,         # 30-32: caldo elevato, possibile stress
    "bio_t_stress_c": 32.0,      # sopra: stress termico
    # Ossigeno: sotto 5 mg/L l'attività è limitata, sotto 4 mg/L stress. Fonte indicata: EPA 1986 (criteri per
    # acque calde; tabella numerica DA VERIFICARE). Il documento EPA riporta soglie letali tra 1 e 3 mg/L e la morte
    # di larve di persico trota dopo 3 h a 2.5 mg/L. [INFERENZA]
    "bio_do_low_mg_l": 5.0,
    "bio_do_stress_mg_l": 4.0,
    # Variazioni che vengono citate nel testo: in 72 h e in 14 giorni, °C. [EURISTICA]
    "bio_micro_note_c": 1.0,
    "bio_macro_note_c": 1.0,

    # --- PARTE C: uscita --------------------------------------------------------------------------------
    # Giorni per mean_7d_air (aria media degli ultimi 7 giorni, giorno richiesto incluso, come l'originale). [EURISTICA]
    "out_mean_air_days": 7,
    # Quota stimata dalla pressione se Open-Meteo non dà "elevation": formula barometrica dell'atmosfera
    # standard ICAO z = 44330.8 (1 - (p / p_msl)^0.190263), m. [MISURATO, approssimata]
    "out_baro_height_m": 44330.8,
    "out_baro_exp": 0.190263,
})



# ==============================================================================
# PARTE A — DATI METEO (Open-Meteo)
# ==============================================================================
# Scarica da Open-Meteo la serie oraria (storia + previsione) e la restituisce pulita:
# ora locale corretta anche nei giorni del cambio d'ora, esattamente 24 ore per giorno,
# buchi brevi interpolati e variazioni di pressione a 3 h e 12 h per il giorno richiesto.
#
# Funzione principale
#     load_weather_series(lat, lon, target_date, past_days, *, today=None) -> dict
#
# Funzioni pure (senza rete), utili per i test e per le parti B e C
#     build_weather_request(lat, lon, target_date, past_days, today=None) -> (params, meta)
#     parse_weather_payload(data, target_date, history_wanted=None) -> dict
#
# Contratto dell'uscita
#     days            {"AAAA-MM-GG": [24 record orari, ore 0..23 in ordine]}
#     dates           lista ordinata delle date presenti in `days`
#     target_date     "AAAA-MM-GG"
#     data_gaps       numero di valori mancanti (None o fuori intervallo) interpolati (buchi <= 3 h)
#     low_confidence  True se la storia è < 60 giorni, se il fuso orario non è stato risolto,
#                     se un giorno di storia ha ancora valori mancanti o è stato scartato
#     timezone        nome IANA restituito da Open-Meteo (es. "Europe/Rome")
#     + chiavi diagnostiche: history_days, history_days_requested, incomplete_dates,
#       unfilled_values, dst_fixes, warnings, utc_offset_seconds, request (solo da load_weather_series)
#
# Record orario
#     date_str, hour (int 0-23), time_label "HH:00", utc_ts (secondi UNIX),
#     air_temp °C, humidity %, pressure_msl hPa, surface_pressure hPa, clouds %, wind km/h, radiation W/m²,
#     filled_vars (variabili interpolate in quell'ora), synthetic_hour (True per l'ora ricostruita
#     nel giorno da 23 ore). Solo nel giorno richiesto anche: pressure_delta (hPa in 3 h) e
#     pressure_trend_12h (hPa in 12 h), calcolati da pressure_msl su ore reali (UTC), quindi corretti
#     anche a cavallo del cambio d'ora. Nella storia un valore può restare None (buco > 3 h): la data
#     compare allora in incomplete_dates. Nel giorno richiesto tutti i valori sono numerici.
#
# Eccezioni
#     ValueError      giorno richiesto con meno di 24 ore valide (anche se fuori dall'orizzonte
#                     dell'API), storia più corta di 14 giorni, risposta senza dati leggibili,
#                     parametri d'ingresso non validi (data, coordinate).
#     requests.*      errori di rete o HTTP (il messaggio include la "reason" di Open-Meteo).
#
# Nomi: le funzioni interne iniziano con `_b1_` come negli altri blocchi, così il file si può
# incollare insieme agli altri senza collisioni.

_B1_HOUR_S = 3600
_B1_EPOCH = _b1_dt.datetime(1970, 1, 1)


# ==============================================================================
# UTILITÀ (pure)
# ==============================================================================
def _b1_num(value):
    """Numero finito come float, altrimenti None (None, bool, testo non numerico, NaN, inf)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        x = float(value)
    elif isinstance(value, str):
        try:
            x = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return x if _b1_math.isfinite(x) else None


def _b1_int(value, default):
    x = _b1_num(value)
    if x is None:
        return default
    return int(round(x))


def _b1_parse_date(value, label="target_date"):
    if isinstance(value, _b1_dt.datetime):
        return value.date()
    if isinstance(value, _b1_dt.date):
        return value
    try:
        return _b1_dt.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ValueError("%s non valida: %r (formato atteso AAAA-MM-GG)." % (label, value)) from None


def _b1_today(today):
    if today is None:
        return _b1_dt.datetime.now(_b1_dt.timezone.utc).date()
    return _b1_parse_date(today, "today")


def _b1_in_range(key, x):
    lo, hi = PARAMS["valid_ranges"].get(key, (-_b1_math.inf, _b1_math.inf))
    return lo <= x <= hi


def _b1_round(x):
    return round(x, PARAMS["round_decimals"])


def _b1_api_name(key):
    for api, k in PARAMS["hourly_vars"].items():
        if k == key:
            return api
    return key


def _b1_parse_time(value, utc_offset_s):
    """-> (secondi UNIX oppure None, True se era un orario ISO locale)."""
    if value is None or isinstance(value, bool):
        return None, False
    if isinstance(value, int):
        return value, False
    if isinstance(value, float):
        return (int(value), False) if _b1_math.isfinite(value) and value.is_integer() else (None, False)
    if isinstance(value, str):
        s = value.strip()
        if s.lstrip("+-").isdigit():
            return int(s), False
        try:
            moment = _b1_dt.datetime.fromisoformat(s)
        except ValueError:
            return None, False
        if moment.tzinfo is not None:
            return int(moment.timestamp()), True
        # Orario locale ISO dell'API (timeformat=iso8601): l'API applica un solo offset a tutta la serie.
        return int((moment - _B1_EPOCH).total_seconds()) - int(utc_offset_s), True
    return None, False


def _b1_resolve_tz(data, warnings):
    """-> (tzinfo, nome, esatto). Fuso IANA con zoneinfo; se non disponibile, offset fisso della risposta."""
    name = str(data.get("timezone") or "").strip()
    offset = _b1_int(data.get("utc_offset_seconds"), 0)
    if name:
        try:
            return _b1_zoneinfo.ZoneInfo(name), name, True
        except (_b1_zoneinfo.ZoneInfoNotFoundError, ValueError, TypeError, OSError):
            pass
    offset = max(-14 * _B1_HOUR_S, min(14 * _B1_HOUR_S, offset))
    warnings.append(
        "Fuso orario %r non risolto con zoneinfo: uso l'offset fisso %+d s della risposta. Nei giorni "
        "lontani da un cambio d'ora le ore possono essere sfasate di 1 h (su Windows installare il "
        "pacchetto 'tzdata')." % (name or "assente", offset))
    return _b1_dt.timezone(_b1_dt.timedelta(seconds=offset)), (name or "UTC"), False


# ==============================================================================
# RICHIESTA A OPEN-METEO
# ==============================================================================
def build_weather_request(lat, lon, target_date, past_days, today=None):
    """
    Parametri della chiamata a Open-Meteo per avere `past_days` (almeno 60) giorni di storia prima
    di `target_date` più il giorno stesso. `today` (AAAA-MM-GG) serve ai test; di default è la data UTC.
    -> (params, meta). Solleva ValueError se la data è chiaramente fuori dalla portata dell'API.
    """
    P = PARAMS
    lat_f, lon_f = _b1_num(lat), _b1_num(lon)
    if lat_f is None or not -90.0 <= lat_f <= 90.0:
        raise ValueError("Latitudine non valida: %r (attesa tra -90 e 90)." % (lat,))
    if lon_f is None or not -180.0 <= lon_f <= 180.0:
        raise ValueError("Longitudine non valida: %r (attesa tra -180 e 180)." % (lon,))
    target = _b1_parse_date(target_date)
    today_d = _b1_today(today)
    history_wanted = max(_b1_int(past_days, P["history_days_target"]), P["history_days_target"])

    days_ahead = (target - today_d).days            # > 0: data futura; < 0: data passata
    days_back = max(0, -days_ahead)
    if days_ahead > P["api_forecast_days_max"]:
        raise ValueError(
            "Il giorno richiesto %s è oltre l'orizzonte di previsione di Open-Meteo (%d giorni da oggi, %s): "
            "non può avere 24 ore di dati." % (target, P["api_forecast_days_max"], today_d))
    if P["api_past_days_max"] - days_back < P["history_days_min"]:
        raise ValueError(
            "Il giorno richiesto %s è troppo indietro (%d giorni fa): Open-Meteo restituisce al massimo %d giorni "
            "passati, quindi la storia sarebbe più corta dei %d giorni minimi."
            % (target, days_back, P["api_past_days_max"], P["history_days_min"]))

    api_past = history_wanted + days_back + P["date_margin_days"] + P["edge_margin_days"]
    api_fore = days_ahead + 1 + P["date_margin_days"]
    api_past = max(0, min(P["api_past_days_max"], api_past))
    api_fore = max(1, min(P["api_forecast_days_max"], api_fore))

    params = {
        "latitude": round(lat_f, 4),
        "longitude": round(lon_f, 4),
        "hourly": ",".join(P["hourly_vars"].keys()),
        "timezone": P["timezone"],
        "timeformat": P["timeformat"],
        "temperature_unit": P["temperature_unit"],
        "wind_speed_unit": P["wind_speed_unit"],
        "past_days": api_past,
        "forecast_days": api_fore,
    }
    meta = {"target_date": target.isoformat(), "today": today_d.isoformat(), "history_wanted": history_wanted}
    return params, meta


def _b1_fetch(params):
    """
    Unico I/O del modulo: GET a Open-Meteo -> dict della risposta JSON. Se la Historical Forecast API è
    sovraccarica o irraggiungibile, riprova sulla Forecast API e segna la risposta con "_b1_fallback".
    """
    try:
        return _b1_get(PARAMS["api_url"], params)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.HTTPError) as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        if isinstance(exc, requests.HTTPError) and not (code == 429 or (code or 0) >= 500):
            raise
        try:
            payload = _b1_get(PARAMS["api_url_fallback"], params)
        except (requests.exceptions.RequestException, ValueError):
            raise exc
    hourly = payload.get("hourly")
    if isinstance(hourly, dict) and isinstance(hourly.get("time"), list):
        cols = [v for k, v in hourly.items() if k != "time" and isinstance(v, list)]
        first = next((i for i in range(len(hourly["time"])) if any(i < len(c) and c[i] is not None for c in cols)),
                     len(hourly["time"]))
        for k, v in hourly.items():
            if isinstance(v, list):
                hourly[k] = v[first:]
    payload["_b1_fallback"] = True
    return payload


def _b1_get(url, params):
    """GET a un endpoint Open-Meteo -> dict della risposta JSON; HTTPError con la "reason" di Open-Meteo."""
    resp = requests.get(url, params=params, timeout=PARAMS["http_timeout_s"])
    code = _b1_int(getattr(resp, "status_code", 200), 200)
    try:
        payload = resp.json()
    except ValueError:
        payload = None
    if code >= 400:
        reason = payload.get("reason") if isinstance(payload, dict) else None
        raise requests.HTTPError(
            "Open-Meteo ha risposto %d: %s" % (code, reason or "nessun dettaglio nella risposta"), response=resp)
    if not isinstance(payload, dict):
        raise ValueError("Risposta di Open-Meteo non leggibile (JSON assente o non valido).")
    if payload.get("error"):
        raise ValueError("Open-Meteo ha segnalato un errore: %s" % (payload.get("reason") or "senza dettagli"))
    return payload


# ==============================================================================
# PULIZIA DELLA SERIE (pure)
# ==============================================================================
def _b1_build_grid(data, warnings):
    """
    Serie oraria regolare in UTC: dal primo all'ultimo istante, un valore per ora (None dove manca).
    -> {"t0", "n", "vals": {chiave: [valori]}, "missing_vars", "iso_times"}
    """
    P = PARAMS
    keys = list(P["hourly_vars"].values())
    out = {"t0": 0, "n": 0, "vals": {k: [] for k in keys}, "missing_vars": [], "iso_times": False}

    hourly = data.get("hourly")
    hourly = hourly if isinstance(hourly, dict) else {}
    raw_times = hourly.get("time")
    raw_times = raw_times if isinstance(raw_times, (list, tuple)) else []
    offset = _b1_int(data.get("utc_offset_seconds"), 0)

    first_index = {}
    bad_t = dup_t = iso_t = 0
    for i, t in enumerate(raw_times):
        ts, was_iso = _b1_parse_time(t, offset)
        if ts is None:
            bad_t += 1
            continue
        iso_t += 1 if was_iso else 0
        if ts in first_index:
            dup_t += 1
            continue
        first_index[ts] = i
    if not first_index:
        warnings.append("La risposta non contiene orari leggibili.")
        return out

    t0, t_last = min(first_index), max(first_index)
    n = (t_last - t0) // _B1_HOUR_S + 1
    if n > P["max_series_hours"]:
        raise ValueError(
            "Risposta di Open-Meteo incoerente: la serie copre %d ore (massimo atteso %d)." % (n, P["max_series_hours"]))

    cols = {}
    for api_name, key in P["hourly_vars"].items():
        col = hourly.get(api_name)
        if not isinstance(col, (list, tuple)):
            out["missing_vars"].append(api_name)
            col = []
        elif len(col) < len(raw_times):
            warnings.append("La colonna %s ha %d valori su %d orari: quelli mancanti sono trattati come buchi."
                            % (api_name, len(col), len(raw_times)))
        cols[key] = col

    vals = {key: [None] * n for key in keys}
    off_grid = rejected = 0
    for ts, i in first_index.items():
        k, rem = divmod(ts - t0, _B1_HOUR_S)
        if rem:
            off_grid += 1
            continue
        for key, col in cols.items():
            x = _b1_num(col[i]) if i < len(col) else None
            if x is not None and not _b1_in_range(key, x):
                rejected += 1
                x = None
            vals[key][k] = x

    holes = n - (len(first_index) - off_grid)
    if out["missing_vars"]:
        warnings.append("Variabili assenti nella risposta: %s." % ", ".join(out["missing_vars"]))
    if bad_t:
        warnings.append("%d orari illeggibili ignorati." % bad_t)
    if dup_t:
        warnings.append("%d orari UTC duplicati ignorati (tenuto il primo)." % dup_t)
    if off_grid:
        warnings.append("%d orari fuori dalla griglia oraria ignorati." % off_grid)
    if holes:
        warnings.append("%d ore assenti nella sequenza degli orari, trattate come buchi." % holes)
    if rejected:
        warnings.append("%d valori fuori dagli intervalli plausibili trattati come mancanti." % rejected)
    if iso_t:
        warnings.append("Orari in formato ISO locale (non unixtime): convertiti con l'offset fisso della "
                        "risposta, possibile sfasamento di 1 h vicino al cambio d'ora.")

    out.update({"t0": t0, "n": n, "vals": vals, "iso_times": iso_t > 0})
    return out


def _b1_fill_short_gaps(values, max_gap):
    """Interpolazione lineare dei buchi lunghi al massimo `max_gap` ore con valori validi ai due lati.
    -> (valori, maschera dei valori interpolati)."""
    out = list(values)
    filled = [False] * len(out)
    n, i = len(out), 0
    while i < n:
        if out[i] is not None:
            i += 1
            continue
        j = i
        while j < n and out[j] is None:
            j += 1
        if i > 0 and j < n and (j - i) <= max_gap:
            a, b, span = out[i - 1], out[j], j - i + 1
            for k in range(i, j):
                out[k] = _b1_round(a + (b - a) * (k - i + 1) / span)
                filled[k] = True
        i = j
    return out, filled


def _b1_make_record(day, hour, ts, values, filled_vars, synthetic):
    rec = {"date_str": day.isoformat(), "hour": hour, "time_label": "%02d:00" % hour, "utc_ts": int(ts)}
    for key in PARAMS["hourly_vars"].values():
        rec[key] = values.get(key)
    rec["filled_vars"] = list(filled_vars)
    rec["synthetic_hour"] = bool(synthetic)
    return rec


def _b1_assemble_local_days(grid, filled, tz):
    """
    Raggruppa la serie UTC per giorno locale con 24 ore esatte (0-23).
    Giorno da 25 ore: l'ora ripetuta compare due volte, si tiene la prima (ora legale) e si scarta il doppione.
    Giorno da 23 ore: l'ora che non esiste viene ricostruita interpolando le due ore vicine.
    Un giorno con ore non ricostruibili (di solito il primo della finestra) viene scartato.
    """
    t0, n, vals = grid["t0"], grid["n"], grid["vals"]
    keys = list(vals.keys())
    stats = {"duplicates_dropped": 0, "dropped_edge": [], "dropped_inner": []}
    slot_index = {}
    for k in range(n):
        local = _b1_dt.datetime.fromtimestamp(t0 + k * _B1_HOUR_S, tz)
        slot = (local.date(), local.hour)
        if slot in slot_index:
            stats["duplicates_dropped"] += 1
            continue
        slot_index[slot] = k
    if not slot_index:
        return {}, stats

    first_day = min(d for d, _ in slot_index)
    last_day = max(d for d, _ in slot_index)
    flat = []
    for i in range((last_day - first_day).days + 1):
        day = first_day + _b1_dt.timedelta(days=i)
        for h in range(24):
            flat.append((day, h, slot_index.get((day, h))))

    m = len(flat)
    prev_present, next_present = [None] * m, [None] * m
    last = None
    for i in range(m):
        prev_present[i] = last
        if flat[i][2] is not None:
            last = i
    last = None
    for i in range(m - 1, -1, -1):
        next_present[i] = last
        if flat[i][2] is not None:
            last = i

    records, broken = {}, set()
    for i, (day, h, k) in enumerate(flat):
        if k is not None:
            values = {key: vals[key][k] for key in keys}
            filled_here = [key for key in keys if filled[key][k]]
            rec = _b1_make_record(day, h, t0 + k * _B1_HOUR_S, values, filled_here, False)
        else:
            p, q = prev_present[i], next_present[i]
            if p is None or q is None or (q - p) > PARAMS["max_structural_gap_slots"] + 1:
                broken.add(day)
                continue
            kp, kq = flat[p][2], flat[q][2]
            w = (i - p) / float(q - p)
            values = {}
            for key in keys:
                a, b = vals[key][kp], vals[key][kq]
                values[key] = None if a is None or b is None else _b1_round(a + (b - a) * w)
            ts = int(round(t0 + _B1_HOUR_S * (kp + (kq - kp) * w)))
            rec = _b1_make_record(day, h, ts, values, [], True)
        records.setdefault(day, []).append(rec)

    days = {}
    for i in range((last_day - first_day).days + 1):
        day = first_day + _b1_dt.timedelta(days=i)
        if day in broken or len(records.get(day, [])) != 24:
            (stats["dropped_edge"] if day in (first_day, last_day) else stats["dropped_inner"]).append(day.isoformat())
            continue
        days[day.isoformat()] = records[day]
    return days, stats


def _b1_value_at(t0, values, t):
    """Valore della serie oraria UTC all'istante t (interpolazione lineare tra le due ore vicine)."""
    if not values:
        return None
    x = (t - t0) / float(_B1_HOUR_S)
    if x < -1e-9 or x > len(values) - 1 + 1e-9:
        return None
    i = int(_b1_math.floor(x + 1e-9))
    f = x - i
    if f < 1e-9:
        return values[min(i, len(values) - 1)]
    if i + 1 >= len(values):
        return None
    a, b = values[i], values[i + 1]
    if a is None or b is None:
        return None
    return a + (b - a) * f


def _b1_add_pressure_deltas(day_records, t0, pressure_series, warnings):
    """pressure_delta (3 h) e pressure_trend_12h (12 h) su ore reali, usando anche il giorno precedente."""
    P = PARAMS
    missing = []
    for rec in day_records:
        now = rec.get("pressure_msl")
        for lag_h, key in ((P["pressure_lag_short_h"], "pressure_delta"), (P["pressure_lag_long_h"], "pressure_trend_12h")):
            before = _b1_value_at(t0, pressure_series, rec["utc_ts"] - lag_h * _B1_HOUR_S)
            if now is None or before is None:
                rec[key] = None
                missing.append("%s %s" % (rec["time_label"], key))
            else:
                rec[key] = _b1_round(now - before)
    if missing:
        warnings.append("Variazione di pressione non calcolabile (pressione mancante nelle ore precedenti): %s."
                        % ", ".join(missing))


# ==============================================================================
# ELABORAZIONE COMPLETA DELLA RISPOSTA (pura)
# ==============================================================================
def parse_weather_payload(data, target_date, history_wanted=None):
    """Trasforma la risposta JSON di Open-Meteo nel dizionario descritto in testa al modulo."""
    P = PARAMS
    warnings = []
    target = _b1_parse_date(target_date)
    t_str = target.isoformat()
    wanted = max(_b1_int(history_wanted, P["history_days_target"]), P["history_days_target"])
    data = data if isinstance(data, dict) else {}
    if data.get("_b1_fallback"):
        warnings.append("Archivio storico di Open-Meteo non disponibile: dati dal servizio di previsione, con "
                        "una storia meteo più corta.")

    tz, tz_name, tz_exact = _b1_resolve_tz(data, warnings)
    grid = _b1_build_grid(data, warnings)
    if grid["n"] == 0:
        raise ValueError("Nessun dato orario nella risposta di Open-Meteo: il giorno %s non ha ore valide." % t_str)

    filled = {}
    for key in list(grid["vals"].keys()):
        grid["vals"][key], filled[key] = _b1_fill_short_gaps(grid["vals"][key], P["max_gap_hours"])

    days, stats = _b1_assemble_local_days(grid, filled, tz)
    dates = sorted(days.keys())
    required = P["required_keys"]

    # --- giorno richiesto: 24 ore con tutti i valori ---
    if t_str not in days:
        if not dates:
            where = "nessun giorno completo nella risposta"
        elif t_str < dates[0] or t_str > dates[-1]:
            where = "la serie scaricata va dal %s al %s" % (dates[0], dates[-1])
        else:
            where = "le sue ore non sono ricostruibili"
        raise ValueError("Il giorno richiesto %s non ha 24 ore di dati (%s)." % (t_str, where))
    target_rows = days[t_str]
    valid_hours = sum(1 for r in target_rows if all(r.get(k) is not None for k in required))
    if valid_hours < 24:
        missing = []
        for k in required:
            cnt = sum(1 for r in target_rows if r.get(k) is None)
            if cnt:
                missing.append("%s (%d ore)" % (_b1_api_name(k), cnt))
        raise ValueError(
            "Il giorno richiesto %s ha solo %d ore valide su 24 dopo l'interpolazione dei buchi fino a %d ore. "
            "Mancano: %s." % (t_str, valid_hours, P["max_gap_hours"], ", ".join(missing)))

    # --- storia ---
    history_dates = [d for d in dates if d < t_str]
    history_days = len(history_dates)
    if history_days < P["history_days_min"]:
        raise ValueError(
            "Storia meteo troppo corta: %d giorni completi prima del %s, ne servono almeno %d."
            % (history_days, t_str, P["history_days_min"]))

    _b1_add_pressure_deltas(target_rows, grid["t0"], grid["vals"]["pressure_msl"], warnings)

    # --- conteggi e affidabilità ---
    data_gaps = unfilled = synthetic = 0
    incomplete = []
    for d in dates:
        day_missing = 0
        for r in days[d]:
            synthetic += 1 if r["synthetic_hour"] else 0
            data_gaps += len(r["filled_vars"])
            day_missing += sum(1 for k in required if r.get(k) is None)
        if day_missing:
            incomplete.append(d)
            unfilled += day_missing

    low = False
    if history_days < P["history_days_target"]:
        low = True
        warnings.append("Storia di %d giorni, sotto i %d consigliati (massimo past_days dell'API: %d)."
                        % (history_days, P["history_days_target"], P["api_past_days_max"]))
    elif history_days < wanted:
        warnings.append("Storia di %d giorni invece dei %d chiesti." % (history_days, wanted))
    if not tz_exact or grid["iso_times"]:
        low = True
    incomplete_history = [d for d in incomplete if d < t_str]
    if incomplete_history:
        low = True
        warnings.append("Giorni di storia con valori ancora mancanti (buchi oltre %d ore): %s."
                        % (P["max_gap_hours"], ", ".join(incomplete_history)))
    inner_history = [d for d in stats["dropped_inner"] if d < t_str]
    if inner_history:
        low = True
        warnings.append("Giorni di storia scartati perché le ore non erano ricostruibili: %s." % ", ".join(inner_history))

    return {
        "days": days,
        "dates": dates,
        "target_date": t_str,
        "data_gaps": data_gaps,
        "low_confidence": low,
        "timezone": tz_name,
        "history_days": history_days,
        "history_days_requested": wanted,
        "incomplete_dates": incomplete,
        "unfilled_values": unfilled,
        "dst_fixes": {
            "duplicates_dropped": stats["duplicates_dropped"],
            "hours_interpolated": synthetic,
            "edge_days_dropped": stats["dropped_edge"],
            "inner_days_dropped": stats["dropped_inner"],
        },
        "utc_offset_seconds": _b1_int(data.get("utc_offset_seconds"), 0),
        # quota del punto del modello restituita da Open-Meteo (campo "elevation", m s.l.m.); None se assente
        "elevation_m": _b1_num(data.get("elevation")),
        "warnings": warnings,
    }


# ==============================================================================
# FUNZIONE PUBBLICA
# ==============================================================================
def load_weather_series(lat, lon, target_date: str, past_days: int, *, today=None) -> dict:
    """
    Scarica e pulisce la serie oraria Open-Meteo per il giorno `target_date` (AAAA-MM-GG), con almeno
    `past_days` (minimo 60, se l'API lo consente) giorni di storia. `today` serve solo ai test.
    """
    params, meta = build_weather_request(lat, lon, target_date, past_days, today)
    data = _b1_fetch(params)
    out = parse_weather_payload(data, meta["target_date"], meta["history_wanted"])
    out["request"] = {"past_days": params["past_days"], "forecast_days": params["forecast_days"], "today": meta["today"]}
    return out


# ==============================================================================
# PARTE B — MODELLO TERMICO DELL'ACQUA
# ==============================================================================
# Temperatura dell'acqua da un bilancio energetico di superficie, calcolato sulla serie oraria
# prodotta dalla parte A (load_weather_series / parse_weather_payload).
#
# Funzioni pubbliche (tutte pure: nessuna rete, nessun file)
#     heat_fluxes(ta, tw, rh, wind_kmh, sw, clouds, pressure_hpa=None, stability=None) -> dict
#         Flussi in W/m², positivi = guadagno dell'acqua: SW_abs, LW_net, H, LE, Q_net.
#     stability_factor(ta, tw, q_air, q_water, wind_ms) -> (fattore, zeta)
#         Correzione di Monin-Obukhov dei coefficienti C_H e C_E (1 = neutro).
#     effective_depth(spot, tw) -> float
#         Spessore dello strato rimescolato (m) per la simulazione giornaliera.
#     compute_water_trends(daily_water, target_date) -> (macro_trend_14d, micro_trend_72h, avvisi)
#     compute_water_temperature(weather, spot_morphology) -> dict
#         Funzione principale: simulazione su tutta la storia + curva oraria del giorno richiesto.
#
# Modello
#     dTw/dt = Q_net / (rho_w * c_w * h)                       passo orario, sotto-passi di 15 min
#     Q_net  = SW_abs + LW_net + H + LE
#     SW_abs = (1 - albedo) * SW
#     LW_net = eps_w * eps_a * sigma * Ta^4 - eps_w * sigma * Tw^4
#              l'acqua assorbe la frazione eps_w dell'infrarosso in arrivo (legge di Kirchhoff)
#              eps_a cielo sereno: Brutsaert (1975)      1.24 * (e_a[hPa] / Ta[K])^(1/7)
#              correzione nuvole: Brutsaert (1982)       eps_a = eps_sereno * (1 + 0.22 * c^2), al massimo 1,
#              con c = frazione di copertura nuvolosa (Open-Meteo cloud_cover / 100)
#     H      = rho_a * cp_a * C_H * U * (Ta - Tw)
#     LE     = -rho_a * L_v * C_E * U * (q_sat(Tw) - q_a),     q_a dall'umidità relativa
#              C_H = C_HN * f, C_E = C_EN * f: f di Monin-Obukhov (Businger-Dyer / Paulson), > 1 quando l'acqua
#              è più calda dell'aria (strato instabile), < 1 quando l'aria è più calda (stabile)
#     U      = vento a 10 m in m/s, minimo 0.5 m/s (convezione libera)
#     Simulazione giornaliera: h = h_eff, interpolato tra inverno (Tw <= 10 °C) ed estate (Tw >= 18 °C).
#     Seme: media dell'aria dei primi 7 giorni. Limite inferiore 0 °C (il ghiaccio non è modellato).
#     Curva oraria del giorno richiesto: stesso bilancio con h = h_diurnal, partendo dalla temperatura
#     giornaliera alle 23:00 del giorno prima; se l'escursione supera max_swing la curva viene compressa
#     (solo limite di sicurezza, segnalato in swing_clipped).
#
# Passo temporale: si usa la distanza reale tra gli istanti UTC dei record (utc_ts della parte A), quindi
# il giorno del cambio d'ora dura 23 o 25 ore anche nella simulazione. Per l'intervallo che finisce
# all'ora h si usa la radiazione del record h (Open-Meteo la indica come media dell'ora precedente,
# DA VERIFICARE) e per le altre variabili la media tra il record h-1 e il record h. [INFERENZA]
#
# REVISIONE DEL 29/10/2026 (correzione del bias caldo)
#     La prima versione (bilancio della specifica, coefficienti neutri, nuvole alla Crawford & Duchon con la
#     copertura totale) sul clima medio del Lago Trasimeno sovrastimava l'acqua di +4.1 °C in media annua e di
#     +5.6 °C a luglio-agosto rispetto alle misure ILEC (RMSE mensile 4.8 °C). Tre correzioni, ciascuna con una
#     giustificazione fisica propria e nessuna tarata su quei dati:
#       1. legge di Kirchhoff: l'acqua assorbe eps_w = 97 % dell'infrarosso in arrivo, non il 100 %;
#       2. nuvole: Brutsaert (1982) (1 + 0.22 c^2), formula pensata per la frazione di cielo coperto, al posto di
#          Crawford & Duchon (1999), che richiede una nuvolosità ricavata dalla radiazione;
#       3. stabilità: C_H e C_E corretti con Monin-Obukhov (le misure su >30 laghi di Guseva et al. 2023 mostrano
#          che i coefficienti costanti non bastano, soprattutto con vento debole).
#     Risultato sullo stesso confronto (test B11): +0.84 °C in media, RMSE 2.45 °C; il test B3 passa (30.75 °C).
#     Non è stato aggiunto uno scambio con l'acqua profonda: un anno di misure con un valore al mese non basta a
#     fissare un parametro in più senza adattarlo ai dati.
#
# LIMITI NOTI (dai test di test_blocco1B.py)
#     * Il ciclo stagionale resta troppo ampio: sul Trasimeno l'estate è più calda di ~2.6 °C e l'inverno più freddo
#       di ~1.3 °C delle misure 1969-70 (un solo anno, un valore al mese, ora del rilievo non nota: errore della misura
#       stessa di ~1 °C). Lo strato è uno solo e non scambia calore con l'acqua profonda né con il fondo, che nei laghi
#       veri smorzano il ciclo; per la Cava l'effetto reale è probabilmente maggiore.
#     * Con forzanti costanti la temperatura tende all'equilibrio, che non dipende da h: le tre morfologie differiscono
#       nella velocità di risposta (test B4), non nel valore estivo di lungo periodo.
#     * La correzione di stabilità usa vento a 10 m e temperatura a 2 m come se fossero alla stessa quota, e la forma
#       lineare -5 z/L nello stabile limitata a z/L = 1.
#     * Il ghiaccio non è modellato (niente calore latente di fusione): sotto 0 °C la temperatura resta a 0.
#     * La curva oraria rappresenta uno strato di 1.6-4.8 m, non la pellicola superficiale: il massimo è un plateau
#       tra le 17:00 e le 19:00 (test B5), più tardi della superficie vera.
#     * La validazione usa un solo lago poco profondo e un clima medio ricostruito (umidità e sole di Perugia
#       1991-2020): va ripetuta con forzanti Open-Meteo reali e misure recenti appena disponibili (DA VERIFICARE).
#
# Nomi: le funzioni interne iniziano con `_b1b_`. Le costanti stanno in PARAMS con chiavi che iniziano
# con `th_`: se questo file viene unito alla parte A in un unico .py, le chiavi si aggiungono allo stesso
# dizionario PARAMS invece di sostituirlo (nessuna chiave in comune).


# ==============================================================================
# UTILITÀ
# ==============================================================================
def _b1b_num(value, default=None):
    """Numero finito come float, altrimenti `default` (None, bool, testo non numerico, NaN, inf)."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        x = float(value)
    elif isinstance(value, str):
        try:
            x = float(value.strip())
        except ValueError:
            return default
    else:
        return default
    return x if _b1b_math.isfinite(x) else default


def _b1b_clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def _b1b_round(x):
    return None if x is None else round(x, PARAMS["th_round"])


def _b1b_mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _b1b_esat_hpa(t_c):
    """Pressione di vapore saturo sopra acqua, hPa (FAO-56)."""
    P = PARAMS
    t_c = _b1b_clamp(t_c, -80.0, 80.0)
    return P["th_esat_a_hpa"] * _b1b_math.exp(P["th_esat_b"] * t_c / (t_c + P["th_esat_c_c"]))


def _b1b_specific_humidity(e_hpa, p_hpa):
    eps = PARAMS["th_eps_rd_rv"]
    denom = p_hpa - (1.0 - eps) * e_hpa
    return eps * e_hpa / denom if denom > 0 else 0.0


# ==============================================================================
# STABILITÀ ATMOSFERICA (Monin-Obukhov)
# ==============================================================================
def _b1b_psi(zeta):
    """Funzioni integrate di stabilità (psi_m, psi_h)."""
    P = PARAMS
    if zeta < 0.0:
        x = (1.0 - P["th_bd_unstable"] * zeta) ** 0.25
        psi_m = (2.0 * _b1b_math.log((1.0 + x) / 2.0) + _b1b_math.log((1.0 + x * x) / 2.0)
                 - 2.0 * _b1b_math.atan(x) + _b1b_math.pi / 2.0)
        psi_h = 2.0 * _b1b_math.log((1.0 + x * x) / 2.0)
        return psi_m, psi_h
    z = min(zeta, P["th_zeta_stable_max"])
    return -P["th_bd_stable"] * z, -P["th_bd_stable"] * z


def stability_factor(ta, tw, q_air, q_water, wind_ms):
    """
    Rapporto C_H / C_HN (uguale per C_E / C_EN) secondo Monin-Obukhov, con la rugosità ricavata dai
    coefficienti neutri C_D e C_H a 10 m. Galleggiamento dalla differenza di temperatura virtuale aria-acqua
    (conta anche il vapore: aria umida sopra l'acqua è più leggera). -> (fattore, zeta = z/L).
    """
    P = PARAMS
    ta_v, tw_v = _b1b_num(ta), _b1b_num(tw)
    qa, qw = _b1b_num(q_air, 0.0), _b1b_num(q_water, 0.0)
    u = max(P["th_wind_min_ms"], _b1b_num(wind_ms, P["th_wind_min_ms"]))
    if ta_v is None or tw_v is None:
        return 1.0, 0.0
    kappa, z = P["th_kappa"], P["th_ref_height_m"]
    ln_m = kappa / _b1b_math.sqrt(P["th_c_d"])                       # ln(z / z0)
    ln_h = kappa * _b1b_math.sqrt(P["th_c_d"]) / P["th_c_h"]         # ln(z / z0t)
    ta_k = ta_v + P["th_kelvin"]
    d_theta_v = (ta_v - tw_v) * (1.0 + 0.61 * qa) + 0.61 * ta_k * (qa - qw)
    zeta = 0.0
    for _ in range(int(P["th_mo_iterations"])):
        psi_m, psi_h = _b1b_psi(zeta)
        u_star = kappa * u / max(1e-6, ln_m - psi_m)
        t_star = kappa * d_theta_v / max(1e-6, ln_h - psi_h)
        if abs(t_star) < 1e-12:
            zeta = 0.0
            break
        obukhov = u_star * u_star * ta_k / (kappa * P["th_gravity"] * t_star)
        zeta = _b1b_clamp(z / obukhov, P["th_zeta_min"], 10.0)
    psi_m, psi_h = _b1b_psi(zeta)
    neutral = 1.0 / (ln_m * ln_h)
    actual = 1.0 / (max(1e-6, ln_m - psi_m) * max(1e-6, ln_h - psi_h))
    return actual / neutral, zeta


# ==============================================================================
# BILANCIO ENERGETICO
# ==============================================================================
def heat_fluxes(ta, tw, rh, wind_kmh, sw, clouds, pressure_hpa=None, stability=None) -> dict:
    """
    Flussi di calore all'interfaccia aria-acqua, W/m², positivi = guadagno dell'acqua.
    ta, tw °C · rh % · wind_kmh km/h a 10 m · sw W/m² (radiazione globale) · clouds % · pressure_hpa hPa al suolo.
    Il vento è quello sopra terra del modello meteo: qui viene riportato all'acqua aperta con
    th_wind_water_factor e th_wind_gust_ms (v3).
    stability: True/False forza la correzione di stabilità; None usa PARAMS["th_use_stability"].
    Input mancanti o non numerici: valori di riserva di PARAMS, elencati in "defaults_used".
    """
    P = PARAMS
    used = []
    ta_v, tw_v = _b1b_num(ta), _b1b_num(tw)
    if ta_v is None and tw_v is None:
        ta_v = tw_v = P["th_default_temp_c"]
        used += ["ta", "tw"]
    elif ta_v is None:
        ta_v = tw_v
        used.append("ta")
    elif tw_v is None:
        tw_v = ta_v
        used.append("tw")
    ta_v = _b1b_clamp(ta_v, -80.0, 70.0)
    tw_v = _b1b_clamp(tw_v, -5.0, 50.0)

    rh_v = _b1b_num(rh)
    if rh_v is None:
        rh_v = P["th_default_rh"]
        used.append("rh")
    rh_v = _b1b_clamp(rh_v, 0.0, 100.0)

    wind_v = _b1b_num(wind_kmh)
    if wind_v is None:
        wind_v = 0.0
        used.append("wind")
    # vento sull'acqua (v3): il vento a 10 m di Open-Meteo è quello sopra terra, più debole che sul lago
    u_land = max(0.0, wind_v) * P["th_kmh_to_ms"]
    u_ms = max(P["th_wind_min_ms"], _b1b_math.hypot(P["th_wind_water_factor"] * u_land, P["th_wind_gust_ms"]))

    sw_v = _b1b_num(sw)
    if sw_v is None:
        sw_v = 0.0
        used.append("sw")
    sw_v = max(0.0, sw_v)

    cl_v = _b1b_num(clouds)
    if cl_v is None:
        cl_v = P["th_default_clouds"]
        used.append("clouds")
    cloud_frac = _b1b_clamp(cl_v, 0.0, 100.0) / 100.0

    p_v = _b1b_num(pressure_hpa)
    if p_v is None:
        p_v = P["th_default_pressure_hpa"]
        used.append("pressure")
    p_v = _b1b_clamp(p_v, 300.0, 1100.0)

    ta_k = ta_v + P["th_kelvin"]
    tw_k = tw_v + P["th_kelvin"]
    e_a = rh_v / 100.0 * _b1b_esat_hpa(ta_v)
    q_a = _b1b_specific_humidity(e_a, p_v)
    q_sat_w = _b1b_specific_humidity(_b1b_esat_hpa(tw_v), p_v)
    rho_a = p_v * 100.0 / (P["th_r_dry_air"] * ta_k * (1.0 + 0.61 * q_a))

    # Onde corte
    sw_abs = (1.0 - P["th_albedo_water"]) * sw_v
    # Onde lunghe: Brutsaert (1975) per il cielo sereno, Brutsaert (1982) per le nuvole, Kirchhoff per l'assorbimento
    eps_clear = P["th_brutsaert_coeff"] * (max(e_a, 0.0) / ta_k) ** P["th_brutsaert_exp"]
    eps_a = min(P["th_eps_air_max"], eps_clear * (1.0 + P["th_cloud_lw_coeff"] * cloud_frac * cloud_frac))
    lw_in = eps_a * P["th_sigma_sb"] * ta_k ** 4
    lw_out = P["th_eps_water"] * P["th_sigma_sb"] * tw_k ** 4
    lw_net = P["th_eps_water"] * lw_in - lw_out
    # Calore sensibile e latente (formule di bulk), con correzione di stabilità
    use_stab = P["th_use_stability"] if stability is None else bool(stability)
    if use_stab:
        f_stab, zeta = stability_factor(ta_v, tw_v, q_a, q_sat_w, u_ms)
    else:
        f_stab, zeta = 1.0, 0.0
    h_flux = rho_a * P["th_cp_air"] * P["th_c_h"] * f_stab * u_ms * (ta_v - tw_v)
    l_v = P["th_lv0"] - P["th_lv_slope"] * tw_v
    le_flux = -rho_a * l_v * P["th_c_e"] * f_stab * u_ms * (q_sat_w - q_a)

    return {
        "SW_abs": sw_abs,
        "LW_net": lw_net,
        "H": h_flux,
        "LE": le_flux,
        "Q_net": sw_abs + lw_net + h_flux + le_flux,
        "LW_in": lw_in,
        "LW_out": lw_out,
        "eps_air": eps_a,
        "stability_factor": f_stab,
        "zeta": zeta,
        "wind_ms": u_ms,
        "rho_air": rho_a,
        "q_air": q_a,
        "q_sat_water": q_sat_w,
        "defaults_used": used,
    }


def effective_depth(spot, tw) -> float:
    """Spessore rimescolato h_eff (m): invernale sotto 10 °C, estivo sopra 18 °C, lineare in mezzo."""
    P = PARAMS
    spot = spot if isinstance(spot, dict) else SPOT_TYPES[P["th_default_spot"]]
    h_w = _b1b_num(spot.get("h_eff_winter_m"), 6.0)
    h_s = _b1b_num(spot.get("h_eff_summer_m"), 3.0)
    t = _b1b_num(tw, P["th_h_winter_below_c"])
    lo, hi = P["th_h_winter_below_c"], P["th_h_summer_above_c"]
    frac = _b1b_clamp((t - lo) / (hi - lo), 0.0, 1.0) if hi > lo else 1.0
    return max(0.1, h_w + (h_s - h_w) * frac)


def _b1b_resolve_spot(name, warnings):
    key = name if isinstance(name, str) and name in SPOT_TYPES else None
    if key is None:
        key = PARAMS["th_default_spot"]
        warnings.append("Morfologia %r sconosciuta: uso %r." % (name, key))
    return key, SPOT_TYPES[key]


# ==============================================================================
# SERIE DI FORZANTI
# ==============================================================================
_B1B_FORCING_KEYS = ("air_temp", "humidity", "wind", "radiation", "clouds", "pressure")


def _b1b_build_forcing(days, sim_dates, warnings):
    """Record orari in ordine, con i valori mancanti riempiti dal valore valido precedente (o successivo)."""
    rows = []
    for d in sim_dates:
        recs = days.get(d)
        if not isinstance(recs, list):
            continue
        for r in recs:
            if not isinstance(r, dict):
                continue
            p = _b1b_num(r.get("surface_pressure"))
            if p is None:
                p = _b1b_num(r.get("pressure_msl"))
            rows.append({
                "date": d,
                "hour": int(_b1b_num(r.get("hour"), len(rows) % 24)),
                "ts": _b1b_num(r.get("utc_ts")),
                "air_temp": _b1b_num(r.get("air_temp")),
                "humidity": _b1b_num(r.get("humidity")),
                "wind": _b1b_num(r.get("wind")),
                "radiation": _b1b_num(r.get("radiation")),
                "clouds": _b1b_num(r.get("clouds")),
                "pressure": p,
            })
    filled = 0
    for key in _B1B_FORCING_KEYS:
        last = None
        for row in rows:
            if row[key] is None:
                if last is not None:
                    row[key] = last
                    filled += 1
            else:
                last = row[key]
        nxt = None
        for row in reversed(rows):
            if row[key] is None:
                if nxt is not None:
                    row[key] = nxt
                    filled += 1
            else:
                nxt = row[key]
    if filled:
        warnings.append("%d valori orari mancanti nelle forzanti sostituiti con il valore valido più vicino." % filled)
    # istanti UTC: se mancano, un'ora dopo il precedente
    for i, row in enumerate(rows):
        if row["ts"] is None:
            row["ts"] = (rows[i - 1]["ts"] + 3600.0) if i > 0 else 0.0
    return rows, filled


# ==============================================================================
# INTEGRAZIONE
# ==============================================================================
def _b1b_integrate(rows, tw0, depth_of, prev=None, flux_log=None, warnings=None):
    """
    Integra dTw/dt = Q_net / (rho_w c_w h) lungo `rows`, partendo da tw0 all'istante di `prev`
    (se prev è None il primo record è lo stato iniziale). -> (temperature dopo ogni record, secondi integrati).
    """
    P = PARAMS
    tw = max(P["th_floor_c"], tw0)
    out, total_s, gaps = [], 0.0, 0
    for rec in rows:
        if prev is None:
            out.append(tw)
            prev = rec
            continue
        dt = rec["ts"] - prev["ts"]
        if not (dt > 0):
            dt = 3600.0
        if dt > P["th_gap_warn_s"]:
            gaps += 1
        ta = 0.5 * (prev["air_temp"] + rec["air_temp"]) if None not in (prev["air_temp"], rec["air_temp"]) else rec["air_temp"]
        rh = 0.5 * (prev["humidity"] + rec["humidity"]) if None not in (prev["humidity"], rec["humidity"]) else rec["humidity"]
        wd = 0.5 * (prev["wind"] + rec["wind"]) if None not in (prev["wind"], rec["wind"]) else rec["wind"]
        cl = 0.5 * (prev["clouds"] + rec["clouds"]) if None not in (prev["clouds"], rec["clouds"]) else rec["clouds"]
        pr = 0.5 * (prev["pressure"] + rec["pressure"]) if None not in (prev["pressure"], rec["pressure"]) else rec["pressure"]
        sw = rec["radiation"]
        n_sub = max(1, int(_b1b_math.ceil(dt / P["th_substep_s"])))
        sub = dt / n_sub
        for _ in range(n_sub):
            f = heat_fluxes(ta, tw, rh, wd, sw, cl, pr)
            h = depth_of(tw)
            tw = max(P["th_floor_c"], tw + f["Q_net"] * sub / (P["th_rho_c_water"] * h))
            if flux_log is not None:
                for k in ("SW_abs", "LW_net", "H", "LE", "Q_net"):
                    flux_log[k] = flux_log.get(k, 0.0) + f[k] * sub
        total_s += dt
        out.append(tw)
        prev = rec
    if gaps and warnings is not None:
        warnings.append("%d salti di oltre %d ore nella serie: integrati con forzanti costanti."
                        % (gaps, PARAMS["th_gap_warn_s"] // 3600))
    return out, total_s


# ==============================================================================
# TREND
# ==============================================================================
def compute_water_trends(daily_water, target_date):
    """
    daily_water: {"AAAA-MM-GG": temperatura giornaliera} fino al giorno richiesto incluso.
    macro_trend_14d = media dei 3 giorni che finiscono al giorno richiesto - media dei 3 giorni che finiscono
                      14 giorni prima.  micro_trend_72h = giorno richiesto - 3 giorni prima.
    -> (macro, micro, avvisi). Con date mancanti usa quelle disponibili e lo segnala.
    """
    P = PARAMS
    warnings = []
    series = {str(k): v for k, v in (daily_water or {}).items() if _b1b_num(v) is not None}
    try:
        t = _b1b_dt.date.fromisoformat(str(target_date)[:10])
    except ValueError:
        return 0.0, 0.0, ["Data del trend non valida: trend posti a 0."]
    if t.isoformat() not in series:
        return 0.0, 0.0, ["Temperatura del giorno richiesto assente: trend posti a 0."]

    def window(end, n):
        return [series[(end - _b1b_dt.timedelta(days=i)).isoformat()] for i in range(n)
                if (end - _b1b_dt.timedelta(days=i)).isoformat() in series]

    n = P["th_trend_window_days"]
    recent = window(t, n)
    past = window(t - _b1b_dt.timedelta(days=P["th_trend_shift_days"]), n)
    if not past:
        earliest = sorted(series)[:n]
        past = [series[d] for d in earliest]
        warnings.append("Storia corta per il trend a 14 giorni: confronto con i primi giorni disponibili (%s)."
                        % ", ".join(earliest))
    elif len(past) < n:
        warnings.append("Trend a 14 giorni calcolato su %d giorni invece di %d." % (len(past), n))
    macro = sum(recent) / len(recent) - sum(past) / len(past)

    ref_day = t - _b1b_dt.timedelta(days=P["th_micro_days"])
    ref = series.get(ref_day.isoformat())
    if ref is None:
        earlier = [d for d in sorted(series) if d <= ref_day.isoformat()]
        if earlier:
            ref = series[earlier[-1]]
            warnings.append("Trend a 72 h calcolato dal %s (manca il %s)." % (earlier[-1], ref_day.isoformat()))
        else:
            ref = series[t.isoformat()]
            warnings.append("Nessun giorno 3 giorni prima del richiesto: trend a 72 h posto a 0.")
    micro = series[t.isoformat()] - ref
    return _b1b_round(macro), _b1b_round(micro), warnings


# ==============================================================================
# FUNZIONE PRINCIPALE
# ==============================================================================
def compute_water_temperature(weather, spot_morphology) -> dict:
    """
    weather: dizionario della parte A (days, dates, target_date, low_confidence). spot_morphology: chiave di SPOT_TYPES.
    -> dizionario con temperatura giornaliera, curva oraria, trend e diagnostica (vedi `return`).
    Solleva ValueError se manca il giorno richiesto con 24 ore o se la storia è più corta di 14 giorni.
    """
    P = PARAMS
    warnings = []
    if not isinstance(weather, dict):
        raise ValueError("Dati meteo assenti: serve il dizionario prodotto da load_weather_series.")
    days = weather.get("days") if isinstance(weather.get("days"), dict) else {}
    target = str(weather.get("target_date") or "")
    target_rows = days.get(target)
    if not isinstance(target_rows, list) or len(target_rows) != 24:
        raise ValueError("Il giorno richiesto %r non ha 24 ore nei dati meteo." % (target or None,))
    spot_key, spot = _b1b_resolve_spot(spot_morphology, warnings)

    dates = weather.get("dates") if isinstance(weather.get("dates"), (list, tuple)) else sorted(days)
    sim_dates = [str(d) for d in sorted(set(map(str, dates)) | {target})
                 if str(d) <= target and isinstance(days.get(str(d)), list) and days.get(str(d))]
    history = [d for d in sim_dates if d < target]
    if len(history) < P["th_history_min_days"]:
        raise ValueError("Storia meteo troppo corta per il modello termico: %d giorni prima del %s, ne servono "
                         "almeno %d." % (len(history), target, P["th_history_min_days"]))

    rows, filled = _b1b_build_forcing(days, sim_dates, warnings)
    first_target = next((i for i, r in enumerate(rows) if r["date"] == target), None)
    if first_target is None or first_target == 0:
        raise ValueError("Ore del giorno richiesto %s non trovate nella serie." % target)

    # --- seme: media dell'aria dei primi 7 giorni -------------------------------------------------
    seed_dates = set(sim_dates[:P["th_seed_days"]])
    seed_air = _b1b_mean(r["air_temp"] for r in rows if r["date"] in seed_dates)
    seed = max(P["th_floor_c"], seed_air if seed_air is not None else P["th_default_temp_c"])

    # --- simulazione giornaliera (h_eff) fino al giorno richiesto incluso --------------------------------
    bulk, _ = _b1b_integrate(rows, seed, lambda tw: effective_depth(spot, tw), warnings=warnings)
    daily = {}
    for d in sim_dates:
        vals = [bulk[i] for i, r in enumerate(rows) if r["date"] == d]
        if vals:
            daily[d] = sum(vals) / len(vals)
    base = daily[target]
    h_target = _b1b_mean(effective_depth(spot, bulk[i]) for i in range(first_target, len(rows)))

    # --- curva oraria del giorno richiesto (h_diurnal) ----------------------------------------------
    start_tw = bulk[first_target - 1]
    h_diurnal = _b1b_num(spot.get("h_diurnal_m"), 2.6)
    flux_log = {}
    hourly, seconds = _b1b_integrate(rows[first_target:], start_tw, lambda tw: h_diurnal,
                                     prev=rows[first_target - 1], flux_log=flux_log, warnings=warnings)
    max_swing = _b1b_num(spot.get("max_swing"), 2.1)
    raw_swing = max(hourly) - min(hourly)
    clipped = raw_swing > max_swing > 0
    if clipped:
        ratio = max_swing / raw_swing
        hourly = [max(P["th_floor_c"], start_tw + (t - start_tw) * ratio) for t in hourly]
        warnings.append("Escursione oraria calcolata %.2f °C oltre il limite di sicurezza %.2f °C: curva compressa."
                        % (raw_swing, max_swing))
    flux_means = {k: _b1b_round(v / seconds) for k, v in flux_log.items()} if seconds > 0 else {}

    # --- trend, ghiaccio, affidabilità ----------------------------------------------------------------
    macro, micro, trend_warn = compute_water_trends(daily, target)
    warnings.extend(trend_warn)
    ice_risk = base <= P["th_ice_risk_c"] or min(hourly) <= P["th_ice_risk_c"]

    low = bool(weather.get("low_confidence", False))
    if len(history) < P["th_spinup_days"]:
        low = True
        warnings.append("Solo %d giorni di storia: la temperatura dipende ancora dal valore iniziale (media "
                        "dell'aria dei primi %d giorni)." % (len(history), P["th_seed_days"]))
    gaps_in_dates = [d for a, d in zip(sim_dates, sim_dates[1:]) if _b1b_day_diff(a, d) != 1]
    if gaps_in_dates:
        low = True
        warnings.append("Date non consecutive nella storia (prima di: %s)." % ", ".join(gaps_in_dates))

    return {
        "spot": spot_key,
        "target_date": target,
        "base_water_temp": _b1b_round(base),
        "water_temp_start": _b1b_round(start_tw),
        "hourly_water_temps": [_b1b_round(t) for t in hourly],
        "hourly_mean_temp": _b1b_round(sum(hourly) / len(hourly)),
        "daily_water": {d: _b1b_round(v) for d, v in daily.items()},
        "macro_trend_14d": macro,
        "micro_trend_72h": micro,
        "ice_risk": bool(ice_risk),
        "swing": _b1b_round(max(hourly) - min(hourly)),
        "swing_raw": _b1b_round(raw_swing),
        "swing_clipped": bool(clipped),
        "max_swing": max_swing,
        "h_eff_target_m": _b1b_round(h_target),
        "h_diurnal_m": h_diurnal,
        "seed_temp": _b1b_round(seed),
        "target_hours_integrated": _b1b_round(seconds / 3600.0),
        "target_flux_means": flux_means,
        "forcing_filled": filled,
        "history_days": len(history),
        "low_confidence": low,
        "warnings": warnings,
    }


def _b1b_day_diff(a, b):
    try:
        return (_b1b_dt.date.fromisoformat(b) - _b1b_dt.date.fromisoformat(a)).days
    except ValueError:
        return 0


# ==============================================================================
# PARTE C — OSSIGENO DISCIOLTO
# ==============================================================================
def do_saturation_mg_l(t_c, pressure_hpa=None):
    """
    Ossigeno disciolto a saturazione in acqua dolce, mg/L, alla temperatura t_c (°C) e alla pressione
    atmosferica pressure_hpa (hPa al suolo; default 1 atm). Benson & Krause (1984) con la correzione di
    pressione adottata da USGS (TM 2011.03). None se la temperatura non è un numero.
    """
    P = PARAMS
    t = _b1b_num(t_c)
    if t is None:
        return None
    lo, hi = P["ox_t_range_c"]
    t = max(lo, min(hi, t))
    tk = t + 273.15
    c0, c1, c2, c3, c4 = P["ox_bk_coeffs"]
    c_star = _b1_math.exp(c0 + c1 / tk + c2 / tk ** 2 + c3 / tk ** 3 + c4 / tk ** 4)
    p_hpa = _b1b_num(pressure_hpa)
    p_atm = (p_hpa if p_hpa is not None and 300.0 <= p_hpa <= 1100.0 else P["ox_hpa_per_atm"]) / P["ox_hpa_per_atm"]
    a, b, c = P["ox_pwv_coeffs"]
    u = _b1_math.exp(a + b / tk + c / tk ** 2)
    ta, tb, tc = P["ox_theta_coeffs"]
    theta = ta + tb * t + tc * t * t
    fp = ((p_atm - u) * (1.0 - theta * p_atm)) / ((1.0 - u) * (1.0 - theta))
    return c_star * max(0.0, fp)


def _b1c_diel_signal(radiations):
    """
    Andamento del bilancio fotosintesi - respirazione nell'arco del giorno, da -1 a +1: somma cumulata della
    radiazione meno la sua media giornaliera. -1 dopo l'alba (fine della respirazione notturna), +1 nel tardo
    pomeriggio, 0 a fine giornata. Tutto 0 se la radiazione è nulla.
    """
    vals = [max(0.0, _b1b_num(r, 0.0)) for r in radiations]
    if not vals:
        return []
    mean = sum(vals) / len(vals)
    if mean <= 0.0:
        return [0.0] * len(vals)
    cum, run = [], 0.0
    for v in vals:
        run += v - mean
        cum.append(run)
    hi, lo = max(cum), min(cum)
    out = []
    for c in cum:
        if c > 0.0 and hi > 0.0:
            out.append(c / hi)
        elif c < 0.0 and lo < 0.0:
            out.append(c / -lo)
        else:
            out.append(0.0)
    return out


def do_saturation_factor_series(spot_key, water_temps, radiations, winds):
    """
    f_sat ora per ora (ossigeno reale / ossigeno a saturazione) [EURISTICA dichiarata]:
    f = 1 + A_giorno * s  se s >= 0,   f = 1 + A_notte * s  se s < 0,   s = _b1c_diel_signal(radiazione)
    A_giorno = sovrasaturazione massima x luce x attività biologica x vento
    A_notte  = deficit massimo x attività biologica x vento
    """
    P = PARAMS
    up_max, down_max = P["ox_diel_amplitude"].get(
        spot_key, P["ox_diel_amplitude"][PARAMS["th_default_spot"]])
    temps = [_b1b_num(t) for t in water_temps if _b1b_num(t) is not None]
    wind_vals = [max(0.0, _b1b_num(w, 0.0)) for w in winds]
    rads = [max(0.0, _b1b_num(r, 0.0)) for r in radiations]
    t_mean = sum(temps) / len(temps) if temps else P["ox_bio_t_low_c"]
    w_mean = sum(wind_vals) / len(wind_vals) if wind_vals else 0.0
    r_mean = sum(rads) / len(rads) if rads else 0.0
    span = P["ox_bio_t_high_c"] - P["ox_bio_t_low_c"]
    g_t = max(0.0, min(P["ox_bio_t_cap"], (t_mean - P["ox_bio_t_low_c"]) / span)) if span > 0 else 1.0
    w_u = 1.0 / (1.0 + (w_mean / P["ox_wind_ref_kmh"]) ** 2)
    light = max(0.0, min(1.0, r_mean / P["ox_light_ref_wm2"]))
    up = up_max * light * g_t * w_u
    down = down_max * g_t * w_u
    return [1.0 + (up * s if s >= 0.0 else down * s) for s in _b1c_diel_signal(rads)]


# ==============================================================================
# PARTE C — STATO BIOLOGICO
# ==============================================================================
def classify_biological_state(t, macro_14d, micro_72h, do_mg_l=None) -> str:
    """
    Stato biologico del persico trota in una frase, dalla temperatura dell'acqua t (°C), dai trend
    (macro_14d, micro_72h in °C) e, se c'è, dall'ossigeno disciolto (mg/L, di solito il minimo del giorno).
    Il Blocco 2 può richiamarla con la temperatura della sonda. Soglie in PARAMS (bio_*).
    """
    P = PARAMS
    tv = _b1b_num(t)
    if tv is None:
        return "Stato non determinato: temperatura dell'acqua non disponibile."
    do_v = _b1b_num(do_mg_l)
    t_txt = "%.1f °C" % tv
    do_txt = ("%.1f mg/L" % do_v) if do_v is not None else ""

    if do_v is not None and do_v < P["bio_do_stress_mg_l"]:
        base = "Stress da ossigeno basso (%s, acqua %s): attività molto limitata, pesci verso acqua più ossigenata" % (
            do_txt, t_txt)
    elif tv < P["bio_t_minimal_c"]:
        base = "Attività minima (acqua %s): metabolismo molto basso, pesci poco mobili e vicini al fondo" % t_txt
    elif tv < P["bio_t_reduced_c"]:
        base = "Attività ridotta (acqua %s): alimentazione lenta, più probabile nelle ore più calde" % t_txt
    elif tv < P["bio_t_growing_c"]:
        base = "Attività in crescita (acqua %s): il metabolismo aumenta con la temperatura" % t_txt
    elif tv <= P["bio_t_hot_c"]:
        if do_v is not None and do_v < P["bio_do_low_mg_l"]:
            base = "Temperatura favorevole (acqua %s) ma ossigeno basso (%s): attività limitata" % (t_txt, do_txt)
        else:
            base = "Attività ottimale (acqua %s): temperatura nell'intervallo più favorevole" % t_txt
    elif tv <= P["bio_t_stress_c"]:
        base = "Caldo elevato (acqua %s): possibile stress, attività concentrata nelle ore più fresche" % t_txt
    else:
        base = "Stress termico (acqua %s): attività ridotta, pesci in acqua più fresca o profonda" % t_txt

    notes = []
    # Ossigeno tra 4 e 5 mg/L: la frase base lo cita solo tra 20 e 30 °C; a ogni altra temperatura va in nota
    # (a 30-32 °C, con la domanda di ossigeno più alta, è anche più rilevante).
    if do_v is not None and P["bio_do_stress_mg_l"] <= do_v < P["bio_do_low_mg_l"] and "ossigeno" not in base:
        notes.append("ossigeno basso (%s): attività limitata" % do_txt)
    micro = _b1b_num(micro_72h, 0.0)
    macro = _b1b_num(macro_14d, 0.0)
    if micro <= -P["bio_micro_note_c"]:
        notes.append("calo di %.1f °C in 72 h" % -micro)
    elif micro >= P["bio_micro_note_c"]:
        notes.append("aumento di %.1f °C in 72 h" % micro)
    if macro <= -P["bio_macro_note_c"]:
        notes.append("acqua in raffreddamento nelle ultime 2 settimane (%+.1f °C)" % macro)
    elif macro >= P["bio_macro_note_c"]:
        notes.append("acqua in riscaldamento nelle ultime 2 settimane (%+.1f °C)" % macro)
    return base + ("; " + "; ".join(notes) if notes else "") + "."


# ==============================================================================
# PARTE C — ASSEMBLAGGIO DELLA SERIE PER I BLOCCHI 2-5
# ==============================================================================
def _b1c_local_today(data, now_utc=None):
    """Data di oggi nel fuso della località (campo "timezone" della risposta; ripiego: offset fisso, poi UTC)."""
    now = now_utc if isinstance(now_utc, _b1_dt.datetime) else _b1_dt.datetime.now(_b1_dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_b1_dt.timezone.utc)
    data = data if isinstance(data, dict) else {}
    name = str(data.get("timezone") or "").strip()
    if name:
        try:
            return now.astimezone(_b1_zoneinfo.ZoneInfo(name)).date()
        except (_b1_zoneinfo.ZoneInfoNotFoundError, ValueError, TypeError, OSError):
            pass
    off = max(-14 * 3600, min(14 * 3600, _b1_int(data.get("utc_offset_seconds"), 0)))
    return (now + _b1_dt.timedelta(seconds=off)).date()


def _b1c_round(x, nd, default=0.0):
    v = _b1b_num(x)
    return round(v if v is not None else default, nd)


def build_thermal_series(data, spot_morphology, target_date=None, day_offset=0, now_utc=None, history_wanted=None):
    """
    Funzione pura: dalla risposta JSON di Open-Meteo al dizionario del Blocco 1 (vedi testa del file).
    target_date "AAAA-MM-GG" ha la precedenza; altrimenti oggi nel fuso del luogo + day_offset.
    Solleva ValueError se il giorno richiesto non ha 24 ore valide o la storia è più corta di 14 giorni.
    """
    P = PARAMS
    warnings = []
    if target_date:
        target = _b1_parse_date(target_date)
    else:
        target = _b1c_local_today(data, now_utc) + _b1_dt.timedelta(days=_b1_int(day_offset, 0))
    t_str = target.isoformat()

    weather = parse_weather_payload(data, t_str, history_wanted)
    thermal = compute_water_temperature(weather, spot_morphology)
    spot_key = thermal["spot"]
    rows = weather["days"][t_str]
    water = thermal["hourly_water_temps"]
    if len(rows) != 24 or len(water) != 24:
        raise ValueError("Serie oraria del giorno %s incompleta: %d ore meteo, %d ore d'acqua." % (
            t_str, len(rows), len(water)))

    # --- ossigeno ------------------------------------------------------------------------------------
    f_sat = do_saturation_factor_series(spot_key, water, [r.get("radiation") for r in rows],
                                        [r.get("wind") for r in rows])
    hourly, missing_delta = [], 0
    for i, r in enumerate(rows):
        ps = _b1b_num(r.get("surface_pressure"))
        sat = do_saturation_mg_l(water[i], ps)
        sat = sat if sat is not None else do_saturation_mg_l(thermal["base_water_temp"], ps)
        actual = sat * f_sat[i]
        delta, trend = _b1b_num(r.get("pressure_delta")), _b1b_num(r.get("pressure_trend_12h"))
        if delta is None or trend is None:
            missing_delta += 1
        hourly.append({
            "hour": int(_b1_int(r.get("hour"), i)),
            "time_label": str(r.get("time_label") or "%02d:00" % i),
            "date_str": str(r.get("date_str") or t_str),
            "air_temp": _b1c_round(r.get("air_temp"), 1),
            "water_temp": _b1c_round(water[i], 1),
            "pressure": _b1c_round(r.get("pressure_msl"), 1, P["th_default_pressure_hpa"]),
            "pressure_delta": _b1c_round(delta, 2),
            "pressure_trend_12h": _b1c_round(trend, 2),
            "clouds": int(round(_b1b_num(r.get("clouds"), P["th_default_clouds"]))),
            "wind": _b1c_round(r.get("wind"), 1),
            "radiation": int(round(_b1b_num(r.get("radiation"), 0.0))),
            "do_saturation_index": round(min(1.0, max(0.0, f_sat[i])), 3),
            "surface_pressure": _b1c_round(ps, 1, P["th_default_pressure_hpa"]),
            "humidity": _b1c_round(r.get("humidity"), 1, P["th_default_rh"]),
            "do_sat_mg_l": round(sat, 2),
            "do_actual_mg_l": round(actual, 2),
        })
    if missing_delta:
        warnings.append("Variazione di pressione assente in %d ore: posta a 0." % missing_delta)

    # --- aria media 7 giorni, quota --------------------------------------------------------------------
    air_days = []
    for k in range(P["out_mean_air_days"]):
        d = (target - _b1_dt.timedelta(days=k)).isoformat()
        vals = [_b1b_num(x.get("air_temp")) for x in weather["days"].get(d, [])]
        vals = [v for v in vals if v is not None]
        if vals:
            air_days.append(sum(vals) / len(vals))
    mean_7d_air = round(sum(air_days) / len(air_days), 1) if air_days else _b1c_round(hourly[0]["air_temp"], 1)

    elevation = weather.get("elevation_m")
    elevation_source = "open-meteo"
    if elevation is None:
        ps_vals = [h["surface_pressure"] for h in hourly]
        pm_vals = [h["pressure"] for h in hourly]
        ratio = (sum(ps_vals) / 24.0) / (sum(pm_vals) / 24.0) if sum(pm_vals) > 0 else 1.0
        elevation = P["out_baro_height_m"] * (1.0 - min(1.2, max(0.4, ratio)) ** P["out_baro_exp"])
        elevation_source = "stimata dalla pressione"

    # --- trend e stato biologico ------------------------------------------------------------------------
    macro = _b1c_round(thermal["macro_trend_14d"], 2)
    micro = _b1c_round(thermal["micro_trend_72h"], 2)
    base = _b1c_round(thermal["base_water_temp"], 1)
    do_min = min(h["do_actual_mg_l"] for h in hourly)
    state = classify_biological_state(base, macro, micro, do_min)

    low = bool(thermal.get("low_confidence")) or bool(missing_delta)
    all_warnings = list(weather.get("warnings") or [])
    for wmsg in list(thermal.get("warnings") or []) + warnings:
        if wmsg not in all_warnings:
            all_warnings.append(wmsg)

    return {
        "base_water_temp": base,
        "macro_trend_14d": macro,
        "micro_trend_72h": micro,
        "biological_state": state,
        "hourly": hourly,
        "thermal_trend_3d": micro,
        "mean_7d_air": mean_7d_air,
        "data_gaps": int(weather.get("data_gaps") or 0),
        "ice_risk": bool(thermal.get("ice_risk")),
        "low_confidence": low,
        "elevation_m": round(elevation, 0),
        # diagnostica
        "elevation_source": elevation_source,
        "target_date": t_str,
        "timezone": weather.get("timezone"),
        "spot": spot_key,
        "history_days": weather.get("history_days"),
        "do_min_mg_l": round(do_min, 2),
        "hourly_mean_water_temp": thermal.get("hourly_mean_temp"),
        "swing_clipped": bool(thermal.get("swing_clipped")),
        "warnings": all_warnings,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_thermal_and_weather_series(lat: float, lon: float, day_offset: int, spot_morphology: str,
                                     target_date: str | None = None) -> dict:
    """
    Scarica da Open-Meteo e restituisce la serie del giorno richiesto (contratto in testa al file).
    target_date "AAAA-MM-GG" ha la precedenza su day_offset. Solleva solo requests.* o ValueError.
    """
    try:
        offset = _b1_int(day_offset, 0)
        if target_date:
            target = _b1_parse_date(target_date)
            request_target = target
        else:
            target = None
            request_target = _b1_today(None) + _b1_dt.timedelta(days=offset)
        params, meta = build_weather_request(lat, lon, request_target.isoformat(), PARAMS["history_days_target"])
        data = _b1_fetch(params)
        out = build_thermal_series(data, spot_morphology, target.isoformat() if target else None, offset,
                                   history_wanted=meta["history_wanted"])
        out["request"] = {"past_days": params["past_days"], "forecast_days": params["forecast_days"]}
        return out
    except ValueError:
        raise
    except (KeyError, TypeError, IndexError, AttributeError, ArithmeticError) as exc:
        raise ValueError("Errore interno del Blocco 1 durante l'elaborazione dei dati (%s: %s)."
                         % (type(exc).__name__, exc)) from exc


# >>> BLOCCO: Blocco2-BF-V2.py <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ==============================================================================
# BASS ENGINE — BLOCCO 2 (v2): MOTORE BIOLOGICO (BAI, TROPHY, PICCHI, STRIKE ZONE)
# ==============================================================================
_b0_magia = """
Blocco 2 dell'app Streamlit "Bass Engine": dalla serie oraria del Blocco 1 v2 agli indici orari che leggono i
Blocchi 3, 4 e 5. File unico, ottenuto da quattro parti (ognuna con i suoi test):
    PARTE A  base biologica: temperatura -> consumo (modello Wisconsin, Rice et al. 1983), limite da ossigeno
             (criteri EPA 1986), variazione termica, torbidità;
    PARTE B  fattori ambientali orari: luce e fotoperiodo (con le nuvole), vento, pressione, luna, indice ambientale;
    PARTE C  Trophy (pesci > 2 kg), scala comune degli indici, ora migliore, strike zone;
    PARTE D  simulazione delle 24 ore e classe pubblica ProTourBiologicalEngine.

INTERFACCIA PUBBLICA
    ProTourBiologicalEngine.run_pro_simulation(series_data, astro, torbidita, manual_water_temp=None,
                                               water_level="Stabile", max_depth_m=None) -> dict
    Contratto completo nella testa della parte D. Funzioni pure del modulo (per test e per il Blocco 3):
    consumption_temperature_factor, oxygen_limit, trend_multiplier, turbidity_factor, score_light, score_wind,
    score_pressure, moon_factor, environment_index, index_scale, prespawn_bonus, trophy_index, pick_peak,
    estimate_strike_zone.

USO NELL'APP
    Incollare dopo il Blocco 1 v2 e prima dei Blocchi 3-5. Dal Blocco 1 v2 (se presente nello stesso file) usa
    SPOT_TYPES (profondità massima dello spot), do_saturation_mg_l e classify_biological_state (solo con la sonda);
    senza Blocco 1 funziona lo stesso e lo segnala in "warnings". Nomi interni con prefisso _b2_, costanti in
    B2_PARAMS (non PARAMS, che è del Blocco 1 v2).

COSTANTI: tutte in B2_PARAMS, con valore, unità, fonte e tipo ([MISURATO] valore documentato da una fonte citata;
[INFERENZA] dedotto; [EURISTICA] scelta di progetto; "DA VERIFICARE" = non controllato sul testo originale).
Elenco delle modifiche rispetto al Blocco 2 originale: CHANGELOG_Blocco2.md. Gli indici sono relativi, non
probabilità.

Requisiti: Python 3.10+, solo libreria standard.
"""
import math as _b2_math
import re as _b2_re


# ##############################################################################
# PARTE A — BASE BIOLOGICA
# ##############################################################################
# Parte A del nuovo Blocco 2: le quattro funzioni pure su cui poggiano gli indici di attività (BAI) e
# Trophy. Nessuna rete, nessuno stato, nessuna dipendenza oltre alla libreria standard.
#
# FUNZIONI PUBBLICHE
#     consumption_temperature_factor(t, cto=None, ctm=None, cq=None) -> float
#         Effetto della temperatura dell'acqua sul consumo massimo, 0-1 (1 all'ottimo). Funzione di consumo
#         "eq. 2" del modello bioenergetico Wisconsin (Kitchell et al. 1977) con i parametri del largemouth
#         bass di Rice et al. (1983). cto/ctm/cq facoltativi: la parte C li usa per il Trophy.
#     oxygen_limit(do_mg_l, shift=0.0, do_sat_mg_l=None, do_saturation_index=None) -> float
#         Riduzione dell'attività per ossigeno basso, 0.1-1. Rampa in mg/L ancorata ai criteri EPA 1986.
#         `shift` alza tutte le soglie (la parte C usa +1 mg/L per i pesci grandi).
#     trend_multiplier(t, micro_72h, macro_14d=0.0) -> float
#         Effetto della variazione termica delle ultime 72 h, 0.80-1.15.
#     turbidity_factor(label) -> (float, str)
#         Moltiplicatore della torbidità e etichetta da mostrare ("Velata (Stima)" se l'utente non l'ha indicata).
#
# COSA LEGGE DAL BLOCCO 1 v2 (righe orarie)
#     water_temp (°C), do_actual_mg_l, do_sat_mg_l, do_saturation_index (rapporto reale 0.75-1.00: le vecchie
#     soglie 0.55-0.68 sull'indice non hanno più senso e qui non compaiono), micro_72h / macro_14d dalla serie.
#
# REGOLE DI INTEGRAZIONE
#     * Tutte le costanti stanno in B2_PARAMS (non in PARAMS, che è il dizionario globale del Blocco 1 v2: nel file
#       unico dell'app verrebbe sovrascritto). Nomi interni con prefisso _b2_.
#     * Ogni funzione rappresenta UN fattore: temperatura, ossigeno, variazione termica, torbidità. La parte C li
#       moltiplica una sola volta ciascuno.
#     * Ingressi mancanti o non numerici (None, testo, NaN, inf, bool) non sollevano eccezioni: valori di riserva
#       dichiarati in ogni funzione.
#     * I risultati non sono arrotondati qui: l'arrotondamento si fa una volta sola nell'uscita (parte D).
#
# LIMITI NOTI
#     * La temperatura del Blocco 1 v2 ha un bias caldo (circa +2.6 °C d'estate, +2-3 °C in primavera). Non viene
#       corretto qui. Dove la curva di consumo è ripida (10-22 °C) il bias pesa molto: 15.0 -> 17.6 °C fa salire il
#       fattore da 0.37 a 0.50 (+37 %). Vicino all'ottimo (25-30 °C) pesa poco.
#     * Gli indici restano relativi (0-100), non probabilità di cattura.
#
# Etichette delle fonti: [MISURATO] valore documentato da una fonte citata; [INFERENZA] dedotto da fatti
# documentati; [EURISTICA] scelta di progetto. "DA VERIFICARE" = non controllato sul testo originale.
# Fonti consultate il 29/10/2026 per questa parte: elencate nella consegna della parte A.

# ==============================================================================
# PARAMETRI — tutte le costanti della parte A del Blocco 2
# ==============================================================================
B2_PARAMS = {
    # --- Consumo in funzione della temperatura (modello bioenergetico Wisconsin, "eq. 2") -----------------
    # f(T) = V^X * exp(X * (1 - V)),  V = (CTM - T) / (CTM - CTO)
    # Z = ln(CQ) * (CTM - CTO);  Y = ln(CQ) * (CTM - CTO + 2);  X = Z^2 * (1 + sqrt(1 + 40 / Y))^2 / 400
    # Forma della funzione e di V: Kitchell J.F., Stewart D.J., Weininger D. (1977), J. Fish. Res. Board Can.
    # 34:1922-1935; confermata dalla documentazione del pacchetto R fb4package (Fish Bioenergetics 4.0).
    # Il calcolo di X da CQ non compare in quella documentazione: formula del progetto, DA VERIFICARE sul
    # manuale Fish Bioenergetics 3.0 (Hanson et al. 1997). Con i parametri sotto dà i valori di riferimento
    # del progetto (0.088 a 5 °C ... 0.915 a 30 °C).
    #
    # Temperatura ottima per il consumo, °C. Rice J.A., Breck J.E., Bartell S.M., Kitchell J.F. (1983),
    # Environmental Biology of Fishes 9(3-4):263-275, doi:10.1007/BF00692375 (pagine da due bibliografie
    # concordi; il prompt del progetto riportava 9:277-288). L'ottimo di ~27.5 °C è attribuito a Rice et al.
    # 1983 da un preprint bioRxiv del 2026 (non revisionato); il parametro non è stato letto sull'originale.
    # [MISURATO, tramite fonte secondaria]
    "cons_cto_c": 27.5,
    # Temperatura massima oltre la quale il consumo è nullo, °C. Valore del progetto per Rice et al. 1983.
    # [MISURATO, DA VERIFICARE sull'originale]
    "cons_ctm_c": 37.0,
    # Coefficiente di dipendenza dalla temperatura (pendenza alle basse temperature), adimensionale.
    # Moore C.M., Ney J.J., Neves R.J. (1993), Parameter valuation of bioenergetics model for striped bass,
    # VCFWRU-SG-93-02, Virginia Tech, lo indica come "the temperature dependence coefficient used by Rice et al.
    # 1983 for largemouth bass". [MISURATO, tramite fonte secondaria]
    "cons_cq": 2.65,
    # Costanti strutturali dell'equazione (+2 °C in Y, 40, 400). [MISURATO: forma dell'equazione, DA VERIFICARE]
    "cons_eq2_y_offset_c": 2.0,
    "cons_eq2_k": 40.0,
    "cons_eq2_div": 400.0,
    # Valore minimo del fattore per T < CTM, adimensionale: attività residua anche in acqua molto fredda.
    # Sotto ~6 °C il largemouth si alimenta di rado ma non smette del tutto (Wright R.A. et al. 1999, Trans. Am.
    # Fish. Soc. 128:603-612, testo letto dall'audit del 28/10/2026); la curva vale 0.075 a 4 °C e 0.039 a 0 °C.
    # Il valore esatto è una scelta. [EURISTICA]
    "cons_min_factor": 0.05,
    # Ampiezza minima CTM - CTO accettata per i parametri facoltativi, °C: sotto, la curva degenera e si usano
    # i valori di default. [EURISTICA]
    "cons_min_span_c": 0.5,

    # --- Limite da ossigeno disciolto (mg/L) --------------------------------------------------------------
    # Rampa a tratti lineari [EURISTICA ancorata ai criteri]: 1.0 da 5 mg/L in su; da 1.0 a 0.3 tra 5 e 3 mg/L;
    # da 0.3 a 0.1 tra 3 e 2 mg/L (raccordo per evitare uno scalino); 0.1 sotto 2 mg/L.
    # Criteri EPA 1986 per acque calde, "altri stadi": media a 30 giorni 5.5, media a 7 giorni dei minimi 4.0,
    # minimo di 1 giorno 3.0 mg/L; stadi giovanili: media a 7 giorni 6.0, minimo 5.0 mg/L. US EPA, Ambient Water
    # Quality Criteria for Dissolved Oxygen (Freshwater), EPA 440/5-86-003 (aprile 1986); tabella letta nella
    # scheda EPA "Parameter factsheet: dissolved oxygen" (2021). [MISURATO i criteri; la rampa è EURISTICA]
    # Con queste soglie 4 mg/L (media a 7 giorni dei minimi) dà 0.65.
    "ox_full_mg_l": 5.0,        # da qui in su nessuna riduzione
    "ox_mid_mg_l": 3.0,         # minimo di 1 giorno EPA per gli adulti
    "ox_low_mg_l": 2.0,         # sotto: riduzione massima
    "ox_full_factor": 1.0,
    "ox_mid_factor": 0.3,
    "ox_low_factor": 0.1,
    # Ossigeno ignoto (né mg/L né saturazione x indice): nessuna riduzione. [EURISTICA]
    "ox_unknown_factor": 1.0,
    # Spostamento massimo accettato delle soglie, mg/L (protegge da valori assurdi). [EURISTICA]
    "ox_shift_range_mg_l": (-3.0, 5.0),

    # --- Variazione termica delle ultime 72 ore ------------------------------------------------------------
    # Sotto 26 °C:  m = 1 + 0.15 * tanh(micro_72h / 1.5)   (riscaldamento favorevole, raffreddamento sfavorevole)
    # Sopra 30 °C:  m = 1 - 0.10 * tanh(max(0, micro_72h) / 1.5)   (oltre l'ottimo un ulteriore riscaldamento pesa)
    # Tra 26 e 30 °C: interpolazione lineare in temperatura tra le due espressioni (continua; salto massimo
    # ~0.006 per 0.1 °C). Limite finale [0.80, 1.15].
    # Nessuno studio quantifica l'effetto dei fronti sul largemouth; l'idea che un raffreddamento rapido riduca
    # l'alimentazione è un'inferenza ragionevole (audit 28/10/2026, B2-4). [EURISTICA]
    "trend_cold_below_c": 26.0,
    "trend_hot_above_c": 30.0,
    "trend_cold_amp": 0.15,
    "trend_hot_amp": 0.10,
    "trend_scale_c": 1.5,
    "trend_min": 0.80,
    "trend_max": 1.15,
    # Valore se manca la temperatura (non si sa quale regime applicare): nessun effetto. [EURISTICA]
    "trend_unknown_factor": 1.0,

    # --- Torbidità -------------------------------------------------------------------------------------------
    # Moltiplicatore sul consumo per categoria [EURISTICA]: via di mezzo tra laboratorio e campo.
    # Shoup D.E., Lane W.D. (2015), North American Journal of Fisheries Management 35(5):913-924,
    # doi:10.1080/02755947.2015.1067260 (testo letto il 29/10/2026): in laboratorio il consumo giornaliero passa da
    # ~3 a ~0.5 bluegill (-83 %) e da ~2 a ~0.6 gizzard shad (-70 %) tra 0-3 e oltre 25 NTU; in campo nessuna
    # correlazione tra torbidità e consumo (Secchi 150-860 mm), ma la dieta cambia (più pesci, meno gamberi).
    # Fangosa 0.60 = -40 %: metà strada circa tra -80 % e 0 %. [MISURATO i dati dello studio; i fattori sono EURISTICA]
    "turb_factors": {
        "Limpida": 1.00,
        "Velata": 0.95,
        "Torbida": 0.80,
        "Fangosa": 0.60,
    },
    # Intervalli NTU indicativi di ogni categoria, solo descrittivi (nessuna misura entra nel calcolo). [EURISTICA]
    "turb_ntu_ranges": {
        "Limpida": (0.0, 5.0),
        "Velata": (5.0, 15.0),
        "Torbida": (15.0, 40.0),
        "Fangosa": (40.0, None),
    },
    # Categoria usata quando l'utente non indica la torbidità o passa un valore sconosciuto, e suffisso
    # dell'etichetta in quel caso (identico al Blocco 2 originale, letto dai Blocchi 3 e 5). [EURISTICA]
    "turb_default": "Velata",
    "turb_estimate_suffix": " (Stima)",
}


# ==============================================================================
# UTILITÀ
# ==============================================================================
def _b2_num(value, default=None):
    """Numero finito come float, altrimenti `default` (None, bool, testo non numerico, NaN, inf, altri tipi)."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        x = float(value)
    elif isinstance(value, str):
        try:
            x = float(value.strip().replace(",", "."))
        except ValueError:
            return default
    else:
        return default
    return x if _b2_math.isfinite(x) else default


def _b2_clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def _b2_lerp(x, x0, y0, x1, y1):
    """Interpolazione lineare tra (x0, y0) e (x1, y1), con x già dentro l'intervallo."""
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


# ==============================================================================
# 1. TEMPERATURA -> CONSUMO
# ==============================================================================
def _b2_consumption_params(cto, ctm, cq):
    """Parametri effettivi: quelli passati se validi, altrimenti i default di B2_PARAMS (tutti insieme)."""
    P = B2_PARAMS
    d_cto, d_ctm, d_cq = P["cons_cto_c"], P["cons_ctm_c"], P["cons_cq"]
    v_cto = _b2_num(cto, d_cto)
    v_ctm = _b2_num(ctm, d_ctm)
    v_cq = _b2_num(cq, d_cq)
    if (v_ctm - v_cto) < P["cons_min_span_c"] or v_cq <= 1.0:
        return d_cto, d_ctm, d_cq
    return v_cto, v_ctm, v_cq


def consumption_temperature_factor(t, cto=None, ctm=None, cq=None) -> float:
    """
    Effetto della temperatura dell'acqua t (°C) sul consumo massimo, 0-1.
    Funzione di consumo "eq. 2" del modello Wisconsin (Kitchell et al. 1977) con i parametri del largemouth
    bass (Rice et al. 1983): vale 1 a CTO = 27.5 °C, 0 da CTM = 37 °C in su, mai sotto 0.05 per T < CTM.

    cto, ctm, cq: facoltativi (°C, °C, adimensionale). Se la combinazione non è valida (CTM - CTO < 0.5 °C,
    oppure CQ <= 1, dove il logaritmo non è positivo) si usano tutti e tre i valori di default.
    Temperatura non numerica: restituisce il minimo (0.05), scelta prudente che non inventa attività.
    """
    P = B2_PARAMS
    floor = P["cons_min_factor"]
    tv = _b2_num(t)
    if tv is None:
        return floor
    cto_v, ctm_v, cq_v = _b2_consumption_params(cto, ctm, cq)
    if tv >= ctm_v:
        return 0.0
    ln_cq = _b2_math.log(cq_v)
    z = ln_cq * (ctm_v - cto_v)
    y = ln_cq * (ctm_v - cto_v + P["cons_eq2_y_offset_c"])
    x = z * z * (1.0 + _b2_math.sqrt(1.0 + P["cons_eq2_k"] / y)) ** 2 / P["cons_eq2_div"]
    v = (ctm_v - tv) / (ctm_v - cto_v)          # > 0 perché tv < ctm_v
    try:
        f = (v ** x) * _b2_math.exp(x * (1.0 - v))
    except (OverflowError, ValueError):
        f = 0.0
    if not _b2_math.isfinite(f):
        f = 0.0
    return _b2_clamp(f, floor, 1.0)


# ==============================================================================
# 2. OSSIGENO DISCIOLTO -> LIMITE
# ==============================================================================
def oxygen_limit(do_mg_l, shift=0.0, do_sat_mg_l=None, do_saturation_index=None) -> float:
    """
    Riduzione dell'attività dovuta all'ossigeno disciolto, 0.1-1.
    do_mg_l: ossigeno reale, mg/L (chiave do_actual_mg_l del Blocco 1 v2).
    shift:   mg/L aggiunti a tutte le soglie (0 per il BAI; la parte C usa +1 per il Trophy).
    Se do_mg_l manca si usa do_sat_mg_l * do_saturation_index; se manca anche uno dei due, nessuna riduzione (1.0).

        DO >= 5 + shift          -> 1.0
        3 + shift .. 5 + shift   -> da 0.3 a 1.0, lineare
        2 + shift .. 3 + shift   -> da 0.1 a 0.3, lineare
        DO < 2 + shift           -> 0.1
    """
    P = B2_PARAMS
    lo_s, hi_s = P["ox_shift_range_mg_l"]
    s = _b2_clamp(_b2_num(shift, 0.0), lo_s, hi_s)

    do_v = _b2_num(do_mg_l)
    if do_v is None:
        sat = _b2_num(do_sat_mg_l)
        idx = _b2_num(do_saturation_index)
        if sat is None or idx is None:
            return P["ox_unknown_factor"]
        do_v = sat * idx
    do_v = max(0.0, do_v)

    full, mid, low = P["ox_full_mg_l"] + s, P["ox_mid_mg_l"] + s, P["ox_low_mg_l"] + s
    f_full, f_mid, f_low = P["ox_full_factor"], P["ox_mid_factor"], P["ox_low_factor"]
    if do_v >= full:
        return f_full
    if do_v >= mid:
        return _b2_lerp(do_v, mid, f_mid, full, f_full)
    if do_v >= low:
        return _b2_lerp(do_v, low, f_low, mid, f_mid)
    return f_low


# ==============================================================================
# 3. VARIAZIONE TERMICA -> MOLTIPLICATORE
# ==============================================================================
def trend_multiplier(t, micro_72h, macro_14d=0.0) -> float:
    """
    Moltiplicatore della variazione termica recente, 0.80-1.15.
    t: temperatura dell'acqua (°C) che decide il regime; micro_72h: variazione in 72 h (°C).
    macro_14d è accettato per uniformità con l'interfaccia ma NON entra nel calcolo: nessuna fonte quantifica un
    effetto separato del trend a 14 giorni sul BAI, e nella parte C lo usa il bonus pre-frega del Trophy (se
    entrasse anche qui, lo stesso segnale verrebbe contato due volte nello stesso indice).
    Ingressi mancanti: micro_72h -> 0 (nessun effetto); t -> nessun effetto (1.0).
    """
    P = B2_PARAMS
    tv = _b2_num(t)
    if tv is None:
        return P["trend_unknown_factor"]
    micro = _b2_num(micro_72h, 0.0)
    scale = P["trend_scale_c"]
    m_cold = 1.0 + P["trend_cold_amp"] * _b2_math.tanh(micro / scale)
    m_hot = 1.0 - P["trend_hot_amp"] * _b2_math.tanh(max(0.0, micro) / scale)
    lo_t, hi_t = P["trend_cold_below_c"], P["trend_hot_above_c"]
    if tv <= lo_t:
        m = m_cold
    elif tv >= hi_t:
        m = m_hot
    else:
        m = _b2_lerp(tv, lo_t, m_cold, hi_t, m_hot)
    return _b2_clamp(m, P["trend_min"], P["trend_max"])


# ==============================================================================
# 4. TORBIDITÀ -> MOLTIPLICATORE
# ==============================================================================
def turbidity_factor(label):
    """
    -> (moltiplicatore, etichetta da mostrare).
    Limpida 1.00 · Velata 0.95 · Torbida 0.80 · Fangosa 0.60 (vedi B2_PARAMS per fonte e intervalli NTU).
    Confronto senza distinzione di maiuscole e spazi. "Non specificato", "Velata (Stima)", valori sconosciuti o
    non testuali: Velata, con etichetta "Velata (Stima)" (la torbidità è assunta, non indicata dall'utente).
    """
    P = B2_PARAMS
    factors = P["turb_factors"]
    default = P["turb_default"]
    estimated_label = default + P["turb_estimate_suffix"]
    if not isinstance(label, str):
        return factors[default], estimated_label
    key = " ".join(label.split()).casefold()
    for name, value in factors.items():
        if key == name.casefold():
            return value, name
    return factors[default], estimated_label


# ##############################################################################
# PARTE B — FATTORI AMBIENTALI ORARI
# ##############################################################################
# Parte B del nuovo Blocco 2: i punteggi ambientali orari (0-1, più alto = più favorevole) e la loro combinazione.
#
# FUNZIONI PUBBLICHE (tutte pure)
#     score_light(hour, sunrise_dec, sunset_dec, clouds, water_temp, water_temp_hourly_rel=0.0, sun_status="normale")
#         -> s_sol, 0.68-0.96. Luce e fotoperiodo, con dentro l'effetto delle nuvole (unico punto in cui entrano).
#     score_wind(wind_kmh) -> s_vento, 0.72-1.00 (escursione 28 %).
#     score_pressure(pressure_msl, pressure_trend_12h) -> s_press, 0.93-1.00 (escursione 7 %). Solo barometro.
#     moon_factor(moon_illum) -> moltiplicatore 1.00-1.05 (non è un punteggio 0-1: la parte C lo applica una volta).
#     environment_index(s_sol, s_vento, s_press) -> 0-1 = s_sol * s_vento * s_press.
#
# SCALA DEI PUNTEGGI
#     Ogni punteggio è la frazione della condizione migliore per quel fattore (1 = migliore possibile; la luce arriva a
#     0.96 nell'ora più favorevole). Il Blocco 4 mostra questi valori nelle barre e nel radar.
#
# DUE SCELTE RISPETTO ALLA PRIMA STESURA (29/10/2026), entrambe per avere indici leggibili e onesti
#     1. Niente s_meteo. Era 0.5 + 0.5 * tanh(micro_72h / 2), ma micro_72h entra già nel BAI con trend_multiplier
#        (parte A): sarebbe stata contata due volte (regola 5), e sopra 30 °C i due termini avevano segno opposto
#        (riscaldamento favorevole per s_meteo, sfavorevole per trend_multiplier). La variazione termica resta solo in
#        trend_multiplier, che tiene conto della temperatura. La pressione resta in score_pressure.
#     2. Prodotto invece di media pesata. Con la media (pesi 0.50 / 0.30 / 0.15 / 0.05) e la combinazione dell'audit
#        (0.6 + 0.4 * env), l'ambiente spostava il BAI solo tra 0.84 e 0.99 e la luce, dichiarata ±15 %, cambiava il BAI
#        del 5 % nel giorno: le ampiezze scritte in B2_PARAMS non erano quelle che il pescatore vede. Con il prodotto
#        ogni escursione dichiarata è l'effetto reale sull'indice (stessa logica dei fattori della parte A e della luna:
#        Vinson & Angradi 2014 danno +5 % sulle catture, e +5 % resta). Il fattore con meno prove (pressione) ha
#        l'escursione più piccola.
#
# Etichette delle fonti come nella parte A: [MISURATO], [INFERENZA], [EURISTICA], "DA VERIFICARE".

# ==============================================================================
# PARAMETRI DELLA PARTE B (si aggiungono a B2_PARAMS; nessuna chiave in comune con la parte A)
# ==============================================================================
B2_PARAMS.update({
    # --- Luce e fotoperiodo (s_sol) ------------------------------------------------------------------------------
    # Fonte del disegno: Hanson K.C., Cooke S.J., Suski C.D., Niezgoda G., Phelan F.J.S., Tinline R., Philipp D.P.
    # (2007), Hydrobiologia 582:243-256, doi:10.1007/s10750-006-0549-6 (testo letto il 29/10/2026). Warner Lake,
    # Ontario, un giorno di 24 h per stagione: primavera (13/04/2004, acqua 7.7 °C) più attività di giorno che di
    # notte, con picchi "leggermente più alti" ad alba e tramonto; autunno (5.9 °C) e inverno (5.1 °C) attività
    # costante, nessun picco. Nessun valore numerico dei rapporti giorno/notte; l'estate NON è stata studiata.
    # [MISURATO la direzione; ampiezze ed estensione all'acqua calda sono EURISTICA]
    #
    # Punteggio medio attorno a cui oscillano le ore. Con i limiti sotto il massimo resta < 1. [EURISTICA]
    "light_base": 0.80,
    # Ampiezza della modulazione diurna in acqua calda, frazione di light_base (±15 %, limite basso dell'intervallo
    # 15-20 % del progetto: con le nuvole il rapporto massimo/minimo resta < 1.5). [EURISTICA]
    "light_warm_amp": 0.15,
    # Forma in acqua calda, in unità di light_warm_amp: notte -1, giorno +0.3, più un picco gaussiano nella prima e
    # nell'ultima ora di luce che porta il massimo vicino a +1. Risultato: notte 0.85, mezzogiorno ~1.045, picchi
    # ~1.15 volte light_base (picchi +10 % sul giorno: "modesti"). [EURISTICA]
    "light_warm_night_rel": -1.0,
    "light_warm_day_rel": 0.3,
    "light_warm_peak_rel": 0.95,
    # Centro dei picchi: alba + 0.5 h e tramonto - 0.5 h, larghezza (deviazione standard) 1 h. [EURISTICA]
    "light_peak_offset_h": 0.5,
    "light_peak_sigma_h": 1.0,
    # Durata della transizione notte/giorno nella funzione di luce (tanh), ore: ordine del crepuscolo civile. [EURISTICA]
    "light_twilight_h": 0.75,
    # Regime freddo: niente giorno/notte né picchi; bonus/malus nelle ore in cui l'acqua del Blocco 1 è più calda o
    # più fredda della media del giorno: ±10 % * tanh(scarto / 0.5 °C). [EURISTICA]
    "light_cold_amp": 0.10,
    "light_cold_rel_scale_c": 0.5,
    # Passaggio dal regime freddo a quello caldo: raccordo smoothstep tra 10 e 14 °C (metà a 12 °C, come chiesto dal
    # progetto). Nota: la soglia NON viene da Hanson et al. 2007, dove il giorno di primavera con picchi era a 7.7 °C
    # e quelli senza picchi a 5-6 °C (la differenza sembra stagionale più che termica; un giorno per stagione, un solo
    # lago: troppo poco per costruirci una regola). In acqua fredda di primavera il regime freddo dà comunque più
    # attività nelle ore di luce, perché l'acqua è più calda di giorno. [EURISTICA]
    "light_cold_below_c": 10.0,
    "light_warm_above_c": 14.0,
    # Nuvole: solo in acqua calda e solo con luce (di notte non cambiano nulla). Da sereno a coperto il punteggio sale
    # del 9 % (±4.5 % attorno al 50 % di copertura): in acqua calda con sole forte il pesce tende a restare in ombra
    # e coperture (pratica da pescatore, nessuna misura trovata). In acqua fredda le nuvole non entrano: l'effetto
    # del sole sull'acqua è già nella temperatura oraria del Blocco 1, contarlo qui sarebbe un doppione. [EURISTICA]
    "light_cloud_amp": 0.09,
    # Stati del sole riconosciuti (campo sun_status del Blocco 5). Qualsiasi altro valore = "normale".
    "light_sun_always_up": "sempre_su",
    "light_sun_always_down": "sempre_giu",

    # --- Vento (s_vento) ---------------------------------------------------------------------------------------
    # Curva unica, nessuna dipendenza dalla temperatura e nessuna riossigenazione (l'ossigeno è in do_actual_mg_l):
    #   s = 1 - 0.12 * (1 - salita) - 0.28 * calo
    #   salita = 0.5 * (1 + tanh((U - 5) / 2))     -> ~1 da 8 km/h in su
    #   calo   = 0.5 * (1 + tanh((U - 34) / 4))    -> comincia oltre 30 km/h, pieno da ~40 km/h
    # Valori: calma 0.88, 8-20 km/h ~1.00, 30 km/h 0.97, 40 km/h 0.73, oltre 0.72 (escursione totale 28 %).
    # Il vento cambia visibilità in superficie e distribuzione delle prede, e nel luccio predice le catture
    # (Lennox et al. 2017, vedi pressione); per il largemouth nessuna quantificazione trovata. [EURISTICA]
    "wind_calm_penalty": 0.12,
    "wind_rise_center_kmh": 5.0,
    "wind_rise_scale_kmh": 2.0,
    "wind_gale_penalty": 0.28,
    "wind_gale_center_kmh": 34.0,
    "wind_gale_scale_kmh": 4.0,
    # Vento ignoto: a metà tra calma e vento favorevole. [EURISTICA]
    "wind_unknown_score": 0.94,

    # --- Pressione (s_press) -------------------------------------------------------------------------------------
    # Solo barometro, sulla pressione al livello del mare (pressure_msl). Nessun meccanismo dimostrato: Lennox R.J.,
    # Alós J., Arlinghaus R. et al. (2017), Fish and Fisheries, doi:10.1111/faf.12219 (volume 18:986-1010 da
    # memoria, DA VERIFICARE; testo letto dall'audit del 28/10/2026) non trovano consenso; l'unico test diretto (luccio) non trova relazioni. In acqua
    # 1 m di profondità = 98 hPa, quindi un fronte di 10 hPa equivale a ~10 cm di profondità. Direzione dalla pratica
    # dei pescatori (pressione in salita o alta = peggio); escursione totale 7 %, la più piccola dei fattori:
    #   s = 1 - 0.04 * 0.5 * (1 + tanh((trend_12h - 1) / 3)) - 0.03 * 0.5 * (1 + tanh((p_msl - 1022) / 6))
    # Fronte da 1010 a 1020 hPa con +10 hPa in 12 h: -3.7 % sull'indice. [EURISTICA]
    "press_trend_penalty": 0.04,
    "press_trend_center_hpa": 1.0,
    "press_trend_scale_hpa": 3.0,
    "press_abs_penalty": 0.03,
    "press_abs_center_hpa": 1022.0,
    "press_abs_scale_hpa": 6.0,
    # Pressione ignota o fuori dall'intervallo plausibile (come nel Blocco 1): atmosfera standard ICAO. [MISURATO]
    "press_default_hpa": 1013.25,
    "press_valid_range_hpa": (850.0, 1090.0),

    # --- Luna -------------------------------------------------------------------------------------------------------
    # Massimo +5 % a luna nuova e piena, 0 ai quarti. Vinson M.R., Angradi T.R. (2014), PLoS ONE 9(5):e98046,
    # doi:10.1371/journal.pone.0098046 (abstract letto il 29/10/2026): muskellunge, effetto relativo massimo previsto
    # ≈ 5 % attorno a luna piena e nuova, più forte nei pesci > 102 cm e di notte. Nessuno studio sul largemouth.
    # Forma: 1 + 0.05 * cos^2(pi * d / 100), d = distanza in punti di illuminazione dalla luna nuova o piena
    # (0-50). [MISURATO l'ampiezza nel muskellunge; trasferimento e forma EURISTICA]
    "moon_max_boost": 0.05,
})


# ==============================================================================
# UTILITÀ DELLA PARTE B
# ==============================================================================
def _b2_smoothstep(x, x0, x1):
    """0 sotto x0, 1 sopra x1, raccordo con derivata continua in mezzo."""
    if x1 <= x0:
        return 1.0 if x >= x1 else 0.0
    u = _b2_clamp((x - x0) / (x1 - x0), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def _b2_circ_h(dh):
    """Differenza oraria sul quadrante di 24 h, in [-12, 12)."""
    return (dh + 12.0) % 24.0 - 12.0


def _b2_light_geometry(h, sunrise_dec, sunset_dec, sun_status):
    """
    -> (luce D 0-1, picco crepuscolare C 0-1, geometria nota). D = 1 di giorno, 0 di notte, raccordo tanh.
    Gestisce il passaggio per la mezzanotte (tramonto "prima" dell'alba nell'ora locale). Sole sempre sopra o
    sempre sotto l'orizzonte: nessun picco. Alba/tramonto non validi: geometria ignota (nessuna modulazione).
    """
    P = B2_PARAMS
    status = sun_status.strip().lower() if isinstance(sun_status, str) else ""
    if status == P["light_sun_always_up"]:
        return 1.0, 0.0, True
    if status == P["light_sun_always_down"]:
        return 0.0, 0.0, True
    sr, ss = _b2_num(sunrise_dec), _b2_num(sunset_dec)
    if sr is None or ss is None:
        return 0.0, 0.0, False
    sr = sr % 24.0
    length = (ss - sr) % 24.0
    if length < 1e-6:
        return 0.0, 0.0, False
    tau = P["light_twilight_h"]
    day = 0.0
    for k in (-24.0, 0.0, 24.0):
        x = h + k - sr
        day = max(day, 0.5 * (1.0 + _b2_math.tanh(x / tau)) * 0.5 * (1.0 - _b2_math.tanh((x - length) / tau)))
    off = min(P["light_peak_offset_h"], 0.5 * length)
    sigma = P["light_peak_sigma_h"]
    peak = 0.0
    for center in (sr + off, sr + length - off):
        d = _b2_circ_h(h - center)
        peak = max(peak, _b2_math.exp(-(d * d) / (2.0 * sigma * sigma)))
    return day, peak, True


# ==============================================================================
# 1. LUCE E FOTOPERIODO
# ==============================================================================
def score_light(hour, sunrise_dec, sunset_dec, clouds, water_temp, water_temp_hourly_rel=0.0,
                sun_status="normale") -> float:
    """
    s_sol (0-1): attività legata alla luce nell'ora `hour` (0-23, ora locale).

    Acqua calda (>= 14 °C): giorno meglio della notte, con picchi modesti nella prima e nell'ultima ora di luce
        (notte 0.85, mezzogiorno ~1.05, picchi ~1.15 volte light_base). Le nuvole contano solo qui e solo di giorno:
        da sereno a coperto +9 %.
    Acqua fredda (<= 10 °C): nessun andamento giorno/notte; ±10 % secondo water_temp_hourly_rel, lo scarto della
        temperatura dell'acqua di quest'ora dalla media del giorno (Blocco 1). Nessuna ora fissa.
    Tra 10 e 14 °C: raccordo continuo tra i due regimi.
    sun_status "sempre_su" / "sempre_giu": nessun picco crepuscolare (sempre giorno / sempre notte).

    Ingressi mancanti: ora o temperatura dell'acqua -> light_base (nessuna modulazione); alba/tramonto non validi
    -> nessuna modulazione giorno/notte; nuvole -> nessun effetto; water_temp_hourly_rel -> 0.
    """
    P = B2_PARAMS
    base = P["light_base"]
    h = _b2_num(hour)
    tw = _b2_num(water_temp)
    if h is None or tw is None:
        return _b2_clamp(base, 0.0, 1.0)
    h = h % 24.0

    w_warm = _b2_smoothstep(tw, P["light_cold_below_c"], P["light_warm_above_c"])

    # regime caldo: giorno/notte + picchi crepuscolari
    day, peak, known = _b2_light_geometry(h, sunrise_dec, sunset_dec, sun_status)
    if known:
        r_warm = (P["light_warm_night_rel"] * (1.0 - day) + P["light_warm_day_rel"] * day
                  + P["light_warm_peak_rel"] * peak)
        r_warm = _b2_clamp(r_warm, -1.0, 1.0)
    else:
        r_warm, day = 0.0, 0.0

    # regime freddo: ore con l'acqua più calda della media del giorno
    rel = _b2_num(water_temp_hourly_rel, 0.0)
    r_cold = _b2_math.tanh(rel / P["light_cold_rel_scale_c"])

    diel = 1.0 + w_warm * P["light_warm_amp"] * r_warm + (1.0 - w_warm) * P["light_cold_amp"] * r_cold

    # nuvole: solo acqua calda, solo con luce
    cl = _b2_num(clouds)
    if cl is None:
        cloud = 1.0
    else:
        cloud = 1.0 + P["light_cloud_amp"] * (_b2_clamp(cl, 0.0, 100.0) / 100.0 - 0.5) * w_warm * day

    return _b2_clamp(base * diel * cloud, 0.0, 1.0)


# ==============================================================================
# 2. VENTO
# ==============================================================================
def score_wind(wind_kmh) -> float:
    """
    s_vento (0-1), vento a 10 m in km/h: calma 0.88, 8-20 km/h ~1.00, calo oltre 30 km/h fino a 0.72.
    Vento negativo trattato come 0; vento non numerico -> wind_unknown_score (0.94).
    """
    P = B2_PARAMS
    u = _b2_num(wind_kmh)
    if u is None:
        return P["wind_unknown_score"]
    u = max(0.0, u)
    rise = 0.5 * (1.0 + _b2_math.tanh((u - P["wind_rise_center_kmh"]) / P["wind_rise_scale_kmh"]))
    gale = 0.5 * (1.0 + _b2_math.tanh((u - P["wind_gale_center_kmh"]) / P["wind_gale_scale_kmh"]))
    s = 1.0 - P["wind_calm_penalty"] * (1.0 - rise) - P["wind_gale_penalty"] * gale
    return _b2_clamp(s, 0.0, 1.0)


# ==============================================================================
# 3. PRESSIONE
# ==============================================================================
def score_pressure(pressure_msl, pressure_trend_12h) -> float:
    """
    s_press (0-1), solo barometro. pressure_msl = pressione al livello del mare (hPa), pressure_trend_12h = variazione
    in 12 h (hPa). Pressione in calo o stabile e non alta ~1.00; in salita e alta fino a 0.93.
    Pressione ignota o fuori 850-1090 hPa -> 1013.25 hPa; trend ignoto -> 0.
    """
    P = B2_PARAMS
    p = _b2_num(pressure_msl)
    lo, hi = P["press_valid_range_hpa"]
    if p is None or not (lo <= p <= hi):
        p = P["press_default_hpa"]
    trend = _b2_num(pressure_trend_12h, 0.0)
    rising = 0.5 * (1.0 + _b2_math.tanh((trend - P["press_trend_center_hpa"]) / P["press_trend_scale_hpa"]))
    high = 0.5 * (1.0 + _b2_math.tanh((p - P["press_abs_center_hpa"]) / P["press_abs_scale_hpa"]))
    s = 1.0 - P["press_trend_penalty"] * rising - P["press_abs_penalty"] * high
    return _b2_clamp(s, 0.0, 1.0)


# ==============================================================================
# 4. LUNA
# ==============================================================================
def moon_factor(moon_illum) -> float:
    """
    Moltiplicatore lunare 1.00-1.05: 1.05 a luna nuova (0 %) e piena (100 %), 1.00 ai quarti (50 %).
    moon_illum = frazione illuminata in % (Blocco 5). Valore ignoto -> 1.00. Va applicato una sola volta (parte C).
    """
    illum = _b2_num(moon_illum)
    if illum is None:
        return 1.0
    illum = _b2_clamp(illum, 0.0, 100.0)
    d = min(illum, 100.0 - illum)                       # 0 = sizigia, 50 = quarto
    return 1.0 + B2_PARAMS["moon_max_boost"] * _b2_math.cos(_b2_math.pi * d / 100.0) ** 2


# ==============================================================================
# 5. COMBINAZIONE
# ==============================================================================
def _b2_env_neutral():
    """Valori usati quando un punteggio manca: quelli che le funzioni danno senza dati."""
    return {
        "light": B2_PARAMS["light_base"],
        "wind": B2_PARAMS["wind_unknown_score"],
        "pressure": score_pressure(None, None),
    }


def environment_index(s_sol, s_vento, s_press) -> float:
    """
    Indice ambientale 0-1 = s_sol * s_vento * s_press: la frazione della condizione ambientale migliore.
    Ogni fattore entra una volta e con la sua escursione piena (luce ±15 %, vento 28 %, pressione 7 %): il rapporto
    tra due ore dell'indice è il prodotto dei rapporti dei singoli punteggi. Intervallo reale circa 0.46-0.96.
    Ogni ingresso viene limitato a 0-1; un ingresso mancante o non numerico prende il valore neutro del suo fattore.
    Non contiene la variazione termica (è in trend_multiplier, parte A) né la luna (moon_factor, parte C).
    """
    neutral = _b2_env_neutral()
    out = 1.0
    for key, value in (("light", s_sol), ("wind", s_vento), ("pressure", s_press)):
        v = _b2_num(value)
        out *= neutral[key] if v is None else _b2_clamp(v, 0.0, 1.0)
    return _b2_clamp(out, 0.0, 1.0)


# ##############################################################################
# PARTE C — TROPHY, SCALA, PICCHI, STRIKE ZONE
# ##############################################################################
# Parte C del nuovo Blocco 2.
#
# FUNZIONI PUBBLICHE (tutte pure)
#     trophy_index(t, do_mg_l, env, micro_72h, macro_14d, moon_illum, s_torb, do_sat_mg_l=None,
#                  do_saturation_index=None) -> float 0-100
#         Indice relativo per i pesci > 2 kg. Prodotto di fattori, ognuno contato una volta:
#         100 * f_big(T) * oxygen_limit(DO, +1 mg/L) * trend_multiplier * s_torb * (env / env_ref) * moon_factor
#             * bonus_prefrega, poi index_scale (0-100, compressione morbida sopra 90).
#     index_scale(raw) -> float 0-100   (scala comune: la usa anche il BAI nella parte D)
#     prespawn_bonus(t, macro_14d) -> float 1.00-2.04   (esposta per i test e per il Blocco 3)
#     pick_peak(timeline, key, sunrise_dec, sunset_dec) -> (riga, flat)
#         Ora migliore con spareggio deterministico; flat = escursione giornaliera < 1 punto.
#     estimate_strike_zone(t, do_mg_l, radiation, wind_kmh, hour, sunrise_dec, sunset_dec, micro_72h,
#                          water_level="Stabile", max_depth_m=None) -> str
#         Fascia descrittiva "Testo (lo m - hi m)", mai più profonda dello spot.
#
# SCALA (vale anche per il BAI della parte D)
#     100 = l'ora migliore realistica: temperatura all'ottimo, ossigeno non limitante, temperatura stabile, acqua
#     limpida, luna al quarto, ambiente migliore realistico (env_ref = 0.96: picco di luce in acqua calda con cielo
#     coperto, vento 15 km/h, pressione in calo). Un riscaldamento recente, la luna nuova/piena o l'acqua limpida
#     possono portare il calcolo oltre 100 vicino all'ottimo. Invece di tagliare a 100 (ore diverse tutte uguali, curva
#     con un altopiano) sopra 90 i valori vengono compressi in modo morbido verso 100, senza mai raggiungerlo:
#     sotto 90 nulla cambia, sopra l'ordine delle ore resta (index_scale).
#
# DUE SCELTE DIVERSE DAL PROMPT DELLA PARTE C (29/10/2026)
#     1. env entra come env / env_ref e non come (0.6 + 0.4 * env): è la scelta fatta nella parte B (prodotto, nessuna
#        diluizione). Con (0.6 + 0.4 * env) la luce, dichiarata ±15 %, cambierebbe il Trophy del 5 % nel giorno.
#     2. Bonus pre-frega fino a ×2.04 invece di ×1.25. Con ×1.25 il Trophy di pre-frega non supera 0.65 dell'ottimo
#        estivo (61 punti), quindi l'app direbbe che luglio è il mese migliore per i pesci grossi e il test C3 (>= 90 con
#        ambiente ottimo) sarebbe irraggiungibile. L'unico dato stagionale sui trofei trovato va nella direzione opposta:
#        dei 346 ShareLunker (>= 13 lb, Texas), 26 % a febbraio, 44 % a marzo, 13 % ad aprile e 17 % negli altri nove
#        mesi (Texas Parks and Wildlife, "March is Big Bass Month", analisi di R. Myers, pagina letta il 29/10/2026; lo
#        sforzo dei pescatori non è controllato e, per molti anni, il programma ha accettato catture solo da ottobre ad
#        aprile, quindi l'estate non è confrontabile: periodo di accettazione da memoria, DA VERIFICARE). L'indice
#        gonadico delle femmine sale da novembre e ha il massimo a febbraio-marzo (Gross T.S. et al. 2002, Am. Fish. Soc.
#        Symp., bass della Florida in stagno, solo abstract). Senza dati estivi comparabili il bonus è scelto in modo che
#        il picco di pre-frega (~15.4 °C) valga quasi quanto l'ottimo termico estivo (25.5 °C): 0.99. Nessuna delle due
#        stagioni domina, autunno e inverno restano sotto. [INFERENZA + EURISTICA, ampiezza DA VERIFICARE]
#
# Etichette delle fonti come nelle parti A e B: [MISURATO], [INFERENZA], [EURISTICA], "DA VERIFICARE".

# ==============================================================================
# PARAMETRI DELLA PARTE C (si aggiungono a B2_PARAMS; nessuna chiave in comune con le parti A e B)
# ==============================================================================
B2_PARAMS.update({
    # --- Scala comune degli indici ----------------------------------------------------------------------------------
    # environment_index dell'ora migliore realistica: 0.959, calcolato con le funzioni della parte B (picco di luce in
    # acqua calda con nuvole 100 %, vento 15 km/h, pressione 1005 hPa in calo di 5 hPa/12 h). Arrotondato. [EURISTICA]
    "index_env_ref": 0.96,
    "index_max": 100.0,
    # Sopra questo valore la scala viene compressa: v = 90 + 10 * tanh((calcolo - 90) / 10). Continua con derivata 1
    # a 90, sempre crescente, mai 100. Serve a non avere più ore pari merito al tetto. [EURISTICA]
    "index_knee": 90.0,

    # --- Trophy (pesci > 2 kg) --------------------------------------------------------------------------------------
    # Ottimo termico spostato di -2 °C rispetto al BAI (CTO_big = 25.5 °C, CTM e CQ invariati). Direzione: Lindmark M.,
    # Ohlberger J., Gårdmark A. (2022), Global Change Biology 28(7):2259-2271, doi:10.1111/gcb.16067: l'ottimo di
    # crescita cala con la taglia dentro la specie (abstract letto dall'audit; nessun valore per il largemouth).
    # Ampiezza [EURISTICA]
    "trophy_cto_shift_c": -2.0,
    # Soglie dell'ossigeno alzate di 1 mg/L: pesci più grandi, maggiore richiesta assoluta. [EURISTICA]
    "trophy_do_shift_mg_l": 1.0,
    # Bonus pre-frega: 1 + (B - 1) * sin^2(pi * (T - 12) / 6) tra 12 e 18 °C (massimo a 15 °C, raccordo con derivata
    # continua agli estremi), moltiplicato per un raccordo smoothstep sul riscaldamento a 14 giorni (0 se l'acqua non
    # si sta scaldando, pieno da +1 °C in 14 giorni).
    # Finestra: la deposizione comincia vicino a 15 °C (Miranda L.E., Muncy R.J. 1987, Proc. Annu. Conf. SEAFWA
    # 41:197-204, testo letto dall'audit) e le femmine pesano di più subito prima. [INFERENZA]
    # B = 2.04: il picco di pre-frega (f_big * bonus, ~15.4 °C) vale 0.99 dell'ottimo termico estivo (con 2.07 sarebbe
    # 1.00); la seconda cifra decimale è fissata in modo che a 15 °C, con gli altri fattori neutri, il Trophy superi
    # 90 solo con env >= 0.90 (test C3). Motivazione e dati nella testa del file. Con B = 1.25 (prima stesura) il
    # picco varrebbe 0.65. [EURISTICA, DA VERIFICARE]
    "trophy_prespawn_t_lo_c": 12.0,
    "trophy_prespawn_t_hi_c": 18.0,
    "trophy_prespawn_max": 2.04,
    "trophy_prespawn_macro_full_c": 1.0,

    # --- Picchi -----------------------------------------------------------------------------------------------------
    # Escursione giornaliera sotto cui la curva è "piatta", punti indice: stessa soglia dei Blocchi 4 e 5. [EURISTICA]
    "peak_flat_span": 1.0,
    # Tolleranza per considerare due valori pari merito, punti indice. [EURISTICA]
    "peak_tie_tol": 1e-6,
    # Alba e tramonto di riserva per lo spareggio quando quelli passati non sono validi (sole sempre sopra o sotto
    # l'orizzonte, dati mancanti): gli stessi valori di riserva del Blocco 5. Evitano il "picco alle 00:00". [EURISTICA]
    "peak_default_twilights_h": (6.5, 19.0),

    # --- Strike zone ------------------------------------------------------------------------------------------------
    # Tutte le soglie e le fasce sono [EURISTICA dichiarata]: pratica da pescatore, nessuna misura di profondità del
    # largemouth nei laghi italiani trovata. Temperature in °C, ossigeno in mg/L, radiazione in W/m², vento in km/h.
    "zone_cold_c": 9.0,                 # sotto: regime invernale
    "zone_cool_c": 14.5,                # 9-14.5: acqua fresca (pre-frega, autunno)
    "zone_hot_c": 28.0,                 # sopra, e solo con ossigeno basso, valgono le regole estive
    "zone_low_do_mg_l": 4.0,            # ossigeno "basso" per le regole estive
    "zone_front_micro_c": -0.9,         # raffreddamento in 72 h che indica un fronte freddo
    "zone_front_max_t_c": 22.0,         # il fronte conta solo sotto questa temperatura
    "zone_winter_sun_rad_wm2": 220.0,   # inverno: sole sufficiente per risalire sulle sassaie esposte
    "zone_winter_wind_max_kmh": 10.0,
    "zone_winter_micro_min_c": -0.3,
    "zone_front_glare_rad_wm2": 450.0,  # fronte: sole forte e calma -> dentro le coperture
    "zone_front_calm_kmh": 7.0,
    "zone_cool_sun_rad_wm2": 200.0,     # acqua fresca: sole o riscaldamento -> risalita sui flat
    "zone_cool_warming_micro_c": 0.5,
    "zone_wave_kmh": 12.0,              # vento che crea onda sulle punte
    "zone_active_wind_kmh": 9.0,        # acqua calda: vento con luce non forte -> acqua bassa attiva
    "zone_active_rad_max_wm2": 450.0,
    "zone_glare_rad_wm2": 600.0,        # acqua calda: sole forte e calma -> ombra fitta
    "zone_glare_calm_kmh": 6.0,
    "zone_night_litoral_min_c": 24.0,   # di notte in acqua calda: basso fondale
    "zone_twilight_window_h": 1.5,      # ore attorno ad alba e tramonto considerate crepuscolo
    "zone_calo_min_depth_m": 1.5,       # livello in calo: mai fasce entro 0-1.5 m (se lo spot è abbastanza profondo)
    "zone_crescita_max_depth_m": 1.5,   # livello in crescita: sempre acqua bassa
    "zone_thermocline_min_depth_m": 4.0,  # sotto questa profondità massima non si parla di termoclino
    "zone_deep_frac": 0.6,              # fascia "punti più profondi": da 0.6 x profondità massima al fondo
    "zone_min_span_m": 0.5,             # ampiezza minima di una fascia dopo i tagli
    # Fasce: chiave -> (testo, profondità minima m, profondità massima m, "oltre" se la profondità dello spot è ignota)
    "zone_bands": {
        "winter_sun": ("Sassaie e sponde a nord, esposte a sud", 2.0, 4.0, False),
        "winter_deep": ("Buche invernali e fondale primario", 4.5, 8.5, True),
        "front_cover": ("Dentro le coperture fitte: legnaie e canneti", 1.5, 3.5, False),
        "front_suspended": ("Sospesi sui drop-off e sul primo scalino", 2.5, 5.0, False),
        "cool_flats": ("Risalita su flat bassi, sassaie e legni", 1.0, 2.2, False),
        "cool_wave_points": ("Punte secondarie e scalini battuti dall'onda", 1.8, 3.5, False),
        "cool_staging": ("Staging sui drop-off e sui margini degli erbai", 2.5, 4.5, False),
        "warm_shallow": ("Acqua bassa attiva, sponde ventose e superficie", 0.2, 1.5, False),
        "warm_shade": ("Ombra fitta: pontili, canneti e alberi sommersi", 0.8, 2.5, False),
        "warm_wave_points": ("Punte esterne e sponde battute dall'onda", 1.2, 3.0, False),
        "warm_night_litoral": ("Basso fondale litorale, caccia notturna", 0.3, 1.5, False),
        "warm_default": ("Sotto superficie, punte e bordi delle coperture", 1.0, 2.5, False),
        "hot_lowdo_night": ("Strato superficiale e immissari, dove arriva acqua più ossigenata", 0.2, 1.0, False),
        "hot_lowdo_day": ("Ombra profonda: sotto i tappeti d'erba o sopra il termoclino", 2.5, 4.5, False),
        "hot_lowdo_day_shallow": ("Ombra sotto la vegetazione più fitta, nei punti più profondi", 1.0, 2.5, False),
        "calo_default": ("Drop-off e punte esterne, bocche dei canali di drenaggio", 1.5, 3.5, False),
        "calo_cold": ("Buche e canali più profondi", 4.5, 8.5, True),
        "calo_hot_lowdo": ("Drop-off esterni in ombra, sopra il termoclino", 2.5, 4.5, False),
        "crescita_default": ("Zone appena allagate: erba, cespugli e canneti sommersi", 0.3, 1.2, False),
        "crescita_cold": ("Bordo esterno delle zone appena allagate, nelle ore più calde", 0.5, 1.5, False),
        "unknown": ("Bordi delle coperture e primo scalino", 1.0, 3.0, False),
    },
    # Testo usato quando la fascia scelta è tutta più profonda dello spot (si scende ai punti più profondi disponibili).
    "zone_deepest_text": "Punti più profondi dello spot",
    "zone_levels": ("Stabile", "In Crescita", "In Calo"),
})


# ==============================================================================
# 0. SCALA COMUNE (usata anche dal BAI nella parte D)
# ==============================================================================
def index_scale(raw) -> float:
    """
    Calcolo grezzo in punti -> indice 0-100. Identità fino a 90; sopra, 90 + 10 * tanh((raw - 90) / 10): sempre
    crescente, mai 100, nessun pari merito al tetto. Negativi e valori non numerici -> 0.
    """
    P = B2_PARAMS
    v = _b2_num(raw, 0.0)
    v = max(0.0, v)
    knee, top = P["index_knee"], P["index_max"]
    if v <= knee or top <= knee:
        return min(v, top)
    span = top - knee
    return knee + span * _b2_math.tanh((v - knee) / span)


# ==============================================================================
# 1. TROPHY
# ==============================================================================
def prespawn_bonus(t, macro_14d) -> float:
    """
    Moltiplicatore pre-frega 1.00-2.04: massimo a 15 °C con acqua in riscaldamento da almeno +1 °C in 14 giorni,
    1.00 fuori da 12-18 °C o con acqua stabile o in raffreddamento. Continuo in temperatura e in macro_14d.
    """
    P = B2_PARAMS
    tv = _b2_num(t)
    if tv is None:
        return 1.0
    lo, hi = P["trophy_prespawn_t_lo_c"], P["trophy_prespawn_t_hi_c"]
    if not (lo < tv < hi) or hi <= lo:
        return 1.0
    shape = _b2_math.sin(_b2_math.pi * (tv - lo) / (hi - lo)) ** 2
    macro = _b2_num(macro_14d, 0.0)
    full = P["trophy_prespawn_macro_full_c"]
    u = _b2_clamp(macro / full, 0.0, 1.0) if full > 0 else (1.0 if macro > 0 else 0.0)
    warming = u * u * (3.0 - 2.0 * u)
    return 1.0 + (P["trophy_prespawn_max"] - 1.0) * shape * warming


def trophy_index(t, do_mg_l, env, micro_72h, macro_14d, moon_illum, s_torb, do_sat_mg_l=None,
                 do_saturation_index=None) -> float:
    """
    Indice Trophy 0-100 (pesci > 2 kg), relativo, non una probabilità.
        100 * f_big(T) * oxygen_limit(DO, +1 mg/L) * trend_multiplier(T, micro_72h) * s_torb
            * (env / 0.96) * moon_factor(moon_illum) * prespawn_bonus(T, macro_14d), poi index_scale
    f_big = consumption_temperature_factor con ottimo a 25.5 °C. env = environment_index della parte B.
    s_torb = moltiplicatore di turbidity_factor (numero, non etichetta).
    Ingressi mancanti: DO -> do_sat_mg_l * do_saturation_index se ci sono, altrimenti nessun limite; env -> valore
    neutro della parte B; s_torb -> Velata; luna e trend -> nessun effetto; temperatura -> minimo della curva.
    Ogni fattore entra una volta: nessun boost aggiuntivo di luna, vento, pressione, luce o crepuscolo.
    """
    P = B2_PARAMS
    tv = _b2_num(t)
    f_big = consumption_temperature_factor(tv, cto=P["cons_cto_c"] + P["trophy_cto_shift_c"])
    o2 = oxygen_limit(do_mg_l, shift=P["trophy_do_shift_mg_l"], do_sat_mg_l=do_sat_mg_l,
                      do_saturation_index=do_saturation_index)
    trend = trend_multiplier(tv, micro_72h, macro_14d)
    torb = _b2_num(s_torb)
    torb = turbidity_factor(None)[0] if torb is None else _b2_clamp(torb, 0.0, 1.0)
    env_v = _b2_num(env)
    if env_v is None:
        env_v = environment_index(None, None, None)
    env_rel = _b2_clamp(env_v, 0.0, 1.0) / P["index_env_ref"]
    value = (P["index_max"] * f_big * o2 * trend * torb * env_rel * moon_factor(moon_illum)
             * prespawn_bonus(tv, macro_14d))
    return index_scale(value)


# ==============================================================================
# 2. PICCHI
# ==============================================================================
def _b2_row_hour(row, index):
    """Ora della riga: campo hour, poi time_label "HH:MM", poi la posizione nella lista."""
    h = _b2_num(row.get("hour"))
    if h is not None:
        return h
    label = row.get("time_label")
    if isinstance(label, str):
        m = _b2_re.match(r"\s*(\d{1,2})(?::(\d{2}))?", label)
        if m:
            return int(m.group(1)) + (int(m.group(2)) / 60.0 if m.group(2) else 0.0)
    return float(index)


def _b2_peak_twilights(sunrise_dec, sunset_dec):
    """Alba e tramonto per lo spareggio; quelli di riserva se mancano o se il giorno è degenere (0 o 24 h)."""
    sr, ss = _b2_num(sunrise_dec), _b2_num(sunset_dec)
    if sr is not None and ss is not None:
        length = (ss - sr) % 24.0
        if 1e-6 < length < 24.0 - 1e-6:
            return sr % 24.0, ss % 24.0
    return tuple(B2_PARAMS["peak_default_twilights_h"])


def pick_peak(timeline, key, sunrise_dec, sunset_dec):
    """
    -> (riga con il valore massimo di `key`, flat).
    Pari merito (entro 1e-6): prima l'ora più vicina ad alba o tramonto (distanza sul quadrante di 24 h), poi l'ora
    più bassa, poi la posizione nella lista. flat = True se max - min < 1 punto: in quel caso nessuna ora si distingue
    e la riga restituita è solo indicativa (mai le 00:00 per pareggio, salvo alba o tramonto vicini alla mezzanotte).
    Righe non dizionario o senza valore numerico vengono ignorate; nessuna riga valida -> (prima riga o {}, True).
    """
    P = B2_PARAMS
    rows = [r for r in timeline if isinstance(r, dict)] if isinstance(timeline, (list, tuple)) else []
    scored = [(i, r, _b2_num(r.get(key))) for i, r in enumerate(rows)]
    scored = [(i, r, v) for i, r, v in scored if v is not None]
    if not scored:
        return (rows[0] if rows else {}), True
    values = [v for _, _, v in scored]
    v_max, v_min = max(values), min(values)
    flat = (v_max - v_min) < P["peak_flat_span"]
    twilights = _b2_peak_twilights(sunrise_dec, sunset_dec)
    candidates = []
    for i, r, v in scored:
        if v >= v_max - P["peak_tie_tol"]:
            h = _b2_row_hour(r, i)
            dist = min(abs(_b2_circ_h(h - tw)) for tw in twilights)
            candidates.append((dist, h % 24.0, i, r))
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    return candidates[0][3], flat


# ==============================================================================
# 3. STRIKE ZONE
# ==============================================================================
def _b2_zone_text(band_key, max_depth, water_level):
    """Testo finale della fascia con i tagli: mai oltre la profondità dello spot, regole del livello dell'acqua."""
    P = B2_PARAMS
    text, lo, hi, open_end = P["zone_bands"].get(band_key, P["zone_bands"]["unknown"])
    min_span = P["zone_min_span_m"]
    if max_depth is not None:
        open_end = False
        if lo >= max_depth - 1e-9:
            text = P["zone_deepest_text"]
            lo, hi = P["zone_deep_frac"] * max_depth, max_depth
        else:
            hi = min(hi, max_depth)
    if water_level == "In Calo":
        lo = max(lo, min(P["zone_calo_min_depth_m"], hi - min_span))
    elif water_level == "In Crescita":
        hi = min(hi, P["zone_crescita_max_depth_m"])
    if hi - lo < min_span:
        lo = max(0.0, hi - min_span)
    lo, hi = round(lo, 1), round(hi, 1)
    return "%s (%sm - %sm%s)" % (text, "%.1f" % lo, "%.1f" % hi, "+" if open_end else "")


def estimate_strike_zone(t, do_mg_l, radiation, wind_kmh, hour, sunrise_dec, sunset_dec, micro_72h,
                         water_level="Stabile", max_depth_m=None) -> str:
    """
    Fascia descrittiva della strike zone: "Testo (lo m - hi m)". Soglie e fasce in B2_PARAMS (EURISTICA dichiarata).
      * Livello "In Calo": drop-off e punte esterne, mai entro 0-1.5 m (se lo spot è profondo almeno 2 m).
      * Livello "In Crescita": zone appena allagate, sempre entro 1.5 m.
      * Regole estive (ombra profonda, termoclino) solo con T > 28 °C e DO < 4 mg/L.
      * Nessuna fascia oltre max_depth_m: se quella scelta è tutta più profonda dello spot, "Punti più profondi
        dello spot" (dal 60 % della profondità massima al fondo).
    Ingressi mancanti: temperatura -> fascia generica; DO -> non basso; vento, radiazione, trend -> 0;
    livello sconosciuto -> Stabile; alba/tramonto non validi -> notte = radiazione nulla, nessun crepuscolo.
    """
    P = B2_PARAMS
    level = water_level if water_level in P["zone_levels"] else "Stabile"
    depth = _b2_num(max_depth_m)
    depth = depth if depth is not None and depth > 0 else None
    tv = _b2_num(t)
    if tv is None:
        return _b2_zone_text("unknown", depth, level)
    do_v = _b2_num(do_mg_l)
    rad = max(0.0, _b2_num(radiation, 0.0))
    wind = max(0.0, _b2_num(wind_kmh, 0.0))
    micro = _b2_num(micro_72h, 0.0)
    h = _b2_num(hour)

    # crepuscolo e notte
    twilight, night = False, rad <= 0.0
    if h is not None:
        day, _peak, known = _b2_light_geometry(h % 24.0, sunrise_dec, sunset_dec, "normale")
        if known:
            night = day < 0.5
            win = P["zone_twilight_window_h"]
            sr, ss = _b2_num(sunrise_dec), _b2_num(sunset_dec)
            twilight = min(abs(_b2_circ_h(h - sr)), abs(_b2_circ_h(h - ss))) <= win

    hot_lowdo = tv > P["zone_hot_c"] and do_v is not None and do_v < P["zone_low_do_mg_l"]

    # 1) livello dell'acqua
    if level == "In Calo":
        if hot_lowdo:
            band = "calo_hot_lowdo"
        elif tv < P["zone_cold_c"]:
            band = "calo_cold"
        else:
            band = "calo_default"
        return _b2_zone_text(band, depth, level)
    if level == "In Crescita":
        band = "crescita_cold" if tv < P["zone_cold_c"] else "crescita_default"
        return _b2_zone_text(band, depth, level)

    # 2) estate con ossigeno basso
    if hot_lowdo:
        if night or twilight:
            band = "hot_lowdo_night"
        elif depth is not None and depth < P["zone_thermocline_min_depth_m"]:
            band = "hot_lowdo_day_shallow"
        else:
            band = "hot_lowdo_day"
        return _b2_zone_text(band, depth, level)

    # 3) inverno
    if tv < P["zone_cold_c"]:
        if (rad >= P["zone_winter_sun_rad_wm2"] and wind < P["zone_winter_wind_max_kmh"]
                and micro >= P["zone_winter_micro_min_c"]):
            band = "winter_sun"
        else:
            band = "winter_deep"
        return _b2_zone_text(band, depth, level)

    # 4) fronte freddo
    if micro <= P["zone_front_micro_c"] and tv < P["zone_front_max_t_c"]:
        if rad > P["zone_front_glare_rad_wm2"] and wind < P["zone_front_calm_kmh"]:
            band = "front_cover"
        else:
            band = "front_suspended"
        return _b2_zone_text(band, depth, level)

    # 5) acqua fresca
    if tv < P["zone_cool_c"]:
        if rad >= P["zone_cool_sun_rad_wm2"] or (micro >= P["zone_cool_warming_micro_c"] and not night):
            band = "cool_flats"
        elif wind >= P["zone_wave_kmh"]:
            band = "cool_wave_points"
        else:
            band = "cool_staging"
        return _b2_zone_text(band, depth, level)

    # 6) acqua temperata e calda (anche sopra 28 °C se l'ossigeno non è basso)
    if twilight or (wind >= P["zone_active_wind_kmh"] and rad < P["zone_active_rad_max_wm2"] and not night):
        band = "warm_shallow"
    elif rad >= P["zone_glare_rad_wm2"] and wind < P["zone_glare_calm_kmh"]:
        band = "warm_shade"
    elif not night and wind >= P["zone_wave_kmh"]:
        band = "warm_wave_points"
    elif night and tv >= P["zone_night_litoral_min_c"]:
        band = "warm_night_litoral"
    else:
        band = "warm_default"
    return _b2_zone_text(band, depth, level)


# ##############################################################################
# PARTE D — SIMULAZIONE DELLE 24 ORE E CLASSE PUBBLICA
# ##############################################################################
# Parte D del nuovo Blocco 2: la simulazione delle 24 ore e la classe ProTourBiologicalEngine letta dai Blocchi 3, 4 e 5.
#
# INTERFACCIA
#     ProTourBiologicalEngine.run_pro_simulation(series_data, astro, torbidita, manual_water_temp=None,
#                                                water_level="Stabile", max_depth_m=None) -> dict
#         series_data: dizionario del Blocco 1 v2 (fetch_thermal_and_weather_series / build_thermal_series).
#         astro: sunrise_dec, sunset_dec, moon_illum (0-100), facoltativo sun_status. None o incompleto: alba 6.5,
#                tramonto 19.5, luna 50, con un avviso in "warnings".
#         torbidita: "Velata" | "Limpida" | "Torbida" | "Fangosa" | "Non specificato" (qualsiasi altro valore = Velata).
#         manual_water_temp: temperatura della sonda (°C) o None.
#         water_level, max_depth_m: NUOVI e facoltativi (il Blocco 5 attuale non li passa). Senza max_depth_m la
#                profondità massima viene presa da SPOT_TYPES[series_data["spot"]] se il Blocco 1 v2 è nello stesso file.
#     Solleva ValueError solo se series_data non contiene nessuna riga oraria.
#
# USCITA
#     timeline (una riga per ogni ora del Blocco 1, copiata così com'è) + water_temp_used, torbidita_label, s_temp
#     (= f(T) x limite ossigeno, 0-1), s_press, s_sol, s_vento, s_torb (0-1), env_trigger (0-100), catch_rate (0-100),
#     trophy_rate (0-100), depth_zone, trend_mult, do_limit, do_used_mg_l.
#     best_hour, best_trophy_hour (righe della timeline scelte con pick_peak), top_3, avg_rate, macro_trend_14d,
#     micro_trend_72h, biological_state, thermal_trend_3d, mean_7d_air, trophy_flat, bai_flat, no_good_window,
#     window_quality, warnings, astro_used, probe_used.
#
# BAI (catch_rate)
#     index_scale(100 * f(T) * do_limit * trend_mult * s_torb * (env / env_ref) * moon_factor)
#     Rispetto al prompt della parte D: env / env_ref invece di (0.6 + 0.4 * env), per la scelta della parte B (prodotto,
#     nessuna diluizione) e index_scale invece del taglio a 100 (parte C: nessun altopiano al tetto). Stessa scala del Trophy.
#
# SONDA
#     water_temp_used = sonda + (water_temp dell'ora - hourly_mean_water_temp del Blocco 1): si conserva la forma della
#     curva oraria del modello, non il suo livello (base_water_temp è la media di uno strato diverso e non si usa).
#     L'ossigeno viene riportato alla temperatura della sonda: saturazione ricalcolata con do_saturation_mg_l del
#     Blocco 1, stesso rapporto reale/saturazione del modello. biological_state = classify_biological_state(sonda, ...)
#     del Blocco 1 con l'ossigeno minimo del giorno. Se il Blocco 1 non è nello stesso file, si tengono i valori del
#     modello e lo si segnala in "warnings".

# ==============================================================================
# PARAMETRI DELLA PARTE D
# ==============================================================================
B2_PARAMS.update({
    # Astronomia di riserva se astro manca o è incompleto (valori del progetto; luna al quarto = nessun effetto). [EURISTICA]
    "sim_default_sunrise_h": 6.5,
    "sim_default_sunset_h": 19.5,
    "sim_default_moon_illum": 50.0,
    # Temperatura dell'acqua usata se una riga e la serie non ne hanno (stesso valore del Blocco 2 originale). [EURISTICA]
    "sim_default_water_temp_c": 15.0,
    # Intervallo accettato per la temperatura con la sonda, °C: 0 = congelamento (limite del Blocco 1 v2), 40 = oltre
    # il limite letale del largemouth (CTmax 37.3 °C a 24 °C di acclimatazione, Fields et al. 1987, citato nel
    # Blocco 1 v2). [INFERENZA]
    "sim_water_temp_range_c": (0.0, 40.0),
    # Soglie lette dal Blocco 4 (valori del progetto). [EURISTICA]
    "sim_no_good_window_below": 15.0,    # no_good_window = True se il catch_rate massimo del giorno è sotto
    "sim_poor_window_below": 30.0,       # window_quality = "scarsa" se il catch_rate massimo è sotto
    "sim_top_n": 3,
    # Decimali nell'uscita: indici a 1 decimale come il Blocco 2 originale, punteggi a 3. [EURISTICA]
    "sim_round_index": 1,
    "sim_round_score": 3,
})


# ==============================================================================
# UTILITÀ DELLA SIMULAZIONE
# ==============================================================================
def _b2_astro_used(astro, warnings):
    """Alba, tramonto, luna e stato del sole effettivi; valori di riserva con avviso se mancano."""
    P = B2_PARAMS
    a = astro if isinstance(astro, dict) else {}
    sr = _b2_num(a.get("sunrise_dec"))
    ss = _b2_num(a.get("sunset_dec"))
    moon = _b2_num(a.get("moon_illum"))
    missing = [k for k, v in (("sunrise_dec", sr), ("sunset_dec", ss), ("moon_illum", moon)) if v is None]
    if missing:
        warnings.append("Dati astronomici mancanti o non validi (%s): uso alba %.1f, tramonto %.1f, luna %d %%."
                        % (", ".join(missing), P["sim_default_sunrise_h"], P["sim_default_sunset_h"],
                           int(P["sim_default_moon_illum"])))
    status = a.get("sun_status")
    return {
        "sunrise_dec": P["sim_default_sunrise_h"] if sr is None else sr,
        "sunset_dec": P["sim_default_sunset_h"] if ss is None else ss,
        "moon_illum": P["sim_default_moon_illum"] if moon is None else _b2_clamp(moon, 0.0, 100.0),
        "sun_status": status if isinstance(status, str) and status else "normale",
    }


def _b2_spot_max_depth(series, max_depth_m):
    """Profondità massima: quella passata, altrimenti SPOT_TYPES[spot]["max_depth_m"] del Blocco 1 v2, altrimenti None."""
    d = _b2_num(max_depth_m)
    if d is not None and d > 0:
        return d
    spots = globals().get("SPOT_TYPES")
    key = series.get("spot")
    if isinstance(spots, dict) and isinstance(key, str) and isinstance(spots.get(key), dict):
        d = _b2_num(spots[key].get("max_depth_m"))
        if d is not None and d > 0:
            return d
    return None


def _b2_do_at_temperature(row, t_model, t_used):
    """
    (ossigeno reale, saturazione) in mg/L alla temperatura usata. Senza sonda (o senza do_saturation_mg_l del
    Blocco 1 nello stesso file) sono quelli della riga. Con la sonda: saturazione ricalcolata alla temperatura della
    sonda e alla pressione al suolo della riga, stesso rapporto reale/saturazione del modello.
    """
    do_act = _b2_num(row.get("do_actual_mg_l"))
    do_sat = _b2_num(row.get("do_sat_mg_l"))
    sat_fn = globals().get("do_saturation_mg_l")
    if t_model is None or t_used is None or abs(t_used - t_model) < 1e-9 or not callable(sat_fn):
        return do_act, do_sat
    if do_act is not None and do_sat is not None and do_sat > 0:
        ratio = do_act / do_sat
    else:
        ratio = _b2_num(row.get("do_saturation_index"))
    sat_new = _b2_num(sat_fn(t_used, row.get("surface_pressure")))
    if sat_new is None or ratio is None:
        return do_act, do_sat
    return sat_new * ratio, sat_new


def _b2_rank_key(row, index, key, twilights):
    """Ordine per top_3: valore più alto, poi ora più vicina ad alba o tramonto, poi ora più bassa (come pick_peak)."""
    v = _b2_num(row.get(key), -1.0)
    h = _b2_row_hour(row, index)
    dist = min(abs(_b2_circ_h(h - tw)) for tw in twilights)
    return (-v, dist, h % 24.0, index)


# ==============================================================================
# SIMULAZIONE DELLE 24 ORE
# ==============================================================================
def _b2_simulate(series_data, astro, torbidita, manual_water_temp=None, water_level="Stabile", max_depth_m=None):
    P = B2_PARAMS
    warnings = []
    series = series_data if isinstance(series_data, dict) else {}
    hourly = series.get("hourly")
    rows_in = [r for r in hourly if isinstance(r, dict)] if isinstance(hourly, (list, tuple)) else []
    if not rows_in:
        raise ValueError("Blocco 2: la serie del Blocco 1 non contiene righe orarie.")
    if len(rows_in) != 24:
        warnings.append("La serie oraria ha %d righe invece di 24." % len(rows_in))

    astro_u = _b2_astro_used(astro, warnings)
    sr, ss, moon_illum, sun_status = (astro_u["sunrise_dec"], astro_u["sunset_dec"], astro_u["moon_illum"],
                                      astro_u["sun_status"])
    macro = _b2_num(series.get("macro_trend_14d"), 0.0)
    micro = _b2_num(series.get("micro_trend_72h"), _b2_num(series.get("thermal_trend_3d"), 0.0))
    mean_7d_air = _b2_num(series.get("mean_7d_air"), P["sim_default_water_temp_c"])
    base_temp = _b2_num(series.get("base_water_temp"), P["sim_default_water_temp_c"])
    s_torb, torb_label = turbidity_factor(torbidita)
    level = water_level if water_level in P["zone_levels"] else "Stabile"
    depth = _b2_spot_max_depth(series, max_depth_m)

    # temperatura del modello per ogni ora e sua media (forma della curva oraria)
    model_t = [_b2_num(r.get("water_temp")) for r in rows_in]
    if any(t is None for t in model_t):
        warnings.append("Temperatura dell'acqua mancante in %d ore: uso la temperatura del giorno."
                        % sum(1 for t in model_t if t is None))
        model_t = [base_temp if t is None else t for t in model_t]
    hourly_mean = _b2_num(series.get("hourly_mean_water_temp"))
    if hourly_mean is None:
        hourly_mean = sum(model_t) / len(model_t)

    probe = _b2_num(manual_water_temp)
    if manual_water_temp is not None and probe is None:
        warnings.append("Temperatura della sonda non numerica (%r): ignorata." % (manual_water_temp,))
    t_lo, t_hi = P["sim_water_temp_range_c"]
    if probe is not None:
        probe = _b2_clamp(probe, t_lo, t_hi)
        if not callable(globals().get("do_saturation_mg_l")):
            warnings.append("Sonda attiva ma do_saturation_mg_l del Blocco 1 non disponibile: ossigeno del modello.")

    env_ref = P["index_env_ref"]
    moon = moon_factor(moon_illum)
    r_idx, r_sc = P["sim_round_index"], P["sim_round_score"]
    timeline, do_used_all = [], []
    for i, row in enumerate(rows_in):
        t_mod = model_t[i]
        rel = t_mod - hourly_mean
        t_used = t_mod if probe is None else _b2_clamp(probe + rel, t_lo, t_hi)
        t_used = round(t_used, 1) if probe is not None else t_used
        do_used, do_sat = _b2_do_at_temperature(row, t_mod, t_used)
        if do_used is not None:
            do_used_all.append(do_used)
        hour = _b2_row_hour(row, i)

        f_t = consumption_temperature_factor(t_used)
        do_lim = oxygen_limit(do_used, 0.0, do_sat, row.get("do_saturation_index"))
        trend = trend_multiplier(t_used, micro, macro)
        s_sol = score_light(hour, sr, ss, row.get("clouds"), t_used, rel, sun_status)
        s_vento = score_wind(row.get("wind"))
        s_press = score_pressure(row.get("pressure"), row.get("pressure_trend_12h"))
        env = environment_index(s_sol, s_vento, s_press)
        catch = index_scale(100.0 * f_t * do_lim * trend * s_torb * (env / env_ref) * moon)
        trophy = trophy_index(t_used, do_used, env, micro, macro, moon_illum, s_torb, do_sat,
                              row.get("do_saturation_index"))
        zone = estimate_strike_zone(t_used, do_used, row.get("radiation"), row.get("wind"), hour, sr, ss, micro,
                                    level, depth)
        out = dict(row)
        out.update({
            "water_temp_used": t_used,
            "torbidita_label": torb_label,
            "s_temp": round(f_t * do_lim, r_sc),
            "s_press": round(s_press, r_sc),
            "s_sol": round(s_sol, r_sc),
            "s_vento": round(s_vento, r_sc),
            "s_torb": round(s_torb, r_sc),
            "env_trigger": round(100.0 * env, r_idx),
            "catch_rate": round(catch, r_idx),
            "trophy_rate": round(trophy, r_idx),
            "depth_zone": zone,
            "trend_mult": round(trend, r_sc),
            "do_limit": round(do_lim, r_sc),
            "do_used_mg_l": None if do_used is None else round(do_used, 2),
        })
        timeline.append(out)

    best_hour, bai_flat = pick_peak(timeline, "catch_rate", sr, ss)
    best_trophy_hour, trophy_flat = pick_peak(timeline, "trophy_rate", sr, ss)
    twilights = _b2_peak_twilights(sr, ss)
    order = sorted(range(len(timeline)), key=lambda k: _b2_rank_key(timeline[k], k, "catch_rate", twilights))
    top = [timeline[k] for k in order[:P["sim_top_n"]]]
    catches = [_b2_num(r.get("catch_rate"), 0.0) for r in timeline]
    max_catch = max(catches)

    bio_state = series.get("biological_state")
    bio_state = bio_state if isinstance(bio_state, str) and bio_state else "Stato non determinato."
    if probe is not None:
        classify = globals().get("classify_biological_state")
        if callable(classify):
            bio_state = classify(probe, macro, micro, min(do_used_all) if do_used_all else None)
        else:
            warnings.append("Sonda attiva ma classify_biological_state del Blocco 1 non disponibile: stato del modello.")

    return {
        "timeline": timeline,
        "best_hour": best_hour,
        "best_trophy_hour": best_trophy_hour,
        "top_3": top,
        "avg_rate": round(sum(catches) / len(catches), r_idx),
        "macro_trend_14d": macro,
        "micro_trend_72h": micro,
        "biological_state": bio_state,
        "thermal_trend_3d": micro,
        "mean_7d_air": mean_7d_air,
        "trophy_flat": bool(trophy_flat),
        "bai_flat": bool(bai_flat),
        "no_good_window": bool(max_catch < P["sim_no_good_window_below"]),
        "window_quality": "scarsa" if max_catch < P["sim_poor_window_below"] else "",
        "warnings": warnings,
        "astro_used": astro_u,
        "probe_used": probe,
        "water_level_used": level,
        "max_depth_used_m": depth,
    }


# ==============================================================================
# CLASSE PUBBLICA (letta dai Blocchi 3, 4 e 5)
# ==============================================================================
class ProTourBiologicalEngine:
    """
    Motore biologico del Bass Engine (Blocco 2 v2). Indici relativi 0-100 per l'attività (BAI, catch_rate) e per i
    pesci > 2 kg (trophy_rate), costruiti come prodotto di fattori contati una volta ciascuno: temperatura (modello
    bioenergetico Wisconsin, Rice et al. 1983), ossigeno (criteri EPA 1986), variazione termica, torbidità, luce, vento,
    pressione, luna; per il Trophy anche il pre-frega. Costanti, fonti e limiti in B2_PARAMS e nel CHANGELOG.
    Le vecchie funzioni statiche (metabolic_potential, score_barometric_and_sky, ...) non sono più esposte: nessun
    altro blocco le chiamava. Le nuove sono funzioni del modulo.
    """

    @classmethod
    def run_pro_simulation(cls, series_data, astro, torbidita, manual_water_temp=None, water_level="Stabile",
                           max_depth_m=None) -> dict:
        """Simulazione delle 24 ore (vedi la testa della parte D). Solleva ValueError solo senza righe orarie."""
        return _b2_simulate(series_data, astro, torbidita, manual_water_temp, water_level, max_depth_m)


# >>> BLOCCO: Blocco3-BF-V3.py <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ==============================================================================
# BASS ENGINE — BLOCCO 3 (v3): REPORT TATTICO IN ITALIANO
# ==============================================================================
_b0_magia = """
v3 (30/10/2026), rispetto alla v2: due obiettivi distinti per il report, "Numeri" (più catture) e "Trophy" (pesci
oltre 2 kg), scelti nel tab "Strategia" del Blocco 5 v5. Con "Trophy" cambiano anche cinetica di recupero, setup canna
e filo e colori (nella v2 cambiavano solo le esche); "Numeri" aggiunge al recupero la regola per fare numero. Con la
curva Trophy piatta il report Trophy usa l'ora migliore dell'attività (il best_trophy_hour del Blocco 2 in quel caso
non è un picco). Nel Bio-alert "Azione" diventa "Attività", lo stesso nome dei grafici. Via l'etichetta "(pratica da
pescatore)" dai testi: le indicazioni pratiche non hanno etichetta, i dati hanno la fonte. Nei colori non compare
più "Cosa dicono i dati" (resta nel codice come appunto, _b3_color_evidence). "Entrambi" resta accettato per i vecchi
chiamanti.

Blocco 3 dell'app Streamlit "Bass Engine": dalla riga oraria del Blocco 2 v2 ai testi del report tattico che il
Blocco 5 v2 mostra nel tab "Report Tattico Pro". File unico, ottenuto da tre parti (ognuna con i suoi test):
    PARTE A  condizione fisiologica, approccio posizionale, strike zone;
    PARTE B  cinetica di recupero, setup canna e filo, colori;
    PARTE C  esche, strategia Trophy, classe pubblica TacticalAdvisorV2.

INTERFACCIA PUBBLICA (letta dal Blocco 5 v2 e da audit_scenari_bassengine_v2.py)
    TacticalAdvisorV2.generate_pro_report(best_hour, trend_3d, astro, sim_results=None, water_level="Stabile",
        forage_base="Misto", fishing_pressure="Media", target_mode="Entrambi") -> dict
        Chiavi: condizione, approccio, esche_primarie, esche_secondarie, colore, recupero, strike_zone, gear_setup,
        strategia_trophy, bio_alert, target_mode, esche, colori, velocita. Invarianti nella testa della parte C.
    TacticalAdvisorV2.generate_report(sim_data, ...)   vecchio wrapper, delega a generate_pro_report.
    Funzioni del modulo (pure): physiological_condition, positional_approach, strike_zone_for, retrieve_kinetics,
    gear_setup, color_choice, lure_matrix, trophy_strategy. Dalla v3 retrieve_kinetics, gear_setup e color_choice
    accettano in fondo goal="Numeri" | "Trophy" (None = testo della v2).

USO NELL'APP
    Incollare dopo il Blocco 2 v2 e prima dei Blocchi 4 e 5. Dal Blocco 2 v2 (se nello stesso file) usa
    estimate_strike_zone, B2_PARAMS e prespawn_bonus; dal Blocco 1 v2 classify_biological_state. Senza di loro funziona
    con valori di riserva e lo dice nel testo. Nomi interni con prefisso _b3_, costanti in B3_PARAMS.

COSTANTI: tutte in B3_PARAMS, con valore, unità, fonte e tipo ([MISURATO] valore documentato da una fonte citata o
costante fisica; [INFERENZA] dedotto; [EURISTICA] scelta di progetto; "DA VERIFICARE" = non controllato sul testo
originale). Modifiche rispetto al Blocco 3 originale e fonti: CHANGELOG_Blocco3.md.
Gli indici sono relativi (0-100), mai probabilità di cattura.

Requisiti: Python 3.10+, solo libreria standard.
"""


# ==============================================================================
# BASS ENGINE — BLOCCO 3 (v3), PARTE A DI 3: CONDIZIONE FISIOLOGICA E POSIZIONAMENTO
# ==============================================================================
# Parte A del nuovo Blocco 3 (report tattico in italiano). Contiene solo i testi "condizione fisiologica" e
# "approccio posizionale" e la strike zone che il report userà. Le parti B (recupero, attrezzatura, colori) e C (esche,
# strategia Trophy, classe TacticalAdvisorV2) seguono nello stesso file.
#
# FUNZIONI PUBBLICHE (pure: nessuna rete, nessuno stato, solo libreria standard)
#     physiological_condition(row, sim) -> str
#         Testo "condizione". Prima riga:  :material/genetics: **Stato Biologico Rilevato:** *{biological_state}*
#         poi tre punti: temperatura e ossigeno disciolto (mg/L), pressione (Δ3h, Δ12h), trend termico (Δ72h, Δ14gg).
#     positional_approach(row, sim, water_level, astro) -> str
#         Parte "posizionamento" del testo "approccio". Prima riga:
#             :material/straighten: **Strike Zone Batimetrica Primaria:** `{zona}`
#         poi il livello dell'acqua e l'indicazione stagionale (indicazioni pratiche, senza etichetta dalla v3).
#     strike_zone_for(row, sim, water_level, astro) -> str
#         La stessa zona della prima riga di positional_approach (chiave "strike_zone" del report).
#
# INGRESSI
#     row          riga oraria della timeline del Blocco 2 v2 (di solito best_hour o best_trophy_hour). Chiavi lette:
#                  hour, time_label, water_temp_used (o water_temp), wind, radiation, pressure (al livello del mare),
#                  pressure_delta, pressure_trend_12h, do_used_mg_l (o do_actual_mg_l, o do_sat_mg_l x
#                  do_saturation_index), do_sat_mg_l, do_limit, trend_mult, depth_zone.
#     sim          uscita di ProTourBiologicalEngine.run_pro_simulation. Chiavi lette: biological_state,
#                  macro_trend_14d, micro_trend_72h (o thermal_trend_3d), probe_used, water_level_used,
#                  max_depth_used_m, astro_used.
#     water_level  "Stabile" | "In Crescita" | "In Calo" (scelta dell'utente, maiuscole e spazi indifferenti).
#                  None o valore non riconosciuto: il livello della simulazione (sim["water_level_used"]).
#     astro        sunrise_dec, sunset_dec (ore locali decimali) e, facoltativa, lat (°; negativa = emisfero sud).
#                  None o incompleto: sim["astro_used"], poi alba 6.5 e tramonto 19.5 (come il Blocco 2 v2).
#     Qualsiasi chiave mancante o non numerica (None, testo, NaN, inf, bool) ha un valore di riserva: nessuna eccezione.
#
# STRIKE ZONE
#     Di norma è depth_zone della riga, che il Blocco 2 v2 calcola già con il livello dell'acqua scelto (il Blocco 5 v2
#     glielo passa). Se il livello chiesto qui è diverso da sim["water_level_used"] (oppure la riga non ha depth_zone),
#     la zona viene ricalcolata con estimate_strike_zone del Blocco 2 v2, con lo stesso livello e la profondità massima
#     sim["max_depth_used_m"]. Senza Blocco 2 nello stesso file si usa una fascia di riserva per il livello
#     (B3_PARAMS["zone_fallback"], copiata dalle fasce del Blocco 2 v2). La fascia di profondità citata nel testo del
#     livello è sempre quella della strike zone.
#
# NOTE PER LA PARTE C (orchestratore)
#     * approccio = physiological_condition(...) + "\n\n" + positional_approach(...): il Blocco 5 v2 mostra la condizione
#       a parte e la toglie da "approccio" con _b5_remove_part, quindi la condizione deve comparire tale e quale.
#     * strike_zone = strike_zone_for(...) con gli stessi argomenti di positional_approach.
#
# DIPENDENZE FACOLTATIVE (nello stesso file dell'app)
#     Blocco 2 v2: estimate_strike_zone, B2_PARAMS (soglie di fronte freddo e acqua calda, lette per restare coerenti con
#     la strike zone). Blocco 1 v2: classify_biological_state (solo se sim non contiene biological_state).
#     Nomi interni con prefisso _b3_, costanti in B3_PARAMS (non PARAMS né B2_PARAMS, che sono dei Blocchi 1 e 2).
#
# Etichette delle fonti: [MISURATO] valore documentato da una fonte citata o costante fisica; [INFERENZA] dedotto da
# fatti documentati; [EURISTICA] scelta di progetto. "DA VERIFICARE" = non controllato sul testo originale.
# Nei testi per il pescatore: "stima del modello" per i valori calcolati, fonte citata per i dati, indicazioni di campo
# senza etichetta (la v2 le marcava "pratica da pescatore"), nessuna fisica presentata come certezza, nessun indice
# presentato come probabilità.
#
# Requisiti: Python 3.10+, solo libreria standard.
import math as _b3_math
import re as _b3_re


# ==============================================================================
# PARAMETRI — tutte le costanti della parte A del Blocco 3
# ==============================================================================
B3_PARAMS = {
    # --- Ossigeno disciolto (mg/L) ---------------------------------------------------------------------------------
    # Criteri EPA per le acque calde, "altri stadi" (adulti): media a 30 giorni 5.5, media a 7 giorni dei minimi
    # giornalieri 4.0, minimo di 1 giorno 3.0 mg/L. US EPA (1986), Ambient Water Quality Criteria for Dissolved Oxygen
    # (Freshwater), EPA 440/5-86-003; valori come riportati nel Blocco 2 v2 dalla scheda EPA "Parameter factsheet:
    # dissolved oxygen" (2021). [MISURATO: criteri pubblicati]
    "do_epa_30d_mean_mg_l": 5.5,
    "do_epa_7d_min_mg_l": 4.0,
    "do_epa_1d_min_mg_l": 3.0,
    # Da qui in su il testo non segnala limiti: stessa soglia da cui il Blocco 2 v2 non riduce più l'indice
    # (ox_full_mg_l). I criteri EPA sono medie su più giorni, qui applicati a un valore orario stimato. [INFERENZA]
    "do_ok_mg_l": 5.0,
    # Sotto questo valore il testo segnala stress: la media a 7 giorni dei minimi giornalieri EPA. [INFERENZA]
    "do_stress_mg_l": 4.0,
    # Sotto questa temperatura dell'acqua, °C, il testo ricorda che l'ossigeno si scioglie di più in acqua fredda.
    # A 10 °C la saturazione in acqua dolce a 1 atm è circa 11.3 mg/L (Benson & Krause 1984, la formula usata dal
    # Blocco 1 v2). [EURISTICA la soglia; MISURATO il valore di saturazione]
    "do_cold_solubility_c": 10.0,
    # do_limit del Blocco 2 (fattore 0.1-1 sull'indice) viene citato nel testo solo se è sotto questo valore. [EURISTICA]
    "do_limit_note_below": 0.995,

    # --- Temperatura dell'acqua --------------------------------------------------------------------------------------
    # Errore tipico della temperatura del modello, °C: RMSE mensile 2.45 °C contro le misure ILEC del Lago Trasimeno
    # (test B11 del Blocco 1 v2; un solo lago e un clima medio ricostruito), arrotondato. [MISURATO, validazione limitata]
    "temp_model_error_c": 2.5,

    # --- Pressione ---------------------------------------------------------------------------------------------------
    # Pressione di 1 m d'acqua dolce: rho * g * 1 m = 1000 kg/m³ x 9.81 m/s² x 1 m = 9810 Pa = 98.1 hPa. [MISURATO]
    "water_rho_kg_m3": 1000.0,
    "gravity_m_s2": 9.81,
    # Variazione in 12 h sotto cui la pressione è "stabile", hPa: centro del termine di salita in score_pressure del
    # Blocco 2 v2 (press_trend_center_hpa). [EURISTICA]
    "press_stable_12h_hpa": 1.0,
    # Variazione in 12 h da cui la pressione è "marcata" e si cita la pratica dei pescatori, hPa: scala dello stesso
    # termine (press_trend_scale_hpa). [EURISTICA]
    "press_marked_12h_hpa": 3.0,
    # Le stesse soglie in 3 h, usate solo se manca la variazione a 12 h, hPa. [EURISTICA]
    "press_stable_3h_hpa": 0.5,
    "press_marked_3h_hpa": 1.5,
    # Intervallo plausibile della pressione al livello del mare, hPa (come Blocchi 1 e 2). [EURISTICA]
    "press_valid_range_hpa": (850.0, 1090.0),
    # Fonte citata nel testo: Lennox R.J., Alós J., Arlinghaus R., Horodysky A., Klefoth T., Monk C.T., Cooke S.J.
    # (2017), What makes fish vulnerable to capture by hooks? A conceptual framework and a review of key determinants,
    # Fish and Fisheries 18(5):986-1010, doi:10.1111/faf.12219 (riferimento controllato il 29/10/2026 sul catalogo
    # dell'Università delle Isole Baleari). Nel testo della rassegna: nessun consenso sull'effetto della pressione;
    # l'unico test diretto citato (luccio, Kuparinen et al. 2010: DA VERIFICARE sull'originale) non trova relazione con
    # le catture; le variazioni barometriche sono piccole rispetto a quelle idrostatiche dei movimenti verticali.
    # [MISURATO, letto tramite riassunto del PDF]
    "press_ref_text": "Lennox et al. 2017",

    # --- Trend termico (°C) ------------------------------------------------------------------------------------------
    # |Δ72h| sotto cui l'acqua è "stabile". [EURISTICA]
    "trend72_stable_c": 0.5,
    # |Δ72h| da cui la variazione è "rapida": scala della tanh in trend_multiplier del Blocco 2 v2 (trend_scale_c). [EURISTICA]
    "trend72_fast_c": 1.5,
    # |Δ14gg| sotto cui l'acqua è "stabile": la stessa soglia con cui il Blocco 1 v2 cita il trend a 14 giorni
    # (bio_macro_note_c). [EURISTICA]
    "trend14_stable_c": 1.0,
    # trend_mult del Blocco 2 viene citato nel testo se si scosta da 1 almeno di questo valore. [EURISTICA]
    "trend_mult_note_tol": 0.01,

    # --- Posizionamento ----------------------------------------------------------------------------------------------
    # Sotto questa temperatura dell'acqua, °C, l'indicazione "sponde a nord, esposte a sud" (più sole). [EURISTICA,
    # requisito del progetto]
    "pos_cold_c": 14.0,
    # Fronte freddo: Δ72h <= -0.9 °C con acqua sotto 22 °C. Copie di zone_front_micro_c e zone_front_max_t_c del Blocco
    # 2 v2: se B2_PARAMS è nello stesso file si leggono da lì, così il testo segue la strike zone. [EURISTICA]
    "pos_front_micro_c": -0.9,
    "pos_front_max_t_c": 22.0,
    # Acqua calda con ossigeno basso: T > 28 °C e DO < 4 mg/L. Copie di zone_hot_c e zone_low_do_mg_l del Blocco 2 v2
    # (lette da B2_PARAMS se presente). Sopra 28 °C anche con ossigeno normale il testo parla di ombra e acqua più
    # fresca nelle ore di sole, in linea con lo stato "caldo elevato" del Blocco 1 v2 (bio_t_hot_c = 30 °C). [EURISTICA]
    "pos_hot_c": 28.0,
    "pos_low_do_mg_l": 4.0,
    # Acqua invernale: sotto 9 °C la strike zone del Blocco 2 v2 va sulle buche profonde (zone_cold_c, letta da
    # B2_PARAMS se presente) e il testo del livello parla di pesci poco mobili vicino al fondo. [EURISTICA]
    "pos_winter_c": 9.0,
    # Fascia della strike zone che inizia almeno a questa profondità, m: "profonda" per il testo stagionale. [EURISTICA]
    "pos_deep_band_m": 3.0,
    # Emisfero assunto se astro non contiene "lat": nord (l'app è pensata per i laghi italiani). Con lat < 0 le sponde
    # più soleggiate diventano quelle a sud, esposte a nord. [INFERENZA]
    "pos_north_hemisphere": True,

    # --- Livello dell'acqua ------------------------------------------------------------------------------------------
    # Valori riconosciuti (identici ai Blocchi 2 e 5). [EURISTICA]
    "levels": ("Stabile", "In Crescita", "In Calo"),
    # Livello della simulazione se sim non lo indica: il default di run_pro_simulation del Blocco 2 v2. [INFERENZA]
    "level_default": "Stabile",
    # Fasce di riserva, usate solo se estimate_strike_zone del Blocco 2 v2 non è nello stesso file: copiate dalle fasce
    # "unknown", "calo_default" e "crescita_default" di B2_PARAMS["zone_bands"] (stesso formato del testo). [EURISTICA]
    "zone_fallback": {
        "Stabile": "Bordi delle coperture e primo scalino (1.0m - 3.0m)",
        "In Calo": "Drop-off e punte esterne, bocche dei canali di drenaggio (1.5m - 3.5m)",
        "In Crescita": "Zone appena allagate: erba, cespugli e canneti sommersi (0.3m - 1.2m)",
    },

    # --- Astronomia di riserva (ore locali decimali): sim_default_sunrise_h / sim_default_sunset_h del Blocco 2 v2 ----
    "default_sunrise_h": 6.5,
    "default_sunset_h": 19.5,

    # --- Testi di riserva ---------------------------------------------------------------------------------------------
    # Stato biologico se sim non lo contiene e non si può calcolare (stesso testo del Blocco 2 v2). [EURISTICA]
    "bio_state_default": "Stato non determinato.",
}


# ==============================================================================
# UTILITÀ
# ==============================================================================
def _b3_num(value, default=None):
    """Numero finito come float, altrimenti `default` (None, bool, testo non numerico, NaN, inf, altri tipi)."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        x = float(value)
    elif isinstance(value, str):
        try:
            x = float(value.strip().replace(",", "."))
        except ValueError:
            return default
    else:
        return default
    return x if _b3_math.isfinite(x) else default


def _b3_dict(value):
    return value if isinstance(value, dict) else {}


def _b3_one_line(value):
    """Testo su una sola riga (spazi compattati); "" se non è una stringa."""
    return " ".join(value.split()) if isinstance(value, str) else ""


def _b3_signed(x):
    """Numero con segno e un decimale, senza "-0.0"."""
    v = round(x, 1)
    if v == 0:
        v = 0.0
    return "%+.1f" % v


def _b3_b2(key, default):
    """Soglia letta da B2_PARAMS (Blocco 2 v2 nello stesso file) se c'è ed è numerica, altrimenti `default`."""
    b2 = globals().get("B2_PARAMS")
    if isinstance(b2, dict):
        v = _b3_num(b2.get(key))
        if v is not None:
            return v
    return default


def _b3_hour(row):
    """Ora della riga 0-24: campo hour, poi time_label "HH:MM"; None se non si ricava."""
    h = _b3_num(row.get("hour"))
    if h is not None:
        return h % 24.0
    label = row.get("time_label")
    if isinstance(label, str):
        m = _b3_re.match(r"\s*(\d{1,2})(?::(\d{2}))?", label)
        if m:
            return (int(m.group(1)) + (int(m.group(2)) / 60.0 if m.group(2) else 0.0)) % 24.0
    return None


def _b3_time_label(row):
    label = _b3_one_line(row.get("time_label"))
    if label:
        return label
    h = _b3_hour(row)
    if h is None:
        return ""
    total = int(round(h * 60.0)) % 1440
    return "%02d:%02d" % divmod(total, 60)


def _b3_water_temp(row):
    t = _b3_num(row.get("water_temp_used"))
    return t if t is not None else _b3_num(row.get("water_temp"))


def _b3_do(row):
    """Ossigeno disciolto, mg/L: do_used_mg_l, poi do_actual_mg_l, poi do_sat_mg_l x do_saturation_index; None se ignoto."""
    for key in ("do_used_mg_l", "do_actual_mg_l"):
        v = _b3_num(row.get(key))
        if v is not None and v >= 0.0:
            return v
    sat = _b3_num(row.get("do_sat_mg_l"))
    idx = _b3_num(row.get("do_saturation_index"))
    if sat is not None and idx is not None and sat > 0.0 and idx >= 0.0:
        return sat * idx
    return None


def _b3_do_sat(row):
    """
    Saturazione dell'ossigeno, mg/L, alla temperatura usata per la riga. Con la sonda il Blocco 2 v2 ricalcola
    do_used_mg_l alla temperatura della sonda tenendo lo stesso rapporto reale/saturazione del modello, ma lascia
    do_sat_mg_l alla temperatura del modello: la saturazione coerente è do_sat_mg_l x do_used_mg_l / do_actual_mg_l.
    """
    sat = _b3_num(row.get("do_sat_mg_l"))
    if sat is None or sat <= 0.0:
        return None
    used, actual = _b3_num(row.get("do_used_mg_l")), _b3_num(row.get("do_actual_mg_l"))
    if used is not None and actual is not None and used >= 0.0 and actual > 0.0:
        return sat * used / actual
    return sat


def _b3_micro(sim):
    v = _b3_num(sim.get("micro_trend_72h"))
    return v if v is not None else _b3_num(sim.get("thermal_trend_3d"))


def _b3_macro(sim):
    return _b3_num(sim.get("macro_trend_14d"))


def _b3_max_depth(sim):
    d = _b3_num(sim.get("max_depth_used_m"))
    return d if d is not None and d > 0.0 else None


def _b3_level(value):
    """Livello riconosciuto (maiuscole e spazi indifferenti) oppure None."""
    key = _b3_one_line(value).casefold()
    if not key:
        return None
    for name in B3_PARAMS["levels"]:
        if key == name.casefold():
            return name
    return None


def _b3_astro(astro, sim):
    """-> (alba, tramonto, emisfero nord). Prima astro, poi sim["astro_used"], poi i valori di riserva."""
    P = B3_PARAMS
    a = _b3_dict(astro)
    used = _b3_dict(sim.get("astro_used"))
    sr = _b3_num(a.get("sunrise_dec"))
    if sr is None:
        sr = _b3_num(used.get("sunrise_dec"), P["default_sunrise_h"])
    ss = _b3_num(a.get("sunset_dec"))
    if ss is None:
        ss = _b3_num(used.get("sunset_dec"), P["default_sunset_h"])
    lat = _b3_num(a.get("lat"))
    if lat is None:
        lat = _b3_num(a.get("latitude"))
    north = bool(P["pos_north_hemisphere"]) if lat is None else lat >= 0.0
    return sr, ss, north


_B3_RE_BAND = _b3_re.compile(r"\(\s*(\d+(?:[.,]\d+)?)\s*m\s*-\s*(\d+(?:[.,]\d+)?)\s*m\s*(\+?)\s*\)\s*$")


def _b3_zone_band(zone):
    """Fascia "(lo m - hi m)" alla fine del testo della zona -> (lo, hi, oltre) oppure None."""
    if not isinstance(zone, str):
        return None
    m = _B3_RE_BAND.search(zone)
    if not m:
        return None
    lo, hi = _b3_num(m.group(1)), _b3_num(m.group(2))
    if lo is None or hi is None:
        return None
    return lo, hi, bool(m.group(3))


def _b3_band_text(band):
    lo, hi, open_end = band
    return "%.1f-%.1f m%s" % (lo, hi, " e oltre" if open_end else "")


def _b3_code_safe(text):
    """Testo dentro `codice`: niente apici inversi (chiuderebbero il blocco)."""
    return _b3_one_line(text).replace("`", "'")


# ==============================================================================
# STRIKE ZONE
# ==============================================================================
def _b3_resolve_zone(row, sim, water_level, astro):
    """
    -> dict: zone (testo), level (livello del report), level_used (livello della simulazione),
             recomputed (True se la zona è stata ricalcolata per un livello diverso), source ("riga" |
             "estimate_strike_zone" | "riserva").
    """
    P = B3_PARAMS
    row, sim = _b3_dict(row), _b3_dict(sim)
    level_used = _b3_level(sim.get("water_level_used")) or P["level_default"]
    level = _b3_level(water_level) or level_used
    zone_row = _b3_one_line(row.get("depth_zone"))
    info = {"zone": zone_row, "level": level, "level_used": level_used, "recomputed": False, "source": "riga"}
    if zone_row and level == level_used:
        return info

    zone, source = "", "riserva"
    fn = globals().get("estimate_strike_zone")
    if callable(fn):
        sr, ss, _north = _b3_astro(astro, sim)
        try:
            zone = fn(_b3_water_temp(row), _b3_do(row), _b3_num(row.get("radiation")), _b3_num(row.get("wind")),
                      _b3_hour(row), sr, ss, _b3_micro(sim), level, _b3_max_depth(sim))
        except Exception:          # un errore del Blocco 2 non deve fermare il report: si usa la fascia di riserva
            zone = ""
        zone = _b3_one_line(zone)
        if zone:
            source = "estimate_strike_zone"
    if not zone:
        zone = P["zone_fallback"].get(level) or P["zone_fallback"][P["level_default"]]
    info.update({"zone": zone, "recomputed": level != level_used, "source": source})
    return info


def strike_zone_for(row, sim, water_level, astro) -> str:
    """Strike zone del report: la stessa della prima riga di positional_approach (vedi la testa del file)."""
    return _b3_resolve_zone(row, sim, water_level, astro)["zone"]


# ==============================================================================
# 1. CONDIZIONE FISIOLOGICA
# ==============================================================================
def _b3_bio_state(row, sim):
    """biological_state della simulazione così com'è; se manca, classify_biological_state del Blocco 1 v2."""
    state = sim.get("biological_state")
    if isinstance(state, str) and state.strip():
        return state if ("\n" not in state and "\r" not in state) else _b3_one_line(state)
    fn = globals().get("classify_biological_state")
    t = _b3_water_temp(row)
    if callable(fn) and t is not None:
        try:
            out = _b3_one_line(fn(t, _b3_macro(sim), _b3_micro(sim), _b3_do(row)))
        except Exception:          # funzione di un altro blocco: un suo errore non deve fermare il report
            out = ""
        if out:
            return out
    return B3_PARAMS["bio_state_default"]


def _b3_temp_oxygen_text(row, sim):
    """Punto 1: temperatura dell'acqua all'ora indicata e ossigeno disciolto in mg/L, con le soglie EPA."""
    P = B3_PARAMS
    t = _b3_water_temp(row)
    when = _b3_time_label(row)
    when_txt = (" alle %s" % when) if when else ""
    probe = _b3_num(sim.get("probe_used"))
    if t is None:
        temp_txt = "Temperatura dell'acqua non disponibile."
    elif probe is not None:
        temp_txt = ("**Acqua %.1f °C**%s: dalla tua sonda (%.1f °C), riportata all'ora con l'andamento orario del "
                    "modello." % (t, when_txt, probe))
    else:
        temp_txt = ("**Acqua %.1f °C**%s: stima del modello termico (errore tipico circa ±%.1f °C; con una sonda il "
                    "dato è più affidabile)." % (t, when_txt, P["temp_model_error_c"]))

    do = _b3_do(row)
    if do is None:
        return temp_txt + " Ossigeno disciolto non disponibile."
    ok, stress, d1 = P["do_ok_mg_l"], P["do_stress_mg_l"], P["do_epa_1d_min_mg_l"]
    sat = _b3_do_sat(row)
    head = "Ossigeno disciolto stimato dal modello **%.1f mg/L**" % do
    if sat is not None and sat > 0.0:
        head += " (saturazione a questa temperatura: %.1f mg/L)" % sat
    if do >= ok:
        verdict = "nessun limite atteso, sopra %.1f mg/L" % ok
        if t is not None and t < P["do_cold_solubility_c"]:
            verdict += "; solubilità alta in acqua fredda"
    elif do >= stress:
        verdict = (":material/warning: attenzione: sotto %.1f mg/L l'ossigeno può cominciare a limitare l'attività "
                   "(criteri EPA 1986 per le acque calde: %.1f mg/L come media a 30 giorni, %.1f mg/L come media a 7 "
                   "giorni dei minimi giornalieri)" % (ok, P["do_epa_30d_mean_mg_l"], P["do_epa_7d_min_mg_l"]))
    else:
        verdict = (":material/warning: **stress da ossigeno basso**: sotto %.1f mg/L, la media a 7 giorni dei "
                   "minimi giornalieri dei criteri EPA 1986 per le acque calde" % stress)
        if do < d1:
            verdict += ", e sotto anche il minimo di 1 giorno (%.1f mg/L)" % d1
    text = "%s %s: %s." % (temp_txt, head, verdict)
    lim = _b3_num(row.get("do_limit"))
    if lim is not None and lim < P["do_limit_note_below"]:
        text += " Nel modello l'ossigeno moltiplica l'indice di attività per %.2f." % max(0.0, lim)
    return text


def _b3_pressure_text(row):
    """Punto 2: pressione con Δ3h e Δ12h, in forma neutra (nessun effetto dimostrato sull'attività)."""
    P = B3_PARAMS
    lo, hi = P["press_valid_range_hpa"]
    p = _b3_num(row.get("pressure"))
    if p is not None and not (lo <= p <= hi):
        p = None
    d3 = _b3_num(row.get("pressure_delta"))
    d12 = _b3_num(row.get("pressure_trend_12h"))
    if p is None and d3 is None and d12 is None:
        return "Pressione non disponibile."

    bits = []
    if p is not None:
        bits.append("%.1f hPa al livello del mare" % p)
    if d3 is not None:
        bits.append("Δ3h %s hPa" % _b3_signed(d3))
    if d12 is not None:
        bits.append("Δ12h %s hPa" % _b3_signed(d12))
    if d12 is not None:
        ref, span, stable, marked = d12, "12 h", P["press_stable_12h_hpa"], P["press_marked_12h_hpa"]
    else:
        ref, span, stable, marked = d3, "3 h", P["press_stable_3h_hpa"], P["press_marked_3h_hpa"]
    direction = ""
    if ref is not None:
        a = abs(ref)
        if a < stable:
            direction = "stabile"
        elif ref < 0.0:
            direction = "in calo marcato" if a >= marked else "in leggero calo"
        else:
            direction = "in salita marcata" if a >= marked else "in leggera salita"
    text = "Pressione " + ", ".join(bits) + ((": " + direction) if direction else "") + "."

    hpa_per_m = P["water_rho_kg_m3"] * P["gravity_m_s2"] / 100.0
    text += " Un effetto della pressione sull'attività del bass non è dimostrato (%s)" % P["press_ref_text"]
    if ref is not None and hpa_per_m > 0.0:
        cm = abs(ref) * 100.0 / hpa_per_m
        eq = "meno di 1 cm" if cm < 1.0 else "circa %d cm" % int(round(cm))
        text += (": la variazione in %s equivale a %s di profondità, perché 1 m d'acqua corrisponde a circa %.0f hPa."
                 % (span, eq, hpa_per_m))
    else:
        text += "."
    if direction == "in calo marcato":
        text += (" *Pratica da pescatore:* molti associano un calo marcato prima di un fronte a pesci più attivi; "
                 "è un'osservazione, non un dato.")
    elif direction == "in salita marcata":
        text += (" *Pratica da pescatore:* molti associano la salita dopo un fronte a pesci più passivi e legati alle "
                 "coperture; è un'osservazione, non un dato.")
    return text


def _b3_trend_text(row, sim):
    """Punto 3: trend della temperatura dell'acqua (Δ72h, Δ14gg) in una frase."""
    P = B3_PARAMS
    micro, macro = _b3_micro(sim), _b3_macro(sim)
    if micro is None and macro is None:
        return "Trend della temperatura dell'acqua non disponibile."
    bits = []
    if micro is not None:
        a = abs(micro)
        if a < P["trend72_stable_c"]:
            word = "stabile"
        else:
            word = ("in riscaldamento" if micro > 0.0 else "in raffreddamento")
            word += " rapido" if a >= P["trend72_fast_c"] else ""
        bits.append("Δ72h %s °C, %s" % (_b3_signed(micro), word))
    if macro is not None:
        if abs(macro) < P["trend14_stable_c"]:
            word = "stabile"
        else:
            word = "in riscaldamento" if macro > 0.0 else "in raffreddamento"
        bits.append("Δ14gg %s °C, %s" % (_b3_signed(macro), word))
    source = "dal modello termico"
    if _b3_num(sim.get("probe_used")) is not None:
        source += ": la sonda dà solo la temperatura di oggi"
    text = "Trend dell'acqua (%s): %s" % (source, "; ".join(bits))
    mult = _b3_num(row.get("trend_mult"))
    if mult is not None and abs(mult - 1.0) >= P["trend_mult_note_tol"]:
        text += "; nel modello la variazione recente moltiplica l'indice di attività per %.2f" % mult
    return text + "."


def physiological_condition(row, sim) -> str:
    """
    Testo "condizione" del report. Prima riga con lo stato biologico della simulazione (così come lo mostra il
    Blocco 5), poi tre punti: temperatura e ossigeno in mg/L, pressione, trend termico.
    """
    row, sim = _b3_dict(row), _b3_dict(sim)
    lines = [
        ":material/genetics: **Stato Biologico Rilevato:** *%s*" % _b3_bio_state(row, sim),
        "- " + _b3_temp_oxygen_text(row, sim),
        "- " + _b3_pressure_text(row),
        "- " + _b3_trend_text(row, sim),
    ]
    return "\n".join(lines)


# ==============================================================================
# 2. APPROCCIO POSIZIONALE
# ==============================================================================
def _b3_level_text(level, band, row, sim):
    """Livello dell'acqua: pratica da pescatore, con la stessa fascia di profondità della strike zone."""
    P = B3_PARAMS
    where = ("nella fascia %s della strike zone" % _b3_band_text(band)) if band else \
        "nella fascia della strike zone indicata sopra"
    micro, t = _b3_micro(sim), _b3_water_temp(row)
    winter = t is not None and t < _b3_b2("zone_cold_c", P["pos_winter_c"])
    if level == "In Crescita":
        return ("**Livello in crescita:** l'acqua che sale allaga erba, "
                "cespugli e canneti e porta cibo verso riva, e i pesci tendono a seguirla%s. Batti il bordo delle zone "
                "appena sommerse, soprattutto negli angoli riparati, %s."
                % (" nelle ore più calde, anche con acqua così fredda" if winter else "", where))
    if level == "In Calo":
        return ("**Livello in calo:** quando l'acqua scende i pesci "
                "lasciano i flat bassi e il fondo delle baie e si portano all'esterno delle coperture, su punte, primi "
                "drop-off e imboccature dei canali di drenaggio%s. Lavora dall'esterno verso riva %s, senza insistere "
                "sotto riva." % ("; con acqua così fredda scendono fino alle buche e ai canali più profondi"
                                 if winter else "", where))
    front_micro = _b3_b2("zone_front_micro_c", P["pos_front_micro_c"])
    front_t = _b3_b2("zone_front_max_t_c", P["pos_front_max_t_c"])
    if micro is not None and t is not None and micro <= front_micro and t < front_t:
        return ("**Livello stabile, acqua in raffreddamento** (Δ72h %s °C): dopo un calo rapido "
                "i pesci tendono a stringersi sulle coperture fitte e sui drop-off e a lasciare le sponde di caccia. "
                "Cercali %s." % (_b3_signed(micro), where))
    if winter:
        return ("**Livello stabile:** nessuno spostamento dovuto al livello; con acqua così "
                "fredda i pesci si muovono poco e restano vicino al fondo. Cercali %s." % where)
    return ("**Livello stabile:** nessuno spostamento dovuto al livello; i pesci restano sulle "
            "rotte tra le coperture e le zone di caccia vicine. Cercali %s." % where)


def _b3_season_text(row, north, band):
    """Indicazione legata alla temperatura dell'acqua (e all'ossigeno basso), come pratica da pescatore."""
    P = B3_PARAMS
    t, do = _b3_water_temp(row), _b3_do(row)
    hot = _b3_b2("zone_hot_c", P["pos_hot_c"])
    low = _b3_b2("zone_low_do_mg_l", P["pos_low_do_mg_l"])
    cold = P["pos_cold_c"]
    if t is None:
        return ("Temperatura dell'acqua non disponibile: parti dai bordi delle coperture e dal primo scalino.")
    if t > hot and do is not None and do < low:
        return ("**Acqua calda e ossigeno basso:** cerca l'acqua più ossigenata, cioè immissari "
                "e sponde battute dal vento e dall'onda, e nei laghi profondi lo strato appena sopra il termoclino; "
                "evita baie chiuse e acqua ferma.")
    if t > hot:
        return ("**Acqua sopra i %.0f °C:** nelle ore di sole cerca ombra fitta e acqua più "
                "profonda o più fresca; all'alba, al tramonto e di notte i pesci tendono a cacciare più vicino a riva."
                % hot)
    if t < cold:
        shore = "sponde a nord, esposte a sud" if north else "sponde a sud, esposte a nord"
        text = ("**Acqua sotto i %.0f °C:** nelle ore di sole prova le %s, che ricevono più "
                "sole; l'acqua bassa vicino a queste sponde si scalda per prima, soprattutto su fondali scuri o "
                "sassosi." % (cold, shore))
        if band and band[0] >= P["pos_deep_band_m"]:
            text += " Fuori da quelle ore resta sulla fascia profonda della strike zone."
    else:
        text = ("**Acqua da %.0f °C in su:** lavora i cambi di pendenza, le punte battute dal "
                "vento e i margini d'ombra delle coperture." % cold)
    if do is not None and do < low:
        text += " Con ossigeno sotto %.1f mg/L privilegia l'acqua mossa dal vento e gli immissari." % low
    return text


def positional_approach(row, sim, water_level, astro) -> str:
    """
    Parte "posizionamento" del testo "approccio": strike zone (ricalcolata se il livello dell'acqua è diverso da
    quello della simulazione), livello dell'acqua e indicazione stagionale, come pratica da pescatore.
    """
    row, sim = _b3_dict(row), _b3_dict(sim)
    info = _b3_resolve_zone(row, sim, water_level, astro)
    zone = info["zone"]
    band = _b3_zone_band(zone)
    _sr, _ss, north = _b3_astro(astro, sim)
    lines = [":material/straighten: **Strike Zone Batimetrica Primaria:** `%s`" % _b3_code_safe(zone)]
    if info["recomputed"]:
        lines.append("- *Fascia ricalcolata per il livello «%s»: la simulazione oraria era impostata su «%s».*"
                     % (info["level"], info["level_used"]))
    if info["source"] == "riserva":
        lines.append("- *Fascia di riserva: il calcolo della strike zone del Blocco 2 non è disponibile.*")
    lines.append("- " + _b3_level_text(info["level"], band, row, sim))
    lines.append("- " + _b3_season_text(row, north, band))
    lines.append("- *Le fasce di profondità sono regole da pescatore del modello, non misure sul tuo lago.*")
    return "\n".join(lines)


# ==============================================================================
# BASS ENGINE — BLOCCO 3 (v3), PARTE B DI 3: RECUPERO, SETUP CANNA E FILO, COLORI
# ==============================================================================
# Parte B del nuovo Blocco 3. Va incollata DOPO la parte A (usa le sue utilità _b3_* e aggiunge chiavi a B3_PARAMS,
# senza toccare quelle della parte A). La parte C (esche, Trophy, classe pubblica) segue.
#
# FUNZIONI PUBBLICHE (pure: nessuna rete, nessuno stato, solo libreria standard)
#     retrieve_kinetics(row, sim, fishing_pressure, goal=None) -> str
#         Velocità e cadenza del recupero per fascia di temperatura dell'acqua (< 8, 8-14, 14-28 °C; oltre 28 °C le
#         presentazioni verticali solo con ossigeno sotto 4 mg/L), un livello più lento dopo un raffreddamento di
#         almeno 1.5 °C in 72 h, poi il protocollo per la pressione di pesca (Alta / Media / Bassa).
#     gear_setup(row, torbidita, wind, fishing_pressure, water_level, goal=None) -> str
#         Prima riga: intestazione in grassetto. Canne e libbraggi come pratica corrente, fisica del filo corretta.
#     color_choice(row, torbidita, forage_base, astro, goal=None) -> str
#         Colori come scelta di contrasto e luminosità, per torbidità, luce e prede italiane.
#     goal (v3)  "Numeri" | "Trophy": righe in più per l'obiettivo (Trophy: anche un altro setup); None = testo della v2.
#
# INGRESSI
#     row               riga oraria del Blocco 2 v2 (water_temp_used, do_used_mg_l, wind, radiation, clouds, hour,
#                       time_label, torbidita_label). Chiavi mancanti o non numeriche: valori di riserva, nessuna eccezione.
#     sim               uscita di run_pro_simulation (micro_trend_72h, astro_used).
#     fishing_pressure  "Alta" | "Media" | "Bassa" (Blocco 5); altro -> "Media".
#     torbidita         "Limpida" | "Velata" | "Torbida" | "Fangosa" | "Non specificato" (anche con " (Stima)");
#                       None -> torbidita_label della riga; altro -> Velata, dichiarata come assunta.
#     wind              vento a 10 m, km/h; None -> wind della riga.
#     water_level       "Stabile" | "In Crescita" | "In Calo"; altro -> "Stabile".
#     forage_base       "Misto" | "Pesce Foraggio (Alborella / Shad)" | "Gamberi / Crostacei / Gobbio" |
#                       "Rane / Insetti / Shallow" (stringhe del Blocco 5, invariate); altro -> "Misto".
#     astro             sunrise_dec, sunset_dec (ore locali decimali); None -> alba 6.5, tramonto 19.5.
#
# NOTA PER LA PARTE C
#     Il Blocco 5 v2 mostra "recupero" senza la parte "gear_setup" (_b5_remove_part): comporre
#     recupero = retrieve_kinetics(...) + "\n\n---\n" + gear_setup(...), con gear_setup identico a quello della chiave
#     "gear_setup".
#
# Etichette delle fonti come nella parte A: [MISURATO], [INFERENZA], [EURISTICA], "DA VERIFICARE".


# ==============================================================================
# PARAMETRI DELLA PARTE B (si aggiungono a B3_PARAMS; nessuna chiave in comune con la parte A)
# ==============================================================================
B3_PARAMS.update({
    # --- Recupero: fasce di temperatura dell'acqua (°C) ---------------------------------------------------------------
    # Direzione: Hanson K.C., Cooke S.J., Suski C.D., Niezgoda G., Phelan F.J.S., Tinline R., Philipp D.P. (2007),
    # Hydrobiologia 582:243-256, doi:10.1007/s10750-006-0549-6 (PDF letto il 29/10/2026): distanza giornaliera percorsa
    # correlata positivamente con la temperatura dell'acqua (non testata statisticamente; giorni a 5.1-7.7 °C, un solo
    # lago). L'estensione all'acqua calda è un'inferenza. [INFERENZA]
    # Sotto: recupero molto lento. Nel modello del Blocco 2 v2 il consumo a 8 °C vale 0.14 dell'ottimo. [EURISTICA]
    "kin_very_slow_below_c": 8.0,
    # Sotto: recupero lento. 14 °C = light_warm_above_c del Blocco 2 v2 (da qui regime "acqua calda" della luce);
    # consumo del modello 0.32 dell'ottimo ("circa un terzo"). [EURISTICA]
    "kin_slow_below_c": 14.0,
    # Da qui in su, nel testo, il pesce è "vicino all'ottimo" con ossigeno buono: consumo del modello 0.89 a 24 °C,
    # ottimo 27.5 °C (Rice et al. 1983, nel Blocco 2 v2). [INFERENZA]
    "kin_near_opt_c": 24.0,
    "kin_opt_c": 27.5,
    # Presentazioni verticali in ombra e profondità solo con T > 28 °C e DO < 4 mg/L: stesse soglie della strike zone
    # estiva del Blocco 2 v2 (zone_hot_c, zone_low_do_mg_l, lette da B2_PARAMS se presente; copie in pos_hot_c e
    # pos_low_do_mg_l della parte A). [EURISTICA]
    # Raffreddamento recente che fa rallentare di un livello, °C in 72 h. [EURISTICA, requisito del progetto]
    "kin_cooling_micro_c": -1.5,
    # Vento da cui, in acqua tra 14 e 28 °C, si consigliano esche di reazione veloci, km/h (Blocco 3 originale). [EURISTICA]
    "kin_wind_reaction_kmh": 10.0,
    # Ore attorno ad alba e tramonto considerate "crepuscolo" per i consigli di superficie (come zone_twilight_window_h
    # del Blocco 2 v2). [EURISTICA]
    "kin_twilight_window_h": 1.5,
    # Pressione di pesca: valori riconosciuti (Blocco 5) e default. [EURISTICA]
    "kin_pressures": ("Alta", "Media", "Bassa"),
    "kin_pressure_default": "Media",
    # Fonti citate nel testo sulla pressione di pesca:
    #   Lennox et al. (2017), Fish and Fisheries 18(5):986-1010, doi:10.1111/faf.12219 (PDF letto tramite riassunto il
    #   29/10/2026): cali delle catture nel tempo comuni nelle attività ricreative (causa difficile da separare dalla
    #   stagione); l'evitamento appreso "may be gear specific"; l'effetto dei rattle non ha prove scientifiche e le
    #   frequenze sono spesso fuori dall'udito dei predatori; i rumori a bassa frequenza (ancora, catene) sono udibili.
    #   Philipp D.P., Cooke S.J., Claussen J.E., Koppelman J.B., Suski C.D., Burkett D.P. (2009), Selection for
    #   vulnerability to angling in largemouth bass, Trans. Am. Fish. Soc. 138:189-199 (riferimento e risultati da
    #   comunicato ScienceDaily del 14/04/2009, articolo non letto: DA VERIFICARE i dettagli): vulnerabilità ereditabile,
    #   linee "poco vulnerabili" sempre più difficili da catturare nelle generazioni. [MISURATO tramite fonti secondarie]
    "kin_ref_pressure": "Lennox et al. 2017",
    "kin_ref_heritable": "Philipp et al. 2009",

    # --- Setup canna e filo ------------------------------------------------------------------------------------------
    # Vento sotto cui, con acqua limpida, si passa al setup finesse, km/h (Blocco 3 originale). [EURISTICA]
    "gear_finesse_wind_kmh": 8.0,
    # Canne e libbraggi: pratica corrente dei pescatori di bass, valori del Blocco 3 originale. [EURISTICA]
    # Indici di rifrazione (luce visibile): acqua 1.33 [MISURATO]; fluorocarbon (PVDF) circa 1.42 e nylon (poliammide 6)
    # circa 1.53: valori tipici del materiale, DA VERIFICARE per le singole marche di filo. [INFERENZA]
    "gear_n_water": 1.33,
    "gear_n_fluoro": 1.42,
    "gear_n_nylon": 1.53,
    # Densità, g/cm³: fluorocarbon (PVDF) circa 1.78, nylon circa 1.14, trecciato in polietilene UHMW circa 0.97;
    # acqua dolce 1.00. Valori tipici del materiale, DA VERIFICARE per le singole marche. Nel testo compare solo l'ordine
    # (fluoro affonda più del nylon, il nylon affonda lentamente, il trecciato galleggia). [INFERENZA]
    "gear_density_fluoro": 1.78,
    "gear_density_nylon": 1.14,
    "gear_density_braid": 0.97,

    # --- Colori -------------------------------------------------------------------------------------------------------
    # Luce: radiazione da cui è "luce forte" con poche nuvole, e sotto cui è "poca luce", W/m²; copertura sotto cui il
    # cielo è "poco nuvoloso", %. Valori del Blocco 3 originale. [EURISTICA]
    "col_bright_rad_wm2": 480.0,
    "col_bright_clouds_max": 35.0,
    "col_low_light_rad_wm2": 120.0,
    "col_twilight_window_h": 1.5,
    # Fonti citate nel testo (tutte lette il 29/10/2026, salvo dove indicato):
    #   Moraga A.D., Wilson A.D.M., Cooke S.J. (2015), Does lure colour influence catch per unit effort, fish capture
    #   size and hooking injury in angled largemouth bass? Fisheries Research 172:1-6, doi:10.1016/j.fishres.2015.06.010
    #   (PDF): 119 bass, Lake Opinicon; nessun effetto del colore sulle catture per unità di sforzo; per colore singolo
    #   nessuna differenza di taglia, per categoria i colori chiari (arancio, bianco) hanno preso pesci più lunghi
    #   (349 contro 318 mm, p = 0.039). [MISURATO]
    #   Wilde G.R., Pope K.L., Durham B.W. (2003), Lure-size restrictions in recreational fisheries, Fisheries 28:18-26:
    #   quattro colori di crankbait da 89 mm, uno (firetiger) con catture più basse, effetto sulla taglia non chiaro.
    #   Risultati come riassunti da Moraga et al. 2015, originale non letto: DA VERIFICARE. [MISURATO tramite fonte secondaria]
    #   Mitchem L.D., Stanis S., Zhou M., Loew E., Epifanio J.M., Fuller R.C. (2018), Seeing red: color vision in the
    #   largemouth bass, Current Zoology 65(1):43-52, doi:10.1093/cz/zoy019 (abstract): coni singoli 535 nm, coni doppi
    #   614 nm; il modello prevede che non distingua chartreuse da bianco né verde da blu e che distingua il rosso da
    #   tutti i grigi; prove comportamentali in parte concordi, il bass usa anche il colore e non solo la luminosità. [MISURATO]
    "col_cone_nm": (535, 614),
    # Prede italiane:
    #   Marinelli A., Scalici M., Gibertini G. (2007), Diet and reproduction of largemouth bass in a recently introduced
    #   population, Lake Bracciano (Central Italy), Bull. Fr. Pêche Piscic. 385:53-68, doi:10.1051/kmae:2007005
    #   (abstract): a giugno pesci ~56 % e crostacei ~38 % della dieta, soprattutto Palaemonetes antennarius. [MISURATO]
    #   Procambarus clarkii: specie esotica invasiva di rilevanza unionale, Regolamento di esecuzione (UE) 2016/1141.
    #   [MISURATO, DA VERIFICARE sul testo del regolamento]
    #   Alborella, gobidi e giovani di persico sole (Lepomis gibbosus) come prede: requisito del progetto. [INFERENZA]
    # Stringhe di forage_base del Blocco 5 (invariate) e default. [EURISTICA]
    "col_forage_options": ("Misto", "Pesce Foraggio (Alborella / Shad)", "Gamberi / Crostacei / Gobbio",
                           "Rane / Insetti / Shallow"),
    "col_forage_default": "Misto",

    # --- Torbidità ----------------------------------------------------------------------------------------------------
    # Categorie e default come turbidity_factor del Blocco 2 v2 ("Non specificato" o valori sconosciuti = Velata
    # assunta). [EURISTICA]
    "turb_names": ("Limpida", "Velata", "Torbida", "Fangosa"),
    "turb_assumed": "Velata",
})


# ==============================================================================
# UTILITÀ DELLA PARTE B
# ==============================================================================
def _b3_pick(value, options, default):
    """Opzione uguale a `value` senza distinzione di maiuscole e spazi, altrimenti `default`."""
    key = _b3_one_line(value).casefold()
    for name in options:
        if key == name.casefold():
            return name
    return default


def _b3_pressure_level(value):
    P = B3_PARAMS
    return _b3_pick(value, P["kin_pressures"], P["kin_pressure_default"])


def _b3_turbidity(label):
    """-> (categoria, assunta). " (Stima)", "Non specificato" e valori sconosciuti -> Velata assunta."""
    P = B3_PARAMS
    text = _b3_one_line(label)
    estimated = "(stima)" in text.casefold()
    core = text.casefold().replace("(stima)", "").strip()
    for name in P["turb_names"]:
        if core == name.casefold():
            return name, estimated
    return P["turb_assumed"], True


def _b3_forage(value):
    """Stringa di forage_base del Blocco 5; ricerca per parola chiave se non è identica; altrimenti "Misto"."""
    P = B3_PARAMS
    options = P["col_forage_options"]
    exact = _b3_pick(value, options, None)
    if exact:
        return exact
    key = _b3_one_line(value).casefold()
    if any(k in key for k in ("gamber", "crostac", "gobbi", "gobid", "craw")):
        return options[2]
    if any(k in key for k in ("rane", "rana", "insett", "shallow")):
        return options[3]
    if any(k in key for k in ("foraggio", "alborell", "pesce")):
        return options[1]
    return P["col_forage_default"]


def _b3_circ_h(dh):
    """Differenza oraria sul quadrante di 24 h, in [-12, 12)."""
    return (dh + 12.0) % 24.0 - 12.0


def _b3_is_twilight(hour, sunrise, sunset, window):
    if hour is None or sunrise is None or sunset is None:
        return False
    return min(abs(_b3_circ_h(hour - sunrise)), abs(_b3_circ_h(hour - sunset))) <= window


# ==============================================================================
# 1. CINETICA DI RECUPERO
# ==============================================================================
_B3_KIN_ORDER = ("molto_lento", "lento", "normale")


def _b3_kinetics_band(row, sim):
    """
    -> dict: base (fascia per la sola temperatura), band (fascia usata), slowed (True se rallentata dal
    raffreddamento), t, do, micro. Fasce: "molto_lento", "lento", "normale", "verticale", "ignoto".
    """
    P = B3_PARAMS
    t, do, micro = _b3_water_temp(row), _b3_do(row), _b3_micro(sim)
    hot = _b3_b2("zone_hot_c", P["pos_hot_c"])
    low = _b3_b2("zone_low_do_mg_l", P["pos_low_do_mg_l"])
    if t is None:
        base = "ignoto"
    elif t < P["kin_very_slow_below_c"]:
        base = "molto_lento"
    elif t < P["kin_slow_below_c"]:
        base = "lento"
    elif t > hot and do is not None and do < low:
        base = "verticale"
    else:
        base = "normale"
    band, slowed = base, False
    if micro is not None and micro <= P["kin_cooling_micro_c"] and base in ("lento", "normale"):
        band = _B3_KIN_ORDER[_B3_KIN_ORDER.index(base) - 1]
        slowed = True
    return {"base": base, "band": band, "slowed": slowed, "t": t, "do": do, "micro": micro}


_B3_KIN_TITLES = {
    "molto_lento": "Recupero molto lento",
    "lento": "Recupero lento e regolare",
    "normale": "Recupero normale o veloce",
    "verticale": "Presentazioni verticali in ombra e profondità",
    "ignoto": "Recupero da adattare",
}


def _b3_kinetics_lines(info, row, sim):
    """Righe dell'elenco per la fascia scelta: prima il perché (dato o inferenza), poi i consigli pratici."""
    P = B3_PARAMS
    band, t, do = info["band"], info["t"], info["do"]
    tip = "*Consiglio pratico:* "
    if band == "molto_lento":
        return [
            "Perché: in acqua fredda il bass si sposta poco; in un lago dell'Ontario la distanza percorsa ogni giorno "
            "cresceva con la temperatura dell'acqua (Hanson et al. 2007). L'esca deve restare a lungo nella zona.",
            tip + "gomma o jig trascinati sul fondo a strappi corti di 5-10 cm, con pause di 6-12 secondi a filo "
            "semiteso.",
            tip + "jerkbait sospesa con due colpi di vetta corti e pause di 8-15 secondi, senza farla avanzare.",
        ]
    if band == "lento":
        return [
            "Perché: tra %.0f e %.0f °C il pesce insegue, ma per poco; nel modello del Blocco 2 il consumo a %.0f °C è "
            "circa un terzo di quello all'ottimo (Rice et al. 1983)."
            % (P["kin_very_slow_below_c"], P["kin_slow_below_c"], P["kin_slow_below_c"]),
            tip + "lama, spinnerbait o chatterbait in slow-rolling vicino al fondo o sul bordo degli erbai, appena "
            "sopra la velocità a cui la paletta smette di girare.",
            tip + "crankbait che tocca sassi e rami; dopo l'urto ferma la manovella 1-2 secondi e lasciala risalire.",
            tip + "jerkbait con pause di 3-6 secondi.",
        ]
    if band == "verticale":
        low = _b3_b2("zone_low_do_mg_l", P["pos_low_do_mg_l"])
        sr, ss, _north = _b3_astro(None, sim)
        return [
            "Perché: con acqua sopra %.0f °C e ossigeno sotto %.1f mg/L (stima del modello; sotto %.1f mg/L i criteri "
            "EPA 1986 per le acque calde indicano stress) il pesce si muove poco e cerca acqua più fresca e ossigenata."
            % (_b3_b2("zone_hot_c", P["pos_hot_c"]), low, P["do_stress_mg_l"]),
            tip + "nelle ore di luce esca che cade in verticale dentro l'ombra fitta (punching, drop shot, jig), "
            "pochi spostamenti orizzontali e qualche secondo di sosta sul fondo.",
            tip + "all'alba, al tramonto e di notte superficie o sottosuperficie a cadenza lenta e continua.",
        ]
    if band == "ignoto":
        return [tip + "temperatura dell'acqua non disponibile: parti con un recupero medio e rallenta se non hai tocchi."]

    # normale (14-28 °C, oppure oltre 28 °C con ossigeno non basso)
    wind = _b3_num(row.get("wind"))
    hour = _b3_hour(row)
    sr, ss, _north = _b3_astro(None, sim)
    hot = _b3_b2("zone_hot_c", P["pos_hot_c"])
    low = _b3_b2("zone_low_do_mg_l", P["pos_low_do_mg_l"])
    if t is not None and t >= P["kin_near_opt_c"] and (do is None or do >= low):
        why = ("Perché: con acqua a %.1f °C e ossigeno non limitante il pesce è vicino all'ottimo di alimentazione del "
               "modello (%.1f °C, Rice et al. 1983): può inseguire esche veloci." % (t, P["kin_opt_c"]))
    else:
        why = ("Perché: tra %.0f e %.0f °C il consumo del modello va da circa un terzo al massimo (Rice et al. 1983): "
               "il pesce è attivo e insegue anche esche veloci." % (P["kin_slow_below_c"], hot))
    lines = [why]
    if wind is not None and wind >= P["kin_wind_reaction_kmh"]:
        lines.append(tip + "con vento e onda esche di reazione a velocità sostenuta, alternando 4-5 giri rapidi di "
                     "manovella a uno stop di mezzo secondo.")
    else:
        lines.append(tip + "con poco vento nuoto regolare a mezz'acqua (swimbait, softbait) o caduta libera di esche "
                     "senza piombo vicino ai margini d'ombra, con piccoli colpi di vetta durante la discesa.")
    lines.append(tip + "nelle coperture, se il tocco non arriva nei primi secondi di caduta o ai primi due inviti sul "
                 "fondo, recupera e rilancia; cambia velocità ogni pochi lanci finché trovi quella che dà tocchi.")
    if _b3_is_twilight(hour, sr, ss, P["kin_twilight_window_h"]):
        lines.append(tip + "all'alba e al tramonto esche di superficie (walk-the-dog, popper) a cadenza continua.")
    if t is not None and t > hot:
        lines.append(tip + "sopra %.0f °C, nelle ore di sole forte, lavora più vicino all'ombra." % hot)
    return lines


def _b3_pressure_protocol(level):
    P = B3_PARAMS
    if level == "Alta":
        return ("**Pressione di pesca alta:** le catture tendono a calare dove gli stessi pesci vengono pescati spesso, "
                "e l'evitamento appreso può riguardare soprattutto il tipo di esca o di attrezzo già visto (%s); nel "
                "largemouth la vulnerabilità all'amo è in parte ereditaria (%s). *Consigli pratici:* cambia tipo di "
                "esca e di presentazione rispetto a quelli più usati sul lago, lancia più lontano e fai arrivare "
                "l'esca alla zona senza tonfi; evita i rumori di barca a bassa frequenza (ancora, catene), che i "
                "pesci sentono. Togliere i rattle è una scelta di molti pescatori: il loro effetto non è dimostrato."
                % (P["kin_ref_pressure"], P["kin_ref_heritable"]))
    if level == "Bassa":
        return ("**Pressione di pesca bassa:** pesci poco abituati alle esche. Usa esche di "
                "ricerca che coprono molta acqua in fretta (spinnerbait, chatterbait, crankbait) e rallenta solo dove "
                "trovi pesce.")
    return ("**Pressione di pesca media:** una prima passata veloce con un'esca di ricerca sui "
            "punti migliori, poi una seconda passata lenta con una gomma sugli stessi punti.")


def _b3_goal_kinetics(goal, band):
    """Righe in più per l'obiettivo del report (v3): "Numeri" o "Trophy"; nessuna per gli altri valori."""
    P = B3_PARAMS
    if goal == "Numeri":
        return ["**Per fare numero:** esche di misura media e molti lanci; se in %d minuti non "
                "hai tocchi cambia zona invece di insistere: i pesci attivi si trovano spostandosi."
                % P["goal_numbers_move_min"]]
    if goal != "Trophy":
        return []
    lines = ["**Per i pesci grandi:** i consigli sopra valgono per le esche di ricerca; con le "
             "esche grandi meno lanci e più tempo su ogni punto buono, recupero più lento e costante, senza strappi, "
             "e pause più lunghe con le esche che restano sospese."]
    if band in ("lento", "normale"):
        lines.append("**Glide bait e swimbait snodate:** due o tre giri lenti di manovella e una "
                     "pausa; se un pesce segue l'esca senza attaccare, prova una pausa improvvisa o un cambio di "
                     "direzione invece di accelerare.")
    return lines


def retrieve_kinetics(row, sim, fishing_pressure, goal=None) -> str:
    """
    Testo della cinetica di recupero: intestazione in grassetto con la fascia, elenco (perché + consigli pratici,
    più le righe dell'obiettivo `goal`), poi il protocollo per la pressione di pesca. Fasce e fonti nella testa del file.
    """
    P = B3_PARAMS
    row, sim = _b3_dict(row), _b3_dict(sim)
    info = _b3_kinetics_band(row, sim)
    when = _b3_time_label(row)
    bits = []
    if info["t"] is not None:
        bits.append("acqua %.1f °C" % info["t"])
    if info["band"] == "verticale" and info["do"] is not None:
        bits.append("ossigeno %.1f mg/L" % info["do"])
    if when:
        bits.append("ore %s" % when)
    head = "**%s**" % _B3_KIN_TITLES[info["band"]] + ((" (" + ", ".join(bits) + ")") if bits else "")
    lines = [head]
    if info["slowed"]:
        lines.append("- Raffreddamento di %.1f °C in 72 h (dal modello termico): un livello più lento di quello che "
                     "indicherebbe la sola temperatura." % abs(info["micro"]))
    elif info["base"] == "molto_lento" and info["micro"] is not None and info["micro"] <= P["kin_cooling_micro_c"]:
        lines.append("- Raffreddamento di %.1f °C in 72 h (dal modello termico): il recupero è già al minimo, allunga "
                     "le pause." % abs(info["micro"]))
    lines.extend("- " + s for s in _b3_kinetics_lines(info, row, sim))
    lines.extend("- " + s for s in _b3_goal_kinetics(goal, info["band"]))
    return "\n".join(lines) + "\n\n" + _b3_pressure_protocol(_b3_pressure_level(fishing_pressure))


# ==============================================================================
# 2. SETUP CANNA E FILO
# ==============================================================================
def _b3_line_physics():
    """Fisica del filo, corretta: il fluorocarbon riduce il contrasto ottico, non lo elimina; ordine di galleggiamento."""
    P = B3_PARAMS
    return ("**Filo, cosa sapere:** il fluorocarbon riduce il contrasto ottico del filo in acqua ma non lo rende "
            "invisibile: il suo indice di rifrazione (circa %.2f) è più vicino a quello dell'acqua (%.2f) di quello del "
            "nylon (circa %.2f); valori indicativi del materiale. Il fluorocarbon affonda più del nylon, anche il nylon "
            "affonda lentamente, il trecciato galleggia."
            % (P["gear_n_fluoro"], P["gear_n_water"], P["gear_n_nylon"]))


def _b3_topwater_line():
    return ("**Esche di superficie:** nylon o trecciato. Il fluorocarbon, che affonda, tira giù la testa dell'esca e "
            "ne peggiora il nuoto.")


def gear_setup(row, torbidita, wind, fishing_pressure, water_level, goal=None) -> str:
    """
    Setup canna e filo. Prima riga: intestazione in grassetto; poi l'elenco (canne e libbraggi: pratica corrente). goal "Trophy": setup da esche grandi. Altrimenti finesse con acqua limpida e poco vento (o
    pressione di pesca alta); heavy cover con acqua torbida o fangosa o livello in crescita; altrimenti setup versatile.
    """
    P = B3_PARAMS
    row = _b3_dict(row)
    turb, assumed = _b3_turbidity(torbidita if torbidita is not None else row.get("torbidita_label"))
    w = _b3_num(wind)
    if w is None:
        w = _b3_num(row.get("wind"))
    if w is not None:
        w = max(0.0, w)
    pressure = _b3_pressure_level(fishing_pressure)
    level = _b3_level(water_level) or P["level_default"]

    turb_txt = "acqua %s%s" % (turb.lower(), " (assunta)" if assumed else "")
    wind_txt = (", vento %.0f km/h" % w) if w is not None else ""
    calm = w is not None and w < P["gear_finesse_wind_kmh"]
    if goal == "Trophy":
        title = "Setup da esche grandi (casting)"
        items = [
            "**Swimbait grandi e glide bait (da 2 oz, circa 60 g, in su):** casting 7'6\"-8'0\" H o XH, azione "
            "moderate-fast, con fluorocarbon 20-25 lb (0.40-0.45 mm) o trecciato 50-65 lb con terminale in "
            "fluorocarbon.",
            "**Jig 1/2-3/4 oz e texas pesanti:** casting 7'2\"-7'4\" H fast con fluorocarbon 16-20 lb "
            "(0.33-0.37 mm).",
        ]
        if turb == "Limpida":
            items.append("**Acqua limpida:** anche qui non scendere sotto %d lb di fluorocarbon (circa 0.28 mm): vicino "
                         "agli ostacoli un pesce oltre i 2 kg rompe facilmente un filo più sottile." % P["goal_trophy_min_lb"])
        items.append("**Rilascio:** tieni il pesce fuori dall'acqua il meno possibile e sorreggilo in orizzontale con "
                     "una mano sotto il ventre, invece di appenderlo alla sola mascella.")
    elif turb == "Limpida" and (calm or pressure == "Alta"):
        title = "Setup finesse (spinning)"
        items = [
            "**Canna:** spinning 6'8\"-7'1\", potenza L o ML, azione fast o extra-fast con vetta sensibile.",
            "**Filo:** trecciato PE 0.6-0.8 (10-14 lb) con un terminale lungo 2.5-3.5 metri in fluorocarbon 5-8 lb "
            "(0.18-0.23 mm), nodo FG o Alberto; in alternativa fluorocarbon in bobina 5-8 lb."
            + (" Con pressione di pesca alta resta sui diametri più sottili." if pressure == "Alta" else ""),
        ]
    elif turb in ("Torbida", "Fangosa") or level == "In Crescita":
        title = "Setup coperture fitte (casting)"
        items = [
            "**Canna:** casting 7'0\"-7'4\", potenza MH o H, azione fast per jig e texas nelle coperture; 7'2\" "
            "moderate-fast in fibra di vetro o composito per chatterbait e squarebill.",
            "**Filo:** fluorocarbon 16-20 lb (0.33-0.37 mm) dove il filo sfrega su legni e sassi; trecciato 40-65 lb "
            "diretto su erbai fitti e rane. In acqua torbida la visibilità del filo conta poco.",
        ]
    else:
        title = "Setup versatile (casting)"
        items = [
            "**Esche in movimento:** casting 7'0\"-7'2\" moderate-fast, che assorbe le testate e tiene le ancorette, "
            "con fluorocarbon 12-14 lb (0.28-0.31 mm).",
            "**Esche sul fondo (jig, texas):** casting 7'1\"-7'3\" fast, con fluorocarbon 14-16 lb (0.31-0.33 mm).",
        ]
        if pressure == "Alta":
            items.append("**Pressione di pesca alta:** su entrambe scendi di circa 2 lb.")
    if level == "In Calo":
        items.append("**Livello in calo:** per i drop-off più profondi (carolina rig, football jig, crankbait medio) "
                     "una casting 7'2\"-7'4\" MH fast con fluorocarbon 14-16 lb.")
    items.append(_b3_topwater_line())
    items.append(_b3_line_physics())
    lines = ["**%s · %s%s**" % (title, turb_txt, wind_txt)]
    lines.extend("- " + s for s in items)
    return "\n".join(lines)


# ==============================================================================
# 3. COLORI
# ==============================================================================
def _b3_color_evidence():
    """
    Cosa dicono i dati sul colore e sulla visione del largemouth. Dalla v3 NON compare nel report (troppo lungo per chi
    è in barca): resta come appunto, con le fonti, su cui si basano le regole di _b3_color_clarity e _b3_color_trophy.
    """
    lo, hi = B3_PARAMS["col_cone_nm"]
    return ("**Cosa dicono i dati:** il colore serve a rendere l'esca visibile, non garantisce catture. In una prova sul "
            "largemouth il colore non ha cambiato le catture per unità di sforzo e ha cambiato poco la taglia: le esche "
            "chiare hanno preso pesci in media di circa 3 cm più lunghi (Moraga et al. 2015); in una prova con "
            "crankbait un colore su quattro ha catturato meno degli altri (Wilde et al. 2003). Il largemouth ha due "
            "tipi di coni, con picchi a %d e %d nm: il modello visivo prevede che non distingua il chartreuse dal "
            "bianco né il verde dal blu, mentre distingue il rosso dai grigi; le prove di comportamento lo confermano "
            "solo in parte e mostrano che il bass usa anche il colore, non solo la luminosità (Mitchem et al. 2018)."
            % (lo, hi))


def _b3_color_clarity(turb, bright):
    if turb == "Limpida":
        if bright:
            return ("**Acqua limpida, luce forte:** toni naturali o traslucidi, che lasciano "
                    "passare la luce: Watermelon Seed, Watermelon Red Flake, Green Pumpkin, Smoke sulle gomme; livree "
                    "traslucide come Ghost Minnow sulle hardbait.")
        return ("**Acqua limpida, luce diffusa:** toni naturali pieni o perlati, che disegnano la "
                "sagoma senza riflessi forti: Green Pumpkin, Cinnamon Blue Flake sulle gomme; Pearl e livree naturali "
                "opache sulle hardbait.")
    if turb == "Velata":
        return ("**Acqua velata:** colori pieni, anche a due toni: Green Pumpkin con coda "
                "chartreuse, PB&J, Bama Bug sulle gomme; Pearl White, Chartreuse & White, Red Craw sulle hardbait; "
                "palette nichel o oro.")
    return ("**Acqua %s:** conta il contrasto. Sagoma scura (Black & Blue, Junebug, nero pieno) "
            "oppure colori molto chiari e opachi (Bone, bianco opaco, chartreuse opaco); per il modello visivo del bass "
            "chartreuse e bianco si somigliano, quindi conta soprattutto che siano chiari e opachi. Palette verniciate "
            "o color rame e oro." % turb.lower())


def _b3_color_forage(forage):
    options = B3_PARAMS["col_forage_options"]
    if forage == options[1]:
        return ("**Prede: pesce foraggio** (alborella, giovani di persico sole): dorso verde oliva o grigio, fianchi "
                "argento e ventre bianco per l'alborella, verde con riflessi bluastri e arancio per il persico sole: "
                "livree argento, Pearl, Silver Flake, Ghost Minnow, e livree verdi con accenti arancio.")
    if forage == options[2]:
        return ("**Prede: gamberi e gobidi:** il gambero della Louisiana (*Procambarus clarkii*, specie invasiva) è "
                "bruno-rossastro con chele rosse; i gamberetti d'acqua dolce (*Palaemonetes antennarius*, a giugno "
                "gran parte della dieta del bass nel Lago di Bracciano, Marinelli et al. 2007) sono quasi traslucidi; "
                "i gobidi sono bruni e maculati. Colori: Green Pumpkin, Brown, Dark Cinnamon, Red Craw, con accenti "
                "arancio o rossi (il rosso è un colore che il bass distingue dai grigi); traslucidi chiari per i "
                "gamberetti.")
    if forage == options[3]:
        return ("**Prede: rane, insetti, sottoriva:** rane verdi con pancia chiara, giovani di persico sole, insetti "
                "scuri: Watermelon, Green Pumpkin con chartreuse, nero e giallo per le esche di superficie, nero e "
                "marrone per le imitazioni di insetti.")
    return ("**Prede miste:** colori chiari (bianco perla, argento) sulle esche a mezz'acqua, naturali o scuri (Green "
            "Pumpkin, Black & Blue, PB&J) su quelle a contatto col fondo.")


def _b3_color_trophy():
    """Colori per i pesci grandi (v3): la misura conta più del colore, con le stesse fonti di _b3_color_evidence."""
    return ("**Per i pesci grandi:** conta più la misura dell'esca del colore: nella prova di %s la misura ha cambiato "
            "la lunghezza dei bass catturati e il colore no; in quella di Moraga et al. 2015 le esche chiare hanno "
            "preso pesci in media di circa 3 cm più lunghi, una differenza piccola. *Consiglio pratico:* sulle esche "
            "grandi livree realistiche della preda principale, indicate qui sotto." % B3_PARAMS["trophy_ref_size"])


def color_choice(row, torbidita, forage_base, astro, goal=None) -> str:
    """
    Colori come scelta di contrasto e luminosità. Prima riga: intestazione in grassetto con acqua e luce; poi la regola
    per torbidità e luce, la nota per la poca luce, con goal "Trophy" la nota sui pesci grandi, infine le prede
    italiane. I dati sulla visione del largemouth (_b3_color_evidence) non vengono mostrati dalla v3.
    """
    P = B3_PARAMS
    row = _b3_dict(row)
    turb, assumed = _b3_turbidity(torbidita if torbidita is not None else row.get("torbidita_label"))
    forage = _b3_forage(forage_base)
    rad = _b3_num(row.get("radiation"))
    clouds = _b3_num(row.get("clouds"))
    hour = _b3_hour(row)
    sr, ss, _north = _b3_astro(astro, {})
    twilight = _b3_is_twilight(hour, sr, ss, P["col_twilight_window_h"])
    low_light = twilight or (rad is not None and rad < P["col_low_light_rad_wm2"])
    bright = (not low_light and rad is not None and rad >= P["col_bright_rad_wm2"]
              and clouds is not None and clouds < P["col_bright_clouds_max"])
    light_txt = "poca luce" if low_light else ("luce forte" if bright else
                                               ("luce diffusa" if rad is not None else "luce non nota"))
    when = _b3_time_label(row)
    head = "**Colori: contrasto e luminosità · acqua %s%s · %s%s**" % (
        turb.lower(), " (assunta)" if assumed else "", light_txt, (" alle " + when) if when else "")
    items = [_b3_color_clarity(turb, bright)]
    if low_light:
        items.append("**Poca luce** (alba, tramonto o cielo scuro): visto da sotto contro il "
                     "cielo, un'esca di superficie si legge meglio come sagoma: scura piena oppure con pancia chiara "
                     "opaca (Bone).")
    if goal == "Trophy":
        items.append(_b3_color_trophy())
    items.append(_b3_color_forage(forage))
    return "\n".join([head] + ["- " + s for s in items])


# ==============================================================================
# BASS ENGINE — BLOCCO 3 (v3), PARTE C DI 3: ESCHE, STRATEGIA TROPHY, CLASSE PUBBLICA
# ==============================================================================
# Parte C del nuovo Blocco 3. Va incollata DOPO le parti A e B (usa le loro funzioni e aggiunge chiavi a B3_PARAMS).
#
# FUNZIONI PUBBLICHE (pure)
#     lure_matrix(row, sim, torbidita, forage_base, fishing_pressure, water_level) -> (primarie, secondarie)
#         Esche per preda (prede italiane) e regime: freddo/finesse (sotto 12 °C o dopo un raffreddamento di almeno
#         1.5 °C in 72 h, oppure con pressione di pesca alta), movimento lento (12-15 °C con acqua in riscaldamento),
#         attivo, estivo verticale (sopra 28 °C con ossigeno sotto 4 mg/L). Le primarie finiscono con l'override del
#         livello dell'acqua, con la stessa fascia della strike zone della parte A.
#     trophy_strategy(trophy_row, sim, fishing_pressure, water_level=None, astro=None) -> str
#         Prima riga = intestazione (il Blocco 5 la scarta). Con sim["trophy_flat"] la seconda riga dice che nessuna ora
#         si distingue e il testo non indica un picco. water_level e astro sono facoltativi (default: quelli della
#         simulazione) e servono solo a dare la stessa strike zone del report.
#
# CLASSE PUBBLICA (letta dal Blocco 5 v2 e dall'audit)
#     TacticalAdvisorV2.generate_pro_report(best_hour, trend_3d, astro, sim_results=None, water_level="Stabile",
#                                           forage_base="Misto", fishing_pressure="Media", target_mode="Entrambi") -> dict
#         Chiavi: condizione, approccio, esche_primarie, esche_secondarie, colore, recupero, strike_zone, gear_setup,
#         strategia_trophy, bio_alert, target_mode, esche, colori, velocita (tutte stringhe).
#         Invarianti su cui si basa il Blocco 5 v2:
#           approccio = condizione + "\n\n" + posizionamento;  recupero = cinetica + "\n\n---\n" + gear_setup;
#           "Numeri": strategia_trophy = "";
#           "Trophy": esche_primarie = strategia_trophy (+ "\n\n" + override del livello), esche_secondarie = ripiego
#             sulle esche "Numeri"; dalla v3 anche recupero, gear_setup e colore hanno i testi per i pesci grandi;
#           "Entrambi": esche_secondarie = secondarie + "\n\n---\n" + strategia_trophy;
#           bio_alert termina con " — " + biological_state (quello di sim_results, identico); nessun "%" accanto agli indici;
#           esche = esche_primarie + "\n\n" + esche_secondarie; colori = colore; velocita = recupero.
#         Icone: Material Symbols di Streamlit (":material/nome:") all'inizio delle righe di titolo; ogni parte di
#           bio_alert comincia con la sua icona, che il Blocco 5 tiene fuori dall'escape del Markdown (_b5_mdx_icon).
#         Ora di riferimento: best_hour, oppure sim_results["best_trophy_hour"] in modalità "Trophy" (dalla v3
#           best_hour anche in "Trophy" se la curva Trophy è piatta).
#     TacticalAdvisorV2.generate_report(sim_data, torbidita="Non specificato", spot_morphology="", water_level="Stabile",
#                                       forage_base="Misto", fishing_pressure="Media", target_mode="Entrambi", astro=None)
#         Vecchio wrapper, delega a generate_pro_report.


# ==============================================================================
# PARAMETRI DELLA PARTE C (si aggiungono a B3_PARAMS; nessuna chiave in comune con le parti A e B)
# ==============================================================================
B3_PARAMS.update({
    # --- Esche: regimi -------------------------------------------------------------------------------------------------
    # Sotto questa temperatura dell'acqua, °C: regime freddo / finesse. [EURISTICA, requisito del progetto]
    "lure_cold_below_c": 12.0,
    # Raffreddamento in 72 h che porta al regime freddo / finesse a qualunque temperatura sotto i 28 °C, °C: stesso
    # valore del rallentamento del recupero (kin_cooling_micro_c della parte B). [EURISTICA]
    "lure_cooling_micro_c": -1.5,
    # Tra 12 e 15 °C con acqua in riscaldamento (Δ72h > 0): esche di movimento lento. Miranda L.E., Muncy R.J. (1987),
    # Spawning sequence of largemouth bass, bluegill, and gizzard shad, Proc. Annu. Conf. SEAFWA 41:197-204 (abstract
    # letto il 29/10/2026): in due bacini del Mississippi il largemouth ha cominciato a deporre a fine marzo con acqua
    # vicino a 15 °C, prima le femmine più grandi. [INFERENZA]
    "lure_prespawn_hi_c": 15.0,
    "lure_prespawn_micro_min_c": 0.0,
    # Foraggio misto: vento da cui si passa alle esche di reazione e, con acqua limpida, vento sotto cui si resta in
    # finesse, km/h (valori del Blocco 3 originale). [EURISTICA]
    "lure_power_wind_kmh": 10.0,
    "lure_clear_calm_kmh": 7.0,

    # --- Strategia Trophy ----------------------------------------------------------------------------------------------
    # Fonte citata: Wilde G.R., Pope K.L., Durham B.W. (2003), Lure-size restrictions in recreational fisheries,
    # Fisheries 28(6):18-26 (abstract letto il 29/10/2026 su DigitalCommons UNL): quattro misure di esca e cinque
    # colori; la misura dell'esca ha cambiato in modo significativo la lunghezza dei bass catturati, mentre le catture
    # orarie di pesci da 305 mm in su erano basse (0-0.5 pesci/ora) e non dipendevano dalla misura; il colore non ha
    # cambiato la lunghezza. [MISURATO]
    "trophy_ref_size": "Wilde et al. 2003",
    "trophy_ref_size_mm": 305,
    # Escursione dell'indice Trophy sotto cui la curva è "piatta", punti: usata solo se sim non contiene trophy_flat
    # (stessa soglia peak_flat_span del Blocco 2 v2). [EURISTICA]
    "trophy_flat_span": 1.0,
    # prespawn_bonus del Blocco 2 v2 sopra cui il testo cita la finestra di pre-frega (bonus massimo 2.04). [EURISTICA]
    "trophy_prespawn_note_min": 1.05,
    # Minuti attorno alla finestra Trophy su cui insistere (Blocco 3 originale). [EURISTICA]
    "trophy_window_min": 45,

    # --- Report ----------------------------------------------------------------------------------------------------------
    # Modalità riconosciute e default. Il Blocco 5 v5 passa solo "Numeri" o "Trophy"; "Entrambi" resta per i vecchi
    # chiamanti (stessi testi della v2). [EURISTICA]
    "report_modes": ("Entrambi", "Numeri", "Trophy"),
    "report_mode_default": "Entrambi",
    # Obiettivi con testi propri in recupero, setup e colori (v3). [EURISTICA]
    "goals": ("Numeri", "Trophy"),
    # "Numeri": minuti senza tocchi dopo cui si cambia zona. [EURISTICA, pratica da pescatore]
    "goal_numbers_move_min": 20,
    # "Trophy": fluorocarbon minimo anche in acqua limpida, lb. [EURISTICA, pratica corrente]
    "goal_trophy_min_lb": 12,
})


# ==============================================================================
# 1. ESCHE
# ==============================================================================
def _b3_lure_regime(row, sim):
    """-> "verticale" | "freddo" | "prefrega" | "attivo" | "ignoto" (soglie nella testa della parte C)."""
    P = B3_PARAMS
    t, do, micro = _b3_water_temp(row), _b3_do(row), _b3_micro(sim)
    hot = _b3_b2("zone_hot_c", P["pos_hot_c"])
    low = _b3_b2("zone_low_do_mg_l", P["pos_low_do_mg_l"])
    if t is None:
        return "ignoto"
    if t > hot and do is not None and do < low:
        return "verticale"
    if t < P["lure_cold_below_c"] or (micro is not None and micro <= P["lure_cooling_micro_c"]):
        return "freddo"
    if t < P["lure_prespawn_hi_c"] and micro is not None and micro > P["lure_prespawn_micro_min_c"]:
        return "prefrega"
    return "attivo"


_B3_LURES = {
    # gamberi, gamberetti e gobidi
    "Gamberi / Crostacei / Gobbio": {
        "finesse": (
            "**Gamberi e gobidi, presentazioni lente sul fondo**\n"
            "- **Ned rig e neko rig:** piccolo craw galleggiante su testina a fungo (1/10-1/6 oz) o creature compatta "
            "a neko; nelle pause lunghe le chele restano alzate.\n"
            "- **Finesse football jig (1/4-3/8 oz):** gonnellino sfoltito e trailer craw piccolo, trascinato piano sui "
            "sassi.\n"
            "- **Crankbait flat-side:** nuoto stretto che urta le pietre del primo scalino."),
        "lento": (
            "**Gamberi e gobidi, movimento lento a contatto**\n"
            "- **Jig da 3/8 oz con trailer craw:** trascinato e fatto saltellare piano lungo sassi e drop-off.\n"
            "- **Crankbait medio:** recupero lento che tocca il fondo; dopo l'urto una breve sosta.\n"
            "- **Chatterbait compatta:** slow-rolling vicino al fondo, appena sopra la velocità minima della lama."),
        "attivo": (
            "**Gamberi e gobidi, contatto col fondo**\n"
            "- **Jig da 3/8-1/2 oz con trailer craw ad alte vibrazioni:** in pitching al piede dei legni o a saltelli "
            "lungo i drop-off sassosi.\n"
            "- **Texas o free rig (piombo in tungsteno 7-10 g):** creature o craw da 3.5-4\"; con il free rig l'esca "
            "plana libera dopo che il piombo tocca il fondo.\n"
            "- **Squarebill o crankbait medio:** fatto arare il fondo e sbattere su sassi e rami."),
        "secondarie": (
            ":material/refresh: **Seconda scelta (gamberi e gobidi):** shaky head con verme dritto o piccola "
            "creature lavorata sul posto, oppure chatterbait compatta in slow-rolling a contatto col fondo."),
    },
    # pesce foraggio: alborella, giovani di persico sole
    "Pesce Foraggio (Alborella / Shad)": {
        "finesse": (
            ":material/set_meal: **Pesce foraggio, esche sospese e finesse**\n"
            "- **Jerkbait sospesa (110 mm):** resta ferma nella zona del pesce durante pause di 8-12 secondi.\n"
            "- **Drop shot o damiki rig:** minnow sottile senza paletta da 3-4\", fatto vibrare a mezz'acqua sopra i "
            "pesci sospesi.\n"
            "- **Soft jerkbait (fluke):** caduta planante silenziosa o recupero lineare."),
        "lento": (
            ":material/set_meal: **Pesce foraggio, movimento lento**\n"
            "- **Spinnerbait:** slow-rolling lungo canneti e bordi degli erbai, appena sopra la velocità minima delle "
            "palette.\n"
            "- **Jerkbait sospesa:** colpi di vetta morbidi e pause di 3-6 secondi.\n"
            "- **Swimbait morbida con coda a paletta (3.8-4.8\"):** recupero lento e regolare vicino al fondo."),
        "attivo": (
            ":material/set_meal: **Pesce foraggio, esche di reazione**\n"
            "- **Spinnerbait (doppia willow in acqua chiara, tandem in acqua velata):** a cadenza regolare sotto la "
            "superficie o in slow-rolling lungo i canneti battuti dal vento.\n"
            "- **Swimbait morbida con coda a paletta (3.8-4.8\"):** su testina piombata o amo zavorrato da 1/4 oz, "
            "lungo le punte e i corridoi degli erbai.\n"
            "- **Chatterbait con trailer sottile:** molta vibrazione con un profilo compatto."),
        "secondarie": (
            ":material/refresh: **Seconda scelta (pesce foraggio):** lipless crankbait a yo-yo sui margini "
            "profondi, oppure underspin (testina con piccola paletta willow) per i pesci che seguono senza "
            "attaccare."),
    },
    # rane, insetti, sottoriva
    "Rane / Insetti / Shallow": {
        "finesse": (
            "**Rane e insetti, sottoriva senza rumore**\n"
            "- **Wacky rig senza piombo o neko (verme da 4-5\"):** in skipping sotto rami bassi, pontili e fronde.\n"
            "- **Finesse jig con gonnellino corto:** presentato piano sui bordi esterni di ninfee e canneti.\n"
            "- **Piccolo insetto galleggiante:** lavorato a galla con piccole vibrazioni e soste lunghe."),
        "lento": (
            "**Rane e insetti, movimento lento**\n"
            "- **Verme senza piombo (4-5\"):** caduta lenta lungo canneti e pontili.\n"
            "- **Chatterbait o spinnerbait:** slow-rolling sui bordi della vegetazione appena nata.\n"
            "- **Jig leggero:** lanciato al piede dei canneti e lasciato fermo qualche secondo."),
        "attivo": (
            "**Rane e coperture fitte**\n"
            "- **Rana in gomma cava:** a walk-the-dog sopra i tappeti di vegetazione o nei varchi d'acqua libera del "
            "canneto.\n"
            "- **Flipping e pitching con creature (texas con piombo bloccato, 10-21 g):** per entrare nelle coperture e "
            "nei rami intrecciati.\n"
            "- **Walk-the-dog, popper o buzzbait:** per battere in fretta la superficie lungo le sponde in ombra."),
        "secondarie": (
            ":material/refresh: **Seconda scelta (rane e insetti):** se il pesce attacca la rana senza restare "
            "allamato, rilancia subito nello stesso punto un verme senza piombo a texas o un fluke."),
    },
}

_B3_LURES_MIXED = {
    "finesse": (
        ":material/target: **Prede miste, finesse ed esche sospese**\n"
        "- **Colonna d'acqua:** jerkbait sospesa da 110 mm (con un po' d'onda) o soft jerkbait.\n"
        "- **Fondo:** neko rig o drop shot sui salti di profondità, finesse jig da 5-7 g vicino ai ripari.\n"
        "- **Sponda e ombre:** wacky rig senza piombo in skipping sotto le ombre.",
        ":material/refresh: **Seconda scelta (prede miste):** crankbait flat-side silenzioso o swimbait morbida "
        "da 3.5\" recuperata piano sul primo scalino."),
    "lento": (
        ":material/target: **Prede miste, movimento lento**\n"
        "- **Ricerca orizzontale:** chatterbait o spinnerbait in slow-rolling vicino al fondo.\n"
        "- **Urto sulla struttura:** crankbait flat-side o squarebill che tocca sassi e legni, con una breve sosta "
        "dopo l'urto.\n"
        "- **Coperture:** jig da 3/8 oz con trailer craw, trascinato piano.",
        ":material/refresh: **Seconda scelta (prede miste):** texas rig (7-10 g) con creature o verme a coda "
        "nastro, passato piano dove le esche in movimento hanno avuto tocchi."),
    "potenza": (
        ":material/target: **Prede miste, esche di reazione**\n"
        "- **Ricerca orizzontale:** chatterbait (3/8-1/2 oz) e spinnerbait (colorado o tandem in acqua scura, doppia "
        "willow in acqua chiara con vento).\n"
        "- **Urto sulla struttura:** squarebill o crankbait flat-side che rimbalza su sassi e legni sommersi.\n"
        "- **Coperture:** jig da 3/8-1/2 oz con trailer craw voluminoso.",
        ":material/refresh: **Seconda scelta (prede miste):** texas rig (7-10 g) con creature o verme a coda "
        "nastro, passato piano dove le esche di reazione hanno avuto tocchi."),
    "attivo": (
        ":material/target: **Prede miste, assortimento completo**\n"
        "- **Ricerca:** swimbait morbida da 4\" su amo zavorrato o crankbait medio lungo punte e bordi degli erbai.\n"
        "- **Struttura e coperture:** jig da 3/8 oz o texas rig in pitching sugli ostacoli visibili.\n"
        "- **Alba e tramonto:** walk-the-dog o popper nei cambi di luce.",
        ":material/refresh: **Seconda scelta (prede miste):** ned rig o wacky rig per insistere sui punti "
        "migliori dopo le esche veloci."),
}

_B3_LURES_VERTICAL = (
    ":material/thermostat: **Acqua calda e ossigeno basso, presentazioni verticali**\n"
    "- **Punching rig (1 oz o più):** dentro i tappeti di vegetazione più fitti, dove c'è ombra.\n"
    "- **Drop shot o jig verticale:** sui bordi in ombra delle coperture, pochi spostamenti orizzontali.\n"
    "- **Alba, tramonto e notte:** rana o wakebait lenti in superficie.",
    ":material/refresh: **Seconda scelta (acqua calda):** texas o carolina con verme lungo (7-10\") vicino agli "
    "immissari e, nei laghi profondi, sopra il termoclino.")

_B3_LURES_UNKNOWN = (
    ":material/target: **Temperatura dell'acqua non disponibile**\n"
    "- **Ricerca:** spinnerbait o crankbait medio lungo punte e bordi delle coperture.\n"
    "- **Fondo:** jig o texas rig sugli ostacoli visibili.",
    ":material/refresh: **Seconda scelta:** ned rig o wacky rig sui punti dove hai avuto tocchi.")


def _b3_level_override(row, sim, water_level, astro=None):
    """Override del livello dell'acqua, con la stessa fascia della strike zone della parte A ("" se il livello è stabile)."""
    info = _b3_resolve_zone(row, sim, water_level, astro)
    band = _b3_zone_band(info["zone"])
    where = ("nella fascia %s della strike zone" % _b3_band_text(band)) if band else \
        "nella fascia della strike zone indicata sopra"
    if info["level"] == "In Crescita":
        return (":material/arrow_upward: **Livello in crescita:** la maggior parte dei lanci "
                "in flipping e pitching (jig o texas con piombo bloccato) dentro i cespugli appena allagati, e una "
                "chatterbait o uno spinnerbait tra l'erba appena sommersa, %s." % where)
    if info["level"] == "In Calo":
        return (":material/arrow_downward: **Livello in calo:** le esche sopra valgono sui "
                "punti esterni, non sotto riva. Carolina rig, football jig, crankbait medio o drop shot sulle punte e "
                "sui primi drop-off, dall'esterno verso riva, %s." % where)
    return ""


def _b3_lure_parts(row, sim, torbidita, forage_base, fishing_pressure, water_level, astro=None):
    """-> (primarie senza override, secondarie, override del livello)."""
    P = B3_PARAMS
    row, sim = _b3_dict(row), _b3_dict(sim)
    turb, _assumed = _b3_turbidity(torbidita if torbidita is not None else row.get("torbidita_label"))
    forage = _b3_forage(forage_base)
    pressure = _b3_pressure_level(fishing_pressure)
    regime = _b3_lure_regime(row, sim)
    wind = _b3_num(row.get("wind"))
    override = _b3_level_override(row, sim, water_level, astro)

    key = ""
    if regime == "verticale":
        prim, sec = _B3_LURES_VERTICAL
    elif regime == "ignoto":
        prim, sec = _B3_LURES_UNKNOWN
    elif forage in _B3_LURES:
        sets = _B3_LURES[forage]
        if regime == "freddo" or pressure == "Alta":
            key = "finesse"
        elif regime == "prefrega":
            key = "lento"
        else:
            key = "attivo"
        prim, sec = sets[key], sets["secondarie"]
    else:                                        # prede miste
        clear_calm = turb == "Limpida" and (wind is None or wind < P["lure_clear_calm_kmh"])
        if regime == "freddo" or pressure == "Alta" or (regime == "attivo" and clear_calm):
            key = "finesse"
        elif regime == "prefrega":
            key = "lento"
        elif turb in ("Torbida", "Fangosa") or (wind is not None and wind >= P["lure_power_wind_kmh"]):
            key = "potenza"
        else:
            key = "attivo"
        prim, sec = _B3_LURES_MIXED[key]
    if key == "lento":
        prim += ("\n- **Perché lento:** acqua tra %.0f e %.0f °C in riscaldamento; la deposizione comincia vicino a "
                 "15 °C (Miranda & Muncy 1987) e prima i pesci seguono esche di movimento lento."
                 % (P["lure_cold_below_c"], P["lure_prespawn_hi_c"]))
    elif key == "finesse":
        t, micro = _b3_water_temp(row), _b3_micro(sim)
        if t is not None and t < P["lure_cold_below_c"]:
            why = "acqua sotto i %.0f °C" % P["lure_cold_below_c"]
        elif micro is not None and micro <= P["lure_cooling_micro_c"]:
            why = "raffreddamento di %.1f °C in 72 h" % abs(micro)
        elif pressure == "Alta":
            why = "pressione di pesca alta: presentazioni diverse da quelle più usate sul lago"
        else:
            why = "acqua limpida e poco vento"
        prim += "\n- **Perché finesse:** %s." % why
    return prim, sec, override


def lure_matrix(row, sim, torbidita, forage_base, fishing_pressure, water_level) -> tuple:
    """(primarie, secondarie): esche per preda e regime; le primarie finiscono con l'override del livello dell'acqua."""
    prim, sec, override = _b3_lure_parts(row, sim, torbidita, forage_base, fishing_pressure, water_level)
    return (prim + ("\n\n" + override if override else "")), sec


# ==============================================================================
# 2. STRATEGIA TROPHY
# ==============================================================================
def _b3_trophy_flat(sim):
    """sim["trophy_flat"] del Blocco 2; se manca, escursione della timeline sotto trophy_flat_span; se manca anche quella, False."""
    flag = sim.get("trophy_flat")
    if isinstance(flag, bool):
        return flag
    timeline = sim.get("timeline")
    if isinstance(timeline, (list, tuple)):
        vals = [_b3_num(r.get("trophy_rate")) for r in timeline if isinstance(r, dict)]
        vals = [v for v in vals if v is not None]
        if vals:
            return (max(vals) - min(vals)) < B3_PARAMS["trophy_flat_span"]
    return False


def _b3_index_txt(value):
    v = _b3_num(value)
    return "%.0f" % v if v is not None else "n/d"


_B3_TROPHY_LURES = {
    "molto_lento": "jig da 1/2 oz trascinato lentamente o jerkbait profonda con pause lunghe: un boccone grande, mosso "
                   "poco.",
    "lento": "glide bait o swimbait snodata da 160-180 mm recuperata lenta, jerkbait profonda, jig da 1/2 oz con "
             "trailer craw.",
    "normale": "swimbait morbida grande (6-7\"), glide bait, jig da 1/2-3/4 oz con trailer voluminoso; all'alba e al "
               "tramonto rana o wakebait.",
    "verticale": "punching rig da 1 oz o più nelle coperture più fitte, texas con verme lungo (7-10\") in ombra; "
                 "all'alba rana o wakebait.",
    "ignoto": "swimbait morbida grande o jig da 1/2 oz con trailer voluminoso.",
}

_B3_TROPHY_SPOTS = {
    "molto_lento": "primo salto di profondità vicino alle baie esposte al sole e grandi alberi sommersi isolati",
    "lento": "primo salto di profondità vicino alle baie esposte al sole e grandi alberi sommersi isolati",
    "normale": "vertici delle punte secondarie battute dal vento, margini esterni dei canneti profondi e angoli più bui "
               "dei pontili",
    "verticale": "coperture vegetali più fitte, immissari con acqua più ossigenata e, nei laghi profondi, lo strato "
                 "sopra il termoclino",
    "ignoto": "bordi delle coperture e primi drop-off",
}


def trophy_strategy(trophy_row, sim, fishing_pressure, water_level=None, astro=None) -> str:
    """
    Strategia per i pesci > 2 kg. Prima riga: intestazione (scartata dal Blocco 5). Seconda riga: finestra Trophy o,
    con la curva piatta, "oggi nessuna ora si distingue per i pesci grandi" (nessun picco indicato).
    """
    P = B3_PARAMS
    row, sim = _b3_dict(trophy_row), _b3_dict(sim)
    flat = _b3_trophy_flat(sim)
    rate = _b3_index_txt(row.get("trophy_rate"))
    label = _b3_time_label(row)
    if flat:
        head_when = "nessuna ora migliore"
    else:
        head_when = ("Ore %s" % label) if label else "ora non disponibile"
    lines = [":material/workspace_premium: **Strategia Big Bass (> 2.0 kg | %s | Indice Trophy %s)**" % (head_when, rate)]
    if flat:
        lines.append("Oggi nessuna ora si distingue per i pesci grandi: l'indice Trophy resta quasi uguale tutto il "
                     "giorno, quindi gli orari li decide l'indice di attività.")
    else:
        lines.append("Finestra con l'indice Trophy più alto del giorno (indice relativo da 0 a 100, non una previsione "
                     "di cattura).")

    band = _b3_kinetics_band(row, sim)["band"]
    t = _b3_water_temp(row)
    lure = _B3_TROPHY_LURES.get(band, _B3_TROPHY_LURES["ignoto"])
    if band == "normale" and t is not None and t >= P["kin_near_opt_c"]:
        lure += " Con acqua calda anche texas o carolina con verme lungo (7-10\") vicino alle coperture."
    lines.append("- **Esca da trofeo:** " + lure)
    lines.append("- **Perché esche grandi:** nelle prove sul largemouth le esche più grandi hanno alzato la taglia "
                 "media delle catture, ma non il numero di pesci da %d mm in su presi ogni ora (%s): servono a "
                 "scegliere i pesci, non a prenderne di più." % (P["trophy_ref_size_mm"], P["trophy_ref_size"]))

    info = _b3_resolve_zone(row, sim, water_level, astro)
    if info["level"] == "In Crescita":
        spot = "bordo esterno delle zone appena allagate, dove l'acqua è un po' più profonda"
    elif info["level"] == "In Calo":
        spot = "punte esterne e primi drop-off, dove i pesci si ritirano quando il livello scende"
    else:
        spot = _B3_TROPHY_SPOTS.get(band, _B3_TROPHY_SPOTS["ignoto"])
    lines.append("- **Dove:** %s. Strike zone Trophy: `%s`." % (spot, _b3_code_safe(info["zone"])))

    bonus_fn = globals().get("prespawn_bonus")
    if callable(bonus_fn) and t is not None:
        try:
            bonus = _b3_num(bonus_fn(t, _b3_macro(sim)))
        except Exception:          # funzione del Blocco 2: un suo errore non deve fermare il report
            bonus = None
        if bonus is not None and bonus >= P["trophy_prespawn_note_min"]:
            macro = _b3_macro(sim)
            lines.append("- **Pre-frega:** acqua a %.1f °C in riscaldamento (Δ14gg %s °C): nel modello è la finestra "
                         "in cui le femmine sono più pesanti; la deposizione comincia vicino a 15 °C (Miranda & Muncy "
                         "1987)." % (t, _b3_signed(macro if macro is not None else 0.0)))

    if _b3_pressure_level(fishing_pressure) == "Alta":
        lines.append("- **Pressione di pesca alta:** lanci molto lunghi e recupero lento e costante, senza fermate "
                     "brusche.")
    elif flat or not label:
        lines.append("- **Tempi:** senza una finestra Trophy, alterna i 2-3 punti migliori durante la giornata e segui "
                     "le ore migliori dell'attività.")
    else:
        lines.append("- **Tempi:** insisti sui 2-3 punti migliori nei %d minuti attorno alle %s."
                     % (P["trophy_window_min"], label))
    return "\n".join(lines)


# ==============================================================================
# 3. CLASSE PUBBLICA
# ==============================================================================
def _b3_mode(value):
    P = B3_PARAMS
    return _b3_pick(value, P["report_modes"], P["report_mode_default"])


def _b3_bio_alert(mode, best, trophy_row, sim, state):
    """Bio-alert per il Blocco 5: "parte | parte — stato" (Entrambi) o "focus — picco — stato"; nessun "%"."""
    catch = _b3_index_txt(best.get("catch_rate"))
    trophy = _b3_index_txt(trophy_row.get("trophy_rate"))
    when = _b3_time_label(best) or "n/d"
    t_when = _b3_time_label(trophy_row) or "n/d"
    trophy_flat = _b3_trophy_flat(sim)
    bai_flat = sim.get("bai_flat") is True
    action = ("Attività senza picco oggi (%s)" % catch) if bai_flat else ("Picco Attività Ore %s (%s)" % (when, catch))
    big = ("Trophy senza picco oggi (%s)" % trophy) if trophy_flat else ("Picco Trophy Ore %s (%s)" % (t_when, trophy))
    if mode == "Numeri":
        return ":material/local_fire_department: Focus Numeri — %s — %s" % (action, state)
    if mode == "Trophy":
        return ":material/workspace_premium: Focus Big Bass — %s — %s" % (big, state)
    return ":material/local_fire_department: %s | :material/workspace_premium: %s — %s" % (action, big, state)


class TacticalAdvisorV2:
    """
    Report tattico del Bass Engine (Blocco 3 v2). Testi in italiano costruiti dalle funzioni delle parti A, B e C:
    condizione e posizionamento (A), recupero, setup e colori (B), esche e strategia Trophy (C). Ogni testo distingue
    i dati (citati con la fonte) dalle indicazioni pratiche; gli indici sono relativi, mai probabilità.
    Le vecchie funzioni statiche (analyze_hydro_biological_positioning, compute_retrieve_kinetics_and_gear,
    select_chromatic_spectrum, build_biomechanical_lure_matrix) non sono più esposte: nessun altro blocco le chiamava.
    """

    @classmethod
    def generate_pro_report(cls, best_hour, trend_3d, astro, sim_results=None, water_level="Stabile",
                            forage_base="Misto", fishing_pressure="Media", target_mode="Entrambi") -> dict:
        """Report completo (contratto e invarianti nella testa della parte C)."""
        sim = dict(sim_results) if isinstance(sim_results, dict) else {}
        best = _b3_dict(best_hour)
        if _b3_micro(sim) is None and _b3_num(trend_3d) is not None:
            sim["micro_trend_72h"] = _b3_num(trend_3d)
        trophy_row = sim.get("best_trophy_hour")
        trophy_row = trophy_row if isinstance(trophy_row, dict) and trophy_row else best
        trophy_ref = best if _b3_trophy_flat(sim) else trophy_row    # curva piatta: best_trophy_hour non è un picco
        mode = _b3_mode(target_mode)
        goal = mode if mode in B3_PARAMS["goals"] else None
        active = trophy_ref if mode == "Trophy" else best
        torb = active.get("torbidita_label")

        state = _b3_bio_state(active, sim)
        condizione = physiological_condition(active, sim)
        approccio = condizione + "\n\n" + positional_approach(active, sim, water_level, astro)
        strike_zone = strike_zone_for(active, sim, water_level, astro)
        gear = gear_setup(active, torb, active.get("wind"), fishing_pressure, water_level, goal)
        recupero = retrieve_kinetics(active, sim, fishing_pressure, goal) + "\n\n---\n" + gear
        colore = color_choice(active, torb, forage_base, astro, goal)
        prim, sec, override = _b3_lure_parts(active, sim, torb, forage_base, fishing_pressure, water_level, astro)
        prim_full = prim + ("\n\n" + override if override else "")

        if mode == "Numeri":
            strategia = ""
            esche_primarie, esche_secondarie = prim_full, sec
        elif mode == "Trophy":
            strategia = trophy_strategy(trophy_ref, sim, fishing_pressure, water_level, astro)
            esche_primarie = strategia + ("\n\n" + override if override else "")
            esche_secondarie = (":material/refresh: **Se le esche grandi non danno seguiti:** "
                                "passa alle esche per fare numero, nelle misure più grandi.\n\n" + prim)
        else:
            strategia = trophy_strategy(trophy_ref, sim, fishing_pressure, water_level, astro)
            esche_primarie = prim_full
            esche_secondarie = sec + "\n\n---\n" + strategia

        return {
            "condizione": condizione,
            "approccio": approccio,
            "esche_primarie": esche_primarie,
            "esche_secondarie": esche_secondarie,
            "colore": colore,
            "recupero": recupero,
            "strike_zone": strike_zone,
            "gear_setup": gear,
            "strategia_trophy": strategia,
            "bio_alert": _b3_bio_alert(mode, best, trophy_row, sim, state),
            "target_mode": mode,
            "esche": esche_primarie + "\n\n" + esche_secondarie,
            "colori": colore,
            "velocita": recupero,
        }

    @classmethod
    def generate_report(cls, sim_data, torbidita="Non specificato", spot_morphology="", water_level="Stabile",
                        forage_base="Misto", fishing_pressure="Media", target_mode="Entrambi", astro=None) -> dict:
        """
        Vecchio wrapper: delega a generate_pro_report con best_hour = sim_data["best_hour"]. La torbidità resta quella
        delle righe del Blocco 2 (torbidita_label); il parametro torbidita si usa solo se la riga non ne ha una.
        spot_morphology è accettato per compatibilità e non entra nel calcolo (come nel Blocco 3 originale).
        astro None: alba e tramonto di sim_data["astro_used"], poi 6.5 e 19.5.
        """
        sim = dict(sim_data) if isinstance(sim_data, dict) else {}
        best = dict(_b3_dict(sim.get("best_hour")))
        if not _b3_one_line(best.get("torbidita_label")):
            best["torbidita_label"] = torbidita
            trophy = sim.get("best_trophy_hour")
            if isinstance(trophy, dict) and not _b3_one_line(trophy.get("torbidita_label")):
                trophy = dict(trophy)
                trophy["torbidita_label"] = torbidita
                sim["best_trophy_hour"] = trophy
        trend = _b3_micro(sim)
        return cls.generate_pro_report(best_hour=best, trend_3d=trend if trend is not None else 0.0, astro=astro,
                                       sim_results=sim, water_level=water_level, forage_base=forage_base,
                                       fishing_pressure=fishing_pressure, target_mode=target_mode)


# >>> BLOCCO: Blocco4-BF-V4.py <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ==============================================================================
# MODULO 4 (v4): MOTORE GRAFICO MOBILE — COLONNE ORARIE INTERATTIVE + GRAFICI PLOTLY
# ==============================================================================
# Stile unico (01/11/2026): una tavolozza sola per tutta l'app (B4_UI, B4_COL_*, B4_RAMP_*), le stesse superfici
#   (riquadri neri con bordo grigio), bordi (8 px), testi, verde e carattere (Source Sans) della parte alta della
#   pagina. Grafico orario: schede come il segmented control di Streamlit, scala di verdi per ora ricostruita sul
#   verde dell'app, fumetti rialzati.
# Fattori nel grafico orario (01/11/2026): metabolismo, barometro, luce, vento, torbidità e ossigeno stanno in un
#   riquadro sotto la striscia delle ore e seguono l'ora selezionata (colonnina, riquadro della striscia o frecce
#   ‹ › del riquadro: una sola selezione per tutto il grafico); senza selezione, l'ora migliore. Prima erano un
#   grafico Plotly a parte, fermo sull'ora migliore, che ora resta solo come riserva. Altezza 782 px.
# Acqua e ossigeno nel grafico orario (01/11/2026): il riquadro sotto la striscia delle ore diventa il riquadro
#   dell'ora (titolo "Ora migliore" / "Ora selezionata", frecce ‹ ›) con due caselle, Acqua °C e Ossigeno mg/L,
#   che seguono la stessa selezione dei fattori. Prima il Blocco 5 le mostrava sopra il grafico, ferme sull'ora
#   migliore. Sotto l'acqua la variazione in 3 giorni (micro_trend_72h: dato del giorno, uguale per tutte le ore,
#   e scritto come tale); sotto l'ossigeno il giudizio dell'ora con le soglie EPA 1986 dei Blocchi 1, 2 e 5
#   (B4_DO_LIMITED_MG_L, B4_DO_STRESS_MG_L). Altezza 862 px.
#
# Cosa cambia rispetto alla v3 (30/10/2026; solo la scheda "Confronta" del grafico a colonnine):
#   * Attività sopra e Trophy sotto, ognuno a tutta larghezza, al posto dei due grafici affiancati (sul telefono
#     erano stretti e alti); una sola scala per le due serie (prima 0-40 e 0-50, non confrontabili).
#   * Niente fumetti in questa scheda: toccando un'ora, la riga del titolo di ogni grafico ne mostra il valore.
#     Si tocca tutta la colonna, non solo la barra.
#   * Altezza del widget invariata (B4_W_HEIGHT): il Blocco 5 non deve cambiare per questo. Schede Attività e
#     Trophy, striscia delle ore, Plotly, radar e fattori identici alla v3.
#
# Cosa cambiava rispetto alla v2 (v3; solo grafica: i Blocchi 1-2-3 NON vengono toccati):
#   * NUOVO create_mobile_hourly_widget(): il grafico orario diventa una pagina HTML con 24 colonnine
#     (una per ora) al posto delle curve Plotly. Dentro il riquadro: schede Attività / Trophy / Confronta,
#     scala laterale con linee orizzontali, corona (icona Material Symbols "crown") sull'ora migliore,
#     striscia scorrevole con il punteggio di ogni ora, fumetto col valore esatto toccando una colonnina.
#     Il Blocco 5 v4 lo mostra con st.iframe; create_mobile_plotly_chart resta come riserva.
#   * Tocco: risponde solo la colonnina disegnata (più 8 px sopra la cima, nessun margine ai lati);
#     un tocco in qualsiasi altro punto della pagina chiude il fumetto.
#   * Colori di Attività e Trophy schiariti (#3DDC97, #B98CFF) per uniformarli al nuovo grafico: valgono
#     anche per radar, barre dei fattori e tabella del Blocco 5. Contrasto su #161B22: 9.8:1 e 6.8:1.
#
# Cosa cambiava rispetto alla v1 (v2):
#   * Una curva = un grafico. Attività (BAI) e Trophy stanno in righe separate, ognuna con la
#     propria scala. Via il doppio asse, via la legenda con le emoji, via la linea "DO %".
#   * Le informazioni chiave sono SCRITTE sopra ogni grafico ("picco 06:00", "ore migliori:
#     05:00–08:00 · 18:00–20:00"): non bisogna leggerle dalla curva con le dita.
#   * Un solo punto etichettato con l'ora per il picco + fasce evidenziate per le ore migliori.
#   * Se una curva è piatta (es. Trophy fisso al minimo) NON viene disegnato un picco finto:
#     il grafico lo dice a parole. Risolve il caso "picco Trophy alle 00:00" visto in estate.
#   * Testi più grandi (11-13 px) e spazi calcolati in pixel. Verificato con un rendering reale
#     (Chromium + plotly.js 2.35 / 3.0 / 4.1, larghezze 320-393 px): nessun testo si sovrappone,
#     esce dal riquadro o viene attraversato dalla curva.
#   * Al tocco compare UN riquadro: ora, valore di ogni serie (Attività, Trophy, Acqua) e
#     contesto in grigio (vento, pressione, O₂, zona). Nessuna etichetta extra sull'asse.
#   * Il valore di ossigeno NON viene più mostrato come "%" (era un indice euristico, non una
#     saturazione): nel tooltip compare come "O₂ indice 0.40", oppure "O₂ 7.2 mg/L" se il
#     Blocco 1 fornirà la chiave `do_actual_mg_l`.
#   * Radar riordinato (etichette con il valore, niente semaforo a soglie) + nuove barre dei
#     fattori, più rapide da leggere del radar.
#
# FUNZIONI PUBBLICHE (firme retrocompatibili con la v1)
#   create_mobile_hourly_widget(sim, astro, target_mode="Entrambi")  # NUOVO (v3): HTML per st.iframe, alto B4_W_HEIGHT
#   create_mobile_plotly_chart(sim, astro, target_mode="Entrambi", focus_hour=None)
#   create_mobile_radar(best_hour, target_mode="Entrambi")            # accetta anche l'intero `sim`
#   create_mobile_factors_chart(best_hour, target_mode="Entrambi")    # NUOVO: barre orizzontali
#   check_block4_contract(sim)                                        # NUOVO: controllo del contratto dati
#   MOBILE_PLOTLY_CONFIG                                              # NUOVO: config consigliata per st.plotly_chart
#
# USO CONSIGLIATO IN STREAMLIT
#   st.plotly_chart(fig, use_container_width=True, config=MOBILE_PLOTLY_CONFIG)
#   Nota: Streamlit applica un proprio tema ai grafici Plotly; se colori o font risultassero
#   diversi da quelli previsti, aggiungere theme=None (non verificato qui: Streamlit non era
#   disponibile nell'ambiente di test).
#
# DATI LETTI (chiavi del timeline dei Blocchi 1-2; tutte tranne `hour` sono opzionali):
#   hour, time_label, date_str, catch_rate, trophy_rate, water_temp_used | water_temp, wind,
#   pressure_delta, depth_zone, do_saturation_index (| do_actual_mg_l), s_temp, s_press, s_sol,
#   s_vento, s_torb. In `sim`: best_hour, best_trophy_hour (| no_good_window, window_quality).
#
# LIMITI NOTI (da dichiarare)
#   * Tutto ciò che il grafico mostra sono gli indici del Blocco 2 (relativi, non calibrati):
#     il Blocco 4 li rende leggibili ma non li rende più affidabili.
#   * best_trophy_hour del Blocco 2 vale ore 00:00 quando il Trophy è piatto (bug del Blocco 2):
#     qui viene ignorato se si passa l'intero `sim`; passando la sola riga resta a carico del chiamante.
#   * Provato con Chromium e dati meteo sintetici, non su Safari/iPhone né dentro Streamlit.
#   * v3, grafico a colonnine: controllato solo il codice (Python eseguito, JavaScript eseguito in Node con una
#     pagina simulata). La resa nel browser, dentro st.iframe e su iPhone NON è stata provata qui.
#   * Il carattere del grafico orario (Source Sans 3, lo stesso di Streamlit) arriva da Google Fonts: senza rete
#     usa il carattere di sistema.
#
# Nota sugli import: se i blocchi vengono incollati in un unico file, questi import possono
# restare duplicati senza problemi (datetime è importato con alias per non sovrascrivere
# eventuali `from datetime import datetime` presenti altrove).
# ==============================================================================
import math
import datetime as _b4_dt
import json as _b4_json
import textwrap as _b4_tw

import plotly.graph_objects as go


# ------------------------------------------------------------------------------
# COSTANTI DI STILE
# ------------------------------------------------------------------------------
# Tavolozza unica dell'app (v4, 01/11/2026): le stesse superfici, bordi, testi, verde e carattere della parte alta
# della pagina. Il tema di Streamlit (.streamlit/config.toml) riporta gli stessi valori; il Blocco 5 legge B4_UI per il
# suo CSS (riquadri "?" e superfici). Superfici: riquadri neri con bordo grigio, come l'intestazione della pagina
# (scelta del 01/11/2026 tra questa e riquadri pieni #1C1C1E).
# Verde = primaryColor del tema; viola alla stessa luminosità. Scale per ora (ore migliori, ore di luce, buio): stessa
# tinta in OKLCH, luminosità 0.65 / 0.53 / 0.43. Verificate il 01/11/2026 con validate_palette.js, modalità scura:
# verde-viola CVD ΔE 17.2 (deutan), visione normale 27.9, contrasto >= 3:1; scale monotone, ΔL >= 0.06, una sola
# tinta. Contrasti su nero: testo 18.8:1, secondario 6.7:1, assi 4.8:1; verde notte 2.72:1, viola notte 2.48:1. Nella v3 erano #3DDC97 / #B98CFF, più chiari del verde dell'app (L 0.80 contro 0.65).
B4_UI = {
    "page": '#000000',
    "surface": '#000000',
    "card": 'transparent',
    "border": 'rgba(242, 242, 247, 0.2)',
    "line": 'rgba(242, 242, 247, 0.10)',
    "line_base": 'rgba(242, 242, 247, 0.30)',
    "track": 'rgba(242, 242, 247, 0.08)',
    "ink": '#F2F2F7',
    "ink2": '#919194',
    "ink3": '#79797C',
    "overlay": 'rgba(44, 44, 46, 0.86)',
    "overlay_solid": '#2C2C2E',
    "overlay_border": 'rgba(242, 242, 247, 0.16)',
    "panel": 'rgba(242, 242, 247, 0.03)',
    "font": '"Source Sans", "Source Sans 3", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "font_css": 'https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap',
    "radius": 8,
}
B4_COL_BAI = "#0fa874"       # Attività / Numeri (= primaryColor del tema)
B4_COL_TROPHY = "#9C72DE"    # Trophy
B4_RAMP_BAI = ("#0fa874", "#0F7F58", "#085F40")        # ore migliori, ore di luce, buio
B4_RAMP_TROPHY = ("#9C72DE", "#7857AC", "#594082")
B4_COL_WATER = "#2b9fe0"     # Temperatura dell'acqua
# Stato dell'ossigeno nel riquadro dell'ora (solo testo di stato, sempre con la parola: mai il colore da solo).
# Ambra = occhio del logo; rosso tenue. Contrasto su nero 10.6:1 e 7.3:1, sul fondo delle caselle 9.3:1 e 6.4:1.
B4_COL_WARN = "#E3B04B"      # attività limitata
B4_COL_ALERT = "#F2706B"     # stress
B4_DO_LIMITED_MG_L = 5.0     # ossigeno sotto: attività limitata (criteri EPA 1986, come Blocchi 1, 2 e 5)
B4_DO_STRESS_MG_L = 4.0      # sotto: stress
B4_INK_1 = B4_UI["ink"]      # testo primario
B4_INK_2 = B4_UI["ink2"]     # testo secondario
B4_INK_3 = B4_UI["ink3"]     # assi e didascalie
B4_SURFACE = B4_UI["surface"]    # colore dietro i grafici (anello attorno ai marker)
B4_PANEL = B4_UI["panel"]
B4_GRID = B4_UI["line"]
B4_DAYLIGHT = "rgba(250, 204, 21, 0.055)"    # velo caldo sulle ore di luce
B4_FONT = B4_UI["font"]

# Config consigliata per st.plotly_chart(..., config=MOBILE_PLOTLY_CONFIG): niente barra
# strumenti, niente zoom con la rotella, niente doppio tocco che resetta il grafico.
MOBILE_PLOTLY_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showTips": False,
    "responsive": True,
}

# Geometria in pixel (pensata per ~360-393 px di larghezza utile)
B4_MARGIN_L = 34
B4_MARGIN_R = 10
B4_MARGIN_T = 2
B4_MARGIN_B = 44
B4_ROW_H_SINGLE = 140        # altezza del grafico quando c'è una sola curva
B4_ROW_H_DUAL = 108          # altezza di ciascun grafico in modalità "Entrambi"
B4_STRIP_H = 34              # striscia della temperatura dell'acqua
B4_HEADER_H = 50             # spazio per il titolo a due righe sopra ogni grafico (aria inclusa)
B4_STRIP_HEADER_H = 30       # spazio per il titolo a una riga sopra la striscia
B4_HEADER_GAP = 7            # distanza tra il titolo e il bordo alto del grafico
B4_STRIP_GAP = 5

# Soglie di PRESENTAZIONE (IPOTESI: servono solo a decidere cosa evidenziare, non hanno
# alcun significato biologico e non influenzano il modello).
B4_FLAT_SPAN = 1.0           # escursione minima (punti indice) sotto cui la curva è "piatta"
B4_WINDOW_FRAC = 0.80        # "ore migliori" = ore con valore >= minimo + 80% dell'escursione
B4_MAX_WINDOWS = 2           # al massimo due fasce evidenziate per grafico (alba e tramonto)
B4_PEAK_TOL = 0.5            # tolleranza per accettare il picco indicato dal Blocco 2
B4_Y_ADAPTIVE = True         # True: scala verticale adattata ai valori; False: sempre 0-100
B4_FOOTER_NOTE = "indici relativi, non probabilità"   # "" per toglierlo
B4_BARS_XMAX = 114           # estremo destro dell'asse delle barre (la colonna dei numeri sta oltre il 100)

_B4_DOW = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")
_B4_MON = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")
_B4_MODES = {"numeri": "Numeri", "trophy": "Trophy", "entrambi": "Entrambi"}


# ------------------------------------------------------------------------------
# UTILITÀ
# ------------------------------------------------------------------------------
def _b4_f(value, default=0.0):
    """float sicuro: None / testo / NaN / inf -> default."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(x) or math.isinf(x):
        return default
    return x


def _b4_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    return "rgba(%d, %d, %d, %s)" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _b4_esc(text):
    """Escape minimo per i testi di Plotly (nomi di zona ecc. arrivano da altri blocchi)."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _b4_wrap_html(text, width=34, max_lines=2, prefix=""):
    lines = _b4_tw.wrap(prefix + str(text), width=width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" ,.;:&(") + "…"
    return "<br>".join(_b4_esc(line) for line in lines)


def _b4_norm_mode(target_mode):
    return _B4_MODES.get(str(target_mode).strip().lower(), "Entrambi")


def _b4_hhmm(hour):
    total = int(round(_b4_f(hour, 0.0) * 60.0))
    hh, mm = divmod(total, 60)
    return "%02d:%02d" % (hh % 24, mm)


def _b4_hour_from_label(label):
    try:
        hh, mm = str(label).split(":")[:2]
        return int(hh) + int(mm) / 60.0
    except (ValueError, TypeError):
        return None


def _b4_parse_day(date_str):
    try:
        return _b4_dt.datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _b4_ts(day, hour):
    """Timestamp 'YYYY-MM-DD HH:MM:SS' per un'ora decimale (anche fuori 0-24: scavalca il giorno)."""
    dt = day + _b4_dt.timedelta(minutes=int(round(hour * 60.0)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _b4_time_ticks(day, hours, step_h, fmt):
    """Tick dell'asse dei tempi: (valori, testi), uno ogni `step_h` ore dalla mezzanotte del primo giorno.

    Li calcoliamo noi (invece di dtick/tick0) per due motivi: l'ultimo tick viene tolto se la sua
    etichetta uscirebbe dal riquadro (con dati ogni 15 minuti, o fino alle 24:00, "00:00" sporgeva
    di qualche pixel a destra) e con pochissimi dati le etichette sono le ore stesse.
    """
    lo_h, hi_h = hours[0] - 0.5, hours[-1] + 0.5
    edge_h = 0.03 * (hi_h - lo_h)      # ~8-10 px sui 276-349 px utili di uno schermo da telefono

    def label(h):
        return (day + _b4_dt.timedelta(minutes=int(round(h * 60.0)))).strftime(fmt)

    vals, texts = [], []
    k = int(math.ceil(lo_h / step_h - 1e-9))
    while len(vals) < 60:
        h = k * step_h
        if h > hi_h - edge_h + 1e-9:
            break
        vals.append(_b4_ts(day, h))
        texts.append(label(h))
        k += 1
    if len(vals) < 2:                  # serie cortissima: nessun multiplo di step_h cade nei dati
        picks = list(hours) if len(hours) <= 6 else [hours[i * (len(hours) - 1) // 5] for i in range(6)]
        vals = [_b4_ts(day, h) for h in picks]
        texts = [label(h) for h in picks]
    return vals, texts


def _b4_day_label(day):
    try:
        return "%s %d %s" % (_B4_DOW[day.weekday()], day.day, _B4_MON[day.month - 1])
    except (AttributeError, IndexError):
        return ""


def _b4_hour_of(obj):
    """Ora (float) da un dict-riga, da un numero o da un 'HH:MM'. None se non interpretabile."""
    if isinstance(obj, dict):
        h = _b4_f(obj.get("hour"), None)
        if h is None:
            h = _b4_hour_from_label(obj.get("time_label"))
        return h
    h = _b4_f(obj, None)
    if h is None:
        h = _b4_hour_from_label(obj)
    return h


def _b4_cont_hour(obj, day0):
    """Ora continua (float) di una riga/numero: conta dal giorno 0 se la riga ha una `date_str`."""
    h = _b4_hour_of(obj)
    if h is None:
        return None
    if isinstance(obj, dict) and day0 is not None:
        d = _b4_parse_day(obj.get("date_str"))
        if d is not None:
            h += (d - day0).days * 24.0
    return h


def _b4_chrono(raw_rows):
    """
    Righe (solo dict) in ordine cronologico -> (giorno_0 oppure None, [(ora_continua, riga), ...]).
    L'ora è continua dal primo giorno: se il timeline copre più giorni (hour 0-23 ripetuto con
    `date_str` diversa) i punti restano nell'ordine giusto invece di mescolarsi.
    """
    items = []
    for i, r in enumerate(raw_rows):
        if not isinstance(r, dict):
            continue
        h = _b4_hour_of(r)
        items.append((_b4_parse_day(r.get("date_str")), float(i) if h is None else h, r))
    days = [d for d, _, _ in items if d is not None]
    day0 = min(days) if days else None
    out = []
    for d, h, r in items:
        if day0 is not None and d is not None:
            h += (d - day0).days * 24.0
        out.append((h, r))
    out.sort(key=lambda t: t[0])
    return day0, out


def _b4_ticks(peak):
    """Scala verticale: tick a 0 / metà / cima + limite superiore con spazio per l'etichetta del picco."""
    if B4_Y_ADAPTIVE:
        tick_top = 100.0
        for cand in (20.0, 30.0, 40.0, 60.0, 80.0, 100.0):
            if peak <= cand:
                tick_top = cand
                break
        else:
            tick_top = float(math.ceil(peak / 10.0) * 10.0)
    else:
        tick_top = 100.0
    range_top = max(tick_top, peak * 1.38)
    return [0.0, tick_top / 2.0, tick_top], range_top


def _b4_find_peak(hours, vals, preferred_hour, twilights):
    """Indice del picco, oppure None se la curva è piatta (nessuna ora si distingue)."""
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    if (hi - lo) < B4_FLAT_SPAN:
        return None
    # 1) picco indicato dal Blocco 2 (coerenza col report testuale), se è davvero in cima
    if preferred_hour is not None:
        for i, h in enumerate(hours):
            if abs(h - preferred_hour) < 1e-6 and vals[i] >= hi - B4_PEAK_TOL:
                return i
    # 2) picco locale con spareggio deterministico: vicino a alba/tramonto, poi ora più bassa
    cands = [i for i, v in enumerate(vals) if v >= hi - 1e-9]
    cands.sort(key=lambda i: (min([abs(hours[i] - t) for t in twilights] or [0.0]), hours[i]))
    return cands[0]


def _b4_windows(hours, vals):
    """Fasce di ore consecutive nella parte alta della curva: [(ora_inizio, ora_fine), ...]."""
    if not vals:
        return [], 1.0
    lo, hi = min(vals), max(vals)
    diffs = sorted(b - a for a, b in zip(hours, hours[1:]) if b - a > 1e-9)
    step = diffs[len(diffs) // 2] if diffs else 1.0
    if (hi - lo) < B4_FLAT_SPAN:
        return [], step
    thr = lo + B4_WINDOW_FRAC * (hi - lo)
    runs, cur = [], []
    for h, v in zip(hours, vals):
        if v >= thr - 1e-12:
            if cur and (h - cur[-1][0]) > step * 1.01:
                runs.append(cur)
                cur = []
            cur.append((h, v))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    runs.sort(key=lambda run: max(v for _, v in run), reverse=True)
    runs = runs[:B4_MAX_WINDOWS]
    runs.sort(key=lambda run: run[0][0])
    return [(run[0][0], run[-1][0]) for run in runs], step


def _b4_windows_text(windows):
    parts = []
    for h0, h1 in windows:
        if abs(h1 - h0) < 1e-9:
            parts.append(_b4_hhmm(h0))
        else:
            parts.append("%s–%s" % (_b4_hhmm(h0), _b4_hhmm(h1)))
    return " · ".join(parts)


def _b4_vtxt(v):
    """Valore di un indice: intero da 10 in su, un decimale sotto (niente falsa precisione)."""
    return ("%.0f" % v) if abs(v) >= 10 else ("%.1f" % v)


def _b4_details(r):
    """Righe di contesto per il tooltip (lista; solo ciò che esiste davvero nella riga)."""
    lines = []
    bits = []
    wind = _b4_f(r.get("wind"), None)
    if wind is not None:
        bits.append("Vento %.0f km/h" % wind)
    dp = _b4_f(r.get("pressure_delta"), None)
    if dp is not None:
        bits.append("Pressione %+.1f hPa/3h" % dp)
    if bits:
        lines.append(" · ".join(bits))
    mg = _b4_f(r.get("do_actual_mg_l"), None)
    if mg is not None:
        lines.append("O₂ %.1f mg/L" % mg)
    else:
        di = _b4_f(r.get("do_saturation_index"), None)
        if di is not None:
            lines.append("O₂ indice %.2f" % di)
    zone = r.get("depth_zone")
    if zone not in (None, "", "-"):
        lines.extend(_b4_wrap_html(zone, prefix="Zona: ").split("<br>"))
    return lines


def _b4_empty_figure(message, height=110):
    return go.Figure(layout=dict(
        template="plotly_dark",
        height=height,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=B4_PANEL,
        font=dict(family=B4_FONT, size=13, color=B4_INK_2),
        dragmode=False,
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        annotations=[dict(text=_b4_esc(message), x=0.5, y=0.5, xref="paper", yref="paper",
                          showarrow=False, font=dict(size=13, color=B4_INK_2))],
    ))


def _b4_dot(color):
    return '<span style="color:%s">●</span>' % color


def _b4_muted(text):
    return '<span style="color:%s">%s</span>' % (B4_INK_2, text)


# ------------------------------------------------------------------------------
# INGRESSO: normalizzazione degli input (dict sim | lista legacy | 3° argomento dict)
# ------------------------------------------------------------------------------
def _b4_prepare(sim, astro, target_mode):
    legacy_best = None
    if isinstance(target_mode, dict):     # vecchia UI: create_mobile_plotly_chart(tl, astro, best_hour)
        legacy_best = target_mode
        target_mode = "Entrambi"
    mode = _b4_norm_mode(target_mode)

    best_hour = best_trophy = None
    flags = {"no_good_window": False, "window_quality": ""}
    if isinstance(sim, dict):
        raw_rows = sim.get("timeline") or []
        if isinstance(sim.get("best_hour"), dict):
            best_hour = sim["best_hour"]
        if isinstance(sim.get("best_trophy_hour"), dict):
            best_trophy = sim["best_trophy_hour"]
        flags["no_good_window"] = bool(sim.get("no_good_window", False))
        flags["window_quality"] = str(sim.get("window_quality") or "").strip().lower()
    elif isinstance(sim, (list, tuple)):
        raw_rows = list(sim)
    else:
        raw_rows = []
    if legacy_best is not None:
        best_hour = legacy_best

    day0, chrono = _b4_chrono(raw_rows)
    rows = [{"h": h, "r": r} for h, r in chrono]

    return {
        "rows": rows,
        "day0": day0,
        "mode": mode,
        "astro": astro if isinstance(astro, dict) else {},
        "best_hour": best_hour,
        "best_trophy_hour": best_trophy,
        "flags": flags,
    }


# ------------------------------------------------------------------------------
# GRAFICO 0 — COLONNE ORARIE INTERATTIVE (pagina HTML per st.iframe) — NUOVO NELLA v3
# ------------------------------------------------------------------------------
# Una pagina HTML autonoma (CSS + JavaScript senza librerie esterne). Python fa tutti i conti (scala, picco, ore
# migliori, colori di giorno e notte) e li passa al JavaScript come JSON; il JavaScript disegna e gestisce i tocchi.
# Streamlit la mostra con st.iframe (vedi Blocco 5 v4), che esegue il JavaScript.
B4_W_HEIGHT = 862            # altezza dell'iframe in px: fissa, le tre schede occupano lo stesso spazio
B4_W_START_TAB = {"Numeri": "att", "Trophy": "tro", "Entrambi": "att"}   # scheda aperta per ogni "Obiettivo"
B4_W_MAX_ROWS = 48           # oltre (dati ogni 15 minuti, più giorni) il Blocco 5 usa il grafico Plotly
B4_W_SCALE_TOPS = (10, 20, 30, 40, 50, 60, 80, 100)   # cima della scala: il primo valore >= picco del giorno
B4_W_TOUCH_PAD = 8           # px di tolleranza al tocco SOPRA la cima di ogni colonnina (ai lati: nessuna)
B4_W_FONT_CSS = B4_UI["font_css"]
B4_W_CARD = B4_UI["card"]    # superficie dei riquadri (come i riquadri di Streamlit)
B4_W_BORDER = B4_UI["border"]
B4_W_INK = B4_UI["ink"]      # testo primario
B4_W_INK_2 = B4_UI["ink2"]   # testo secondario
B4_W_INK_3 = B4_UI["ink3"]   # scala e orari
# Icona "crown" di Material Symbols (Google), stile rounded pieno, licenza Apache 2.0: vettoriale 24x24.
B4_CROWN_PATH = (
    "M6 20q-.425 0-.712-.288T5 19t.288-.712T6 18h12q.425 0 .713.288T19 19t-.288.713T18 20zm.7-3.5q-.725 0-1.287-.475"
    "t-.688-1.2l-1-6.35q-.05 0-.112.013T3.5 8.5q-.625 0-1.062-.437T2 7t.438-1.062T3.5 5.5t1.063.438T5 7q0 .175-.038.325"
    "t-.087.275L8 9l3.125-4.275q-.275-.2-.45-.525t-.175-.7q0-.625.438-1.063T12 2t1.063.438T13.5 3.5q0 .375-.175.7"
    "t-.45.525L16 9l3.125-1.4q-.05-.125-.088-.275T19 7q0-.625.438-1.063T20.5 5.5t1.063.438T22 7t-.437 1.063T20.5 8.5"
    "q-.05 0-.112-.012t-.113-.013l-1 6.35q-.125.725-.687 1.2T17.3 16.5z"
)

# Geometria interna (px). Se la cambi, ricontrolla B4_W_HEIGHT: schede 36 + 12 + vista + 12 + striscia 66 + 12
# + fattori + 6.
_B4_W_VIEW_H = 368           # altezza della vista (riquadro grande oppure i due di "Confronta")
_B4_W_PLOT = (236, 160)      # riquadro grande: (altezza dell'area del grafico, altezza massima delle colonnine)
_B4_W_PLOT_CMP = (108, 86)    # "Confronta": come _B4_W_PLOT, per ciascuno dei due grafici impilati
_B4_W_FAC_H = 344            # riquadro dell'ora: titolo con le frecce, caselle acqua e ossigeno, sintesi, 6 barre


def _b4_rgba(hex_color, alpha):
    """"#0fa874", 0.1 -> "rgba(15, 168, 116, 0.1)": velature che funzionano su qualsiasi superficie."""
    h = hex_color.lstrip("#")
    return "rgba(%d, %d, %d, %s)" % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _b4_w_scale(peak):
    """(cima della scala, valori delle linee orizzontali). Cima = primo valore di B4_W_SCALE_TOPS >= picco."""
    top = next((float(c) for c in B4_W_SCALE_TOPS if peak <= c + 1e-9), None)
    if top is None:
        top = float(math.ceil(peak / 20.0) * 20.0)
    step = 5.0 if top <= 10 else (10.0 if top <= 50 else 20.0)
    ticks, v = [], 0.0
    while v <= top + 1e-9:
        ticks.append(int(v) if float(v).is_integer() else round(v, 1))
        v += step
    return top, ticks


def _b4_w_series(key, name, ramp, best_row, flat, hours, recs, day0, twilights, daylight, no_good):
    """Tutto ciò che serve al JavaScript per una serie (Attività o Trophy). ramp = B4_RAMP_*."""
    color, mid, low = ramp              # ore migliori, ore di luce, buio
    vals = [max(0.0, _b4_f(r.get(key), 0.0)) for r in recs]
    peak = None
    if not flat and not no_good:
        best_h = _b4_cont_hour(best_row, day0) if isinstance(best_row, dict) else None
        peak = _b4_find_peak(hours, vals, best_h, twilights)
        flat = peak is None                      # curva piatta anche se il Blocco 2 non l'ha segnalata
    wins = _b4_windows(hours, vals)[0] if peak is not None else []
    in_win = [any(h0 - 1e-6 <= h <= h1 + 1e-6 for h0, h1 in wins) for h in hours]
    if peak is not None and not any(in_win):
        in_win[peak] = True
    top, ticks = _b4_w_scale(max(vals) if vals else 0.0)
    if no_good:
        sub, short = "Giornata difficile: nessuna finestra buona", "poco favorevole"
    elif flat:
        sub, short = "Andamento piatto: nessuna ora si distingue", "nessun picco"
    else:
        when = _b4_windows_text(wins) if wins else _b4_hhmm(hours[peak])
        sub, short = "Il momento migliore: " + when, "migliore " + when
    head = vals[peak] if peak is not None else (max(vals) if vals else 0.0)
    return {
        "name": name, "color": color, "tint": _b4_rgba(color, 0.12), "edge": _b4_rgba(color, 0.55),
        "vals": [round(v, 2) for v in vals], "txt": [_b4_vtxt(v) for v in vals],
        "win": in_win, "bar": [color if w else (mid if d else low) for w, d in zip(in_win, daylight)],
        "peak": peak, "num": _b4_vtxt(head), "sub": sub, "short": short, "top": top, "ticks": ticks,
    }


def _b4_w_water(sim_d, recs):
    """Caselle Acqua e Ossigeno del riquadro dell'ora: testi già pronti per ogni ora (il JavaScript li mostra e basta).
    Ossigeno: do_used_mg_l (sonda inclusa, Blocco 2 v2) oppure do_actual_mg_l (Blocco 1), come il Blocco 5."""
    temps, o2, o2_txt, o2_cls = [], [], [], []
    for r in recs:
        t = _b4_f(r.get("water_temp_used", r.get("water_temp")), None)
        mg = _b4_f(r.get("do_used_mg_l"), None)
        if mg is None:
            mg = _b4_f(r.get("do_actual_mg_l"), None)
        if mg is None:
            txt, cls = "", ""
        elif mg < B4_DO_STRESS_MG_L:
            txt, cls = "stress", "alert"
        elif mg < B4_DO_LIMITED_MG_L:
            txt, cls = "attività limitata", "warn"
        else:
            txt, cls = "nessun limite", ""
        temps.append(None if t is None else "%.1f" % t)
        o2.append(None if mg is None else "%.1f" % mg)
        o2_txt.append(txt)
        o2_cls.append(cls)
    # variazione della temperatura media del giorno rispetto a 3 giorni prima (Blocco 1): uguale per tutte le ore
    micro = _b4_f(sim_d.get("micro_trend_72h", sim_d.get("thermal_trend_3d")), None)
    if micro is None:
        trend = ""
    elif abs(micro) < 0.05:
        trend = "stabile in 3 giorni"
    else:
        trend = ("%+.1f °C in 3 giorni" % micro).replace("-", "−")
    probe = _b4_f(sim_d.get("probe_used"), None) is not None
    return {"name": "Acqua · sonda" if probe else "Acqua", "temp": temps, "trend": trend,
            "o2": o2, "o2txt": o2_txt, "o2cls": o2_cls}


def create_mobile_hourly_widget(sim: dict, astro: dict, target_mode: str = "Entrambi") -> str:
    """
    Grafico orario a colonnine come pagina HTML interattiva, da mostrare con
        st.iframe(html, height=B4_W_HEIGHT)
    Restituisce "" se il timeline è vuoto o ha più di B4_W_MAX_ROWS righe: in quel caso usare
    create_mobile_plotly_chart (il Blocco 5 v4 lo fa da solo).

    Contenuto: schede Attività / Trophy / Confronta (si apre su B4_W_START_TAB[target_mode]); numero del picco
    "su 100" con le ore migliori scritte sotto; colonnine con scala laterale e linee orizzontali (scala da 0 a
    un valore tondo appena sopra il picco del giorno); corona sull'ora migliore; striscia scorrevole con un
    riquadro per ogni ora. Colonnine: colore pieno nelle ore migliori, medio nelle ore di luce, scuro col buio.
    Tocchi: una colonnina o un riquadro della striscia mostra il valore esatto in un fumetto (e centra il
    riquadro); di nuovo sulla stessa ora, o in qualsiasi altro punto della pagina, il fumetto si chiude.
    Curve piatte (trophy_flat / bai_flat del Blocco 2, o escursione < B4_FLAT_SPAN) e no_good_window: niente
    corona e niente ore migliori, il testo lo dice.
    Sotto, il riquadro dell'ora selezionata, con le frecce ‹ › per scorrere le ore: acqua °C, ossigeno mg/L e i 6
    fattori (come create_mobile_factors_chart). La selezione è una sola per tutto il grafico. Senza selezione: l'ora
    migliore della scheda aperta.
    """
    ctx = _b4_prepare(sim, astro, target_mode)
    rows = ctx["rows"]
    if not rows or len(rows) > B4_W_MAX_ROWS:
        return ""
    sim_d = sim if isinstance(sim, dict) else {}
    recs = [d["r"] for d in rows]
    hours = [d["h"] for d in rows]
    diffs = sorted(b - a for a, b in zip(hours, hours[1:]) if b - a > 1e-9)
    step = diffs[len(diffs) // 2] if diffs else 1.0

    astro_d = ctx["astro"]
    sr = _b4_f(astro_d.get("sunrise_dec"), None)
    ss = _b4_f(astro_d.get("sunset_dec"), None)
    sun_ok = sr is not None and ss is not None and 0.0 <= sr < ss <= 24.0
    twilights = []
    if sun_ok:
        for dk in range(int(math.floor(hours[0] / 24.0)), int(math.floor(hours[-1] / 24.0)) + 1):
            twilights += [24.0 * dk + sr, 24.0 * dk + ss]
    # un'ora è "di luce" se il suo centro cade tra alba e tramonto (senza alba/tramonto: tutte di luce)
    daylight = [(sr <= (h % 24.0) + step / 2.0 < ss) if sun_ok else True for h in hours]

    no_good = ctx["flags"]["no_good_window"]
    common = (hours, recs, ctx["day0"], twilights, daylight, no_good)
    att = _b4_w_series("catch_rate", "Attività", B4_RAMP_BAI, ctx["best_hour"], bool(sim_d.get("bai_flat")), *common)
    tro = _b4_w_series("trophy_rate", "Trophy", B4_RAMP_TROPHY, ctx["best_trophy_hour"],
                       bool(sim_d.get("trophy_flat")), *common)

    def axis_labels(every):
        out = []
        for h in hours:
            hh = h % 24.0
            whole = abs(hh - round(hh)) < 1e-6
            out.append("%02d" % (int(round(hh)) % 24) if whole and int(round(hh)) % every == 0 else "")
        return out

    both = att if att["top"] >= tro["top"] else tro    # "Confronta": una sola scala, quella della serie più alta
    facts = [_b4_factor_list(r) for r in recs]
    # ora dei fattori senza selezione: il picco della serie; con la curva piatta l'ora col valore più alto
    start_att = att["peak"] if att["peak"] is not None else max(range(len(recs)), key=lambda i: att["vals"][i])
    start_tro = tro["peak"] if tro["peak"] is not None else start_att
    data = {
        "labels": [str(r.get("time_label") or _b4_hhmm(h)) for r, h in zip(recs, hours)],
        "ax3": axis_labels(3),
        "att": att, "tro": tro,
        "start": B4_W_START_TAB.get(ctx["mode"], "att"),
        "crown": B4_CROWN_PATH, "pad": int(B4_W_TOUCH_PAD),
        "plot": list(_B4_W_PLOT), "plotCmp": list(_B4_W_PLOT_CMP),
        "cmp": {"top": both["top"], "ticks": both["ticks"]},
        "fac": {"names": [name for name, _ in _B4_FACTORS], "start": start_att, "startTro": start_tro,
                "vals": [[None if v is None else int(round(v)) for _, v in f] for f in facts],
                "weak": [_b4_extremes_text(f) for f in facts]},
        "wat": _b4_w_water(sim_d, recs),
    }
    payload = _b4_json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = _B4_W_TEMPLATE
    for token, value in (("__FONT__", B4_W_FONT_CSS.replace("&", "&amp;")), ("__FONTFAMILY__", B4_UI["font"]),
                         ("__CARD__", B4_W_CARD), ("__BORDER__", B4_W_BORDER), ("__INK__", B4_W_INK),
                         ("__INK2__", B4_W_INK_2), ("__INK3__", B4_W_INK_3), ("__LINEBASE__", B4_UI["line_base"]),
                         ("__LINE__", B4_UI["line"]), ("__OVERLAYBD__", B4_UI["overlay_border"]),
                         ("__OVERLAY__", B4_UI["overlay_solid"]), ("__ACCENTBG__", _b4_rgba(B4_COL_BAI, 0.1)),
                         ("__ACCENT__", B4_COL_BAI), ("__RADIUS__", str(B4_UI["radius"])),
                         ("__VIEWH__", str(_B4_W_VIEW_H)), ("__FACH__", str(_B4_W_FAC_H)),
                         ("__TRACK__", B4_UI["track"]), ("__WARN__", B4_COL_WARN), ("__ALERT__", B4_COL_ALERT)):
        html = html.replace(token, value)
    return html.replace("__DATA__", payload)          # per ultimo: i dati non vengono toccati dalle sostituzioni


_B4_W_TEMPLATE = r"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Andamento orario</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="__FONT__">
<style>
:root{--g:clamp(2px,1.1vw,10px)}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:transparent}
body{font-family:__FONTFAMILY__;color:__INK__;
  -webkit-tap-highlight-color:transparent;-webkit-user-select:none;user-select:none;-webkit-text-size-adjust:100%}
button{font-family:inherit;color:inherit;-webkit-appearance:none;appearance:none}
#w{display:flex;flex-direction:column;gap:12px;padding:2px 1px 4px}
.tabs{display:flex}
.tab{position:relative;flex:1 1 0;min-width:0;height:36px;margin:0 0 0 -1px;border:1px solid __BORDER__;border-radius:0;
  background:transparent;color:__INK__;font-size:14px;font-weight:400;cursor:pointer}
.tab:first-child{margin-left:0;border-radius:__RADIUS__px 0 0 __RADIUS__px}
.tab:last-child{border-radius:0 __RADIUS__px __RADIUS__px 0}
.tab.on{z-index:1;border-color:__ACCENT__;color:__ACCENT__;background:__ACCENTBG__}
.tab:focus-visible,.bar:focus-visible,.chip:focus-visible{outline:2px solid __INK__;outline-offset:2px}
#view{height:__VIEWH__px}
.card{background:__CARD__;border:1px solid __BORDER__;border-radius:__RADIUS__px}
.main{height:100%;padding:16px;display:flex;flex-direction:column}
.hero{display:flex;align-items:baseline;gap:4px}
.num{font-size:40px;font-weight:600;line-height:1;font-variant-numeric:tabular-nums}
.of{font-size:16px;font-weight:400;color:__INK3__}
.sub{margin-top:6px;font-size:14px;line-height:18px;color:__INK2__;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chart{display:flex;gap:8px;margin-top:10px}
.axis{position:relative;flex:0 0 22px}
.axis span{position:absolute;right:0;font-size:12px;line-height:12px;color:__INK3__;font-variant-numeric:tabular-nums}
.plot{position:relative;flex:1 1 auto;min-width:0}
.gl{position:absolute;left:0;right:0;height:0;border-top:1px solid __LINE__}
.gl.base{border-top-color:__LINEBASE__}
.bars{position:absolute;top:0;bottom:0;left:3px;right:3px;display:flex;align-items:flex-end;gap:var(--g)}
.col{position:relative;flex:1 1 0;min-width:0;height:100%;display:flex;flex-direction:column;align-items:center;
  justify-content:flex-end}
.crown{display:block;flex:0 0 auto}
.bar{display:block;flex:0 0 auto;width:100%;margin:0;padding:0;border:0;background:transparent;cursor:pointer}
.bar span{display:block;width:100%;border-radius:4px 4px 1px 1px;transition:opacity .15s}
.dim .bar span{opacity:.45}
.dim .bar.on span{opacity:1;box-shadow:0 0 0 2px __INK__}
.bub{position:absolute;z-index:3;left:50%;transform:translateX(-50%);display:flex;flex-direction:column;
  align-items:center;padding:5px 10px;border-radius:8px;background:__OVERLAY__;border:1px solid __OVERLAYBD__;
  color:__INK__;white-space:nowrap;line-height:1.15;box-shadow:0 8px 24px rgba(0,0,0,.55);pointer-events:none}
.bub b{font-size:15px;font-weight:600}
.bub i{font-style:normal;font-size:12px;color:__INK2__}
.bub.l{left:0;transform:none}
.bub.r{left:auto;right:0;transform:none}
.hrs{display:flex;gap:var(--g);padding:0 3px 0 33px;margin-top:6px}
.hrs span{flex:1 1 0;min-width:0;text-align:center;font-size:12px;line-height:13px;height:13px;color:__INK3__;
  white-space:nowrap;overflow:visible}
.cmp{height:100%;display:grid;grid-template-rows:repeat(2,minmax(0,1fr));gap:8px}
.stk{min-height:0;padding:10px 12px;display:flex;flex-direction:column;justify-content:space-between}
.stk .hero{min-width:0}
.stk .num{font-size:26px}
.stk .of{font-size:13px}
.stk .nm{flex:1 1 auto;min-width:0;margin-left:8px;font-size:13px;color:__INK2__;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.ccol{position:relative;flex:1 1 0;min-width:0;height:100%;margin:0;padding:0;border:0;background:transparent;
  cursor:pointer;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}
.ccol .cb{display:block;width:100%;border-radius:3px 3px 1px 1px;transition:opacity .15s}
.dim .ccol .cb{opacity:.45}
.dim .ccol.on .cb{opacity:1;box-shadow:0 0 0 2px __INK__}
.ccol:focus-visible,.mcol:focus-visible{outline:2px solid __INK__;outline-offset:2px}
.strip{position:relative;display:flex;gap:8px;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x proximity;
  scrollbar-width:none;-webkit-overflow-scrolling:touch;padding:2px;
  -webkit-mask-image:linear-gradient(90deg,transparent 0,#000 20px,#000 calc(100% - 20px),transparent 100%);
  mask-image:linear-gradient(90deg,transparent 0,#000 20px,#000 calc(100% - 20px),transparent 100%)}
.strip::-webkit-scrollbar{display:none}
.chip{flex:0 0 64px;height:62px;scroll-snap-align:center;border-radius:__RADIUS__px;background:__CARD__;
  border:1px solid __BORDER__;cursor:pointer;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:3px;padding:0}
.chip.wide{flex-basis:84px}
.chip .h{display:flex;align-items:center;gap:2px;font-size:12px;line-height:15px;color:__INK2__}
.chip .v{font-size:18px;line-height:22px;font-weight:600;font-variant-numeric:tabular-nums}
.chip.wide .v{font-size:16px}
.chip.on{border-color:__INK__ !important;box-shadow:inset 0 0 0 1px __INK__}
.fac{height:__FACH__px;padding:12px 16px 14px;display:flex;flex-direction:column}
.fhead{display:flex;align-items:center;justify-content:space-between;gap:8px}
.ftitle{font-size:16px;font-weight:600}
.fnav{display:flex;align-items:center;gap:4px}
.fstep{width:40px;height:40px;margin:0;padding:0;border:1px solid __BORDER__;border-radius:__RADIUS__px;
  background:transparent;color:__INK__;cursor:pointer;display:flex;align-items:center;justify-content:center}
.fstep:disabled{opacity:.3;cursor:default}
.fstep:focus-visible{outline:2px solid __INK__;outline-offset:2px}
.fhour{min-width:56px;text-align:center;font-size:16px;font-weight:600;font-variant-numeric:tabular-nums}
.wq{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}
.wt{min-width:0;padding:8px 10px;border-radius:__RADIUS__px;background:__TRACK__;display:flex;flex-direction:column;
  gap:1px}
.wn,.ws{font-size:13px;line-height:16px;color:__INK2__;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wv{font-size:22px;line-height:26px;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}
.wv small{margin-left:3px;font-size:14px;font-weight:400;color:__INK2__}
.ws.warn{color:__WARN__}
.ws.alert{color:__ALERT__}
.fsub{margin-top:12px;font-size:13px;line-height:17px;color:__INK2__;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.frows{margin-top:auto;padding-top:10px;display:flex;flex-direction:column;gap:9px}
.frow{display:grid;grid-template-columns:92px minmax(0,1fr) 32px;align-items:center;gap:10px}
.fname{font-size:14px;line-height:18px}
.ftrack{height:14px;border-radius:4px;background:__TRACK__;overflow:hidden}
.ftrack span{display:block;height:100%;border-radius:4px;transition:width .2s}
.fval{font-size:14px;line-height:18px;text-align:right;font-variant-numeric:tabular-nums}
</style>
</head>
<body>
<div id="w">
  <div class="tabs" role="group" aria-label="Indice mostrato">
    <button type="button" class="tab" data-tab="att">Attività</button>
    <button type="button" class="tab" data-tab="tro">Trophy</button>
    <button type="button" class="tab" data-tab="cmp">Confronta</button>
  </div>
  <div id="view"></div>
  <div id="strip" class="strip" role="group" aria-label="Punteggio ora per ora"></div>
  <div id="fac" class="card fac" aria-live="polite"></div>
</div>
<script>
(function () {
  "use strict";
  var D = __DATA__;
  var N = D.labels.length;
  var state = { tab: D.start, sel: null };
  var view = document.getElementById("view");
  var fac = document.getElementById("fac");
  var strip = document.getElementById("strip");
  var tabs = document.querySelectorAll("[data-tab]");

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function series() { return state.tab === "tro" ? D.tro : D.att; }
  function crown(size, color) {
    return '<svg class="crown" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" aria-hidden="true">' +
      '<path fill="' + color + '" d="' + D.crown + '"/></svg>';
  }

  // Grafico a colonnine: la colonnina (un <button>) è alta quanto il valore + D.pad px sopra; nient'altro risponde.
  // Linee orizzontali e numeri della scala laterale per i valori `ticks`, alla quota y(v).
  function marks(ticks, y) {
    var m = { lines: "", axis: "" };
    ticks.forEach(function (v, k) {
      m.lines += '<div class="gl' + (k === 0 ? " base" : "") + '" style="top:' + (y(v) - 1) + 'px"></div>';
      if (k > 0) m.axis += '<span style="top:' + (y(v) - 7) + 'px">' + v + "</span>";
    });
    return m;
  }
  function hrsRow() {
    return '<div class="hrs">' + D.ax3.map(function (t) { return "<span>" + t + "</span>"; }).join("") + "</div>";
  }
  // Scala laterale + area del grafico (alta P) con le colonne `cols` e l'eventuale `extra`, poi le ore sotto.
  function plotBox(P, m, cols, extra) {
    return '<div class="chart"><div class="axis" style="height:' + P + 'px">' + m.axis + '</div><div class="plot" ' +
      'style="height:' + P + 'px">' + m.lines + '<div class="bars' + (state.sel !== null ? " dim" : "") + '">' +
      cols + "</div>" + (extra || "") + "</div></div>" + hrsRow();
  }

  function chart(S) {
    var P = D.plot[0], H = D.plot[1], pad = D.pad, cs = 22;
    function y(v) { return P - Math.round(v / S.top * H); }
    var m = marks(S.ticks, y), lines = m.lines, axis = m.axis, cols = "";
    for (var i = 0; i < N; i++) {
      var h = Math.max(3, Math.round(S.vals[i] / S.top * H));
      var on = state.sel === i, isPeak = S.peak === i;
      var cell = '<div class="col">';
      if (on) {
        var side = i <= 1 ? " l" : (i >= N - 2 ? " r" : "");
        cell += '<div class="bub' + side + '" style="bottom:' + (h + pad + (isPeak ? cs : 0) + 6) +
          'px"><b>' + esc(S.txt[i]) + "</b><i>" + esc(D.labels[i]) + "</i></div>";
      }
      if (isPeak) cell += crown(cs, S.color);
      cell += '<button type="button" class="bar' + (on ? " on" : "") + '" data-i="' + i + '" aria-label="' +
        esc(D.labels[i] + ", " + S.name + " " + S.txt[i] + " su 100" + (isPeak ? ", ora migliore" : "")) +
        '" style="height:' + (h + pad) + "px;padding-top:" + pad + 'px"><span style="height:' + h +
        "px;background:" + S.bar[i] + '"></span></button></div>';
      cols += cell;
    }
    return plotBox(P, { lines: lines, axis: axis }, cols);
  }

  function mainCard(S) {
    return '<div class="card main"><div class="hero"><span class="num" style="color:' + S.color + '">' +
      esc(S.num) + '</span><span class="of">/100</span></div><div class="sub">' + esc(S.sub) + "</div>" +
      chart(S) + "</div>";
  }
  // "Confronta" (variante A): Attività sopra, Trophy sotto, a tutta larghezza e con la stessa scala (D.cmp).
  // Niente fumetti: l'ora toccata prende il posto del picco nella riga del titolo. Risponde tutta la colonna.
  function stackCard(S) {
    var P = D.plotCmp[0], H = D.plotCmp[1], top = D.cmp.top, on = state.sel !== null, cols = "";
    var m = marks(D.cmp.ticks, function (v) { return P - Math.round(v / top * H); });
    for (var i = 0; i < N; i++) {
      var h = Math.max(2, Math.round(S.vals[i] / top * H)), isPeak = S.peak === i;
      cols += '<button type="button" class="ccol' + (state.sel === i ? " on" : "") + '" data-i="' + i +
        '" aria-label="' + esc(D.labels[i] + ", " + S.name + " " + S.txt[i] + " su 100" +
        (isPeak ? ", ora migliore" : "")) + '">' + (isPeak ? crown(14, S.color) : "") +
        '<span class="cb" style="height:' + h + "px;background:" + S.bar[i] + '"></span></button>';
    }
    return '<div class="card stk"><div class="hero"><span class="num" style="color:' + S.color + '">' +
      esc(on ? S.txt[state.sel] : S.num) + '</span><span class="of">/100</span><span class="nm">' +
      esc(S.name + " · " + (on ? "alle " + D.labels[state.sel] : S.short)) + "</span></div>" +
      plotBox(P, m, cols) + "</div>";
  }

  function chips() {
    var cmp = state.tab === "cmp", S = series(), out = "";
    for (var i = 0; i < N; i++) {
      var marks = "";
      if (cmp) {
        if (D.att.peak === i) marks += crown(13, D.att.color);
        if (D.tro.peak === i) marks += crown(13, D.tro.color);
      } else if (S.peak === i) {
        marks = crown(13, S.color);
      }
      var style = S.win[i] ? "background:" + S.tint + ";border-color:" + (S.peak === i ? S.color : S.edge) :
        (S.peak === i ? "border-color:" + S.color : "");
      var val = cmp ? D.att.txt[i] + " · " + D.tro.txt[i] : S.txt[i];
      var said = cmp ? "attività " + D.att.txt[i] + ", trophy " + D.tro.txt[i] : S.name + " " + S.txt[i];
      out += '<button type="button" class="chip' + (cmp ? " wide" : "") + (state.sel === i ? " on" : "") +
        '" data-i="' + i + '" aria-label="' + esc(D.labels[i] + ": " + said) + '" style="' + style + '">' +
        '<span class="h">' + marks + esc(D.labels[i]) + '</span><span class="v"' +
        (!cmp && S.peak === i ? ' style="color:' + S.color + '"' : "") + ">" + esc(val) + "</span></button>";
    }
    return out;
  }

  function center(how) {
    var S = series();
    var i = state.sel !== null ? state.sel : (S.peak !== null ? S.peak : Math.floor(N / 2));
    var c = strip.children[i];
    if (!c) return;
    var left = Math.max(0, c.offsetLeft - (strip.clientWidth - c.offsetWidth) / 2);
    try { strip.scrollTo({ left: left, behavior: how === "smooth" ? "smooth" : "auto" }); }
    catch (e) { strip.scrollLeft = left; }
  }

  // Riquadro dell'ora (acqua, ossigeno, fattori): l'ora selezionata; senza selezione, l'ora migliore della scheda
  // (Confronta: quella dell'Attività).
  function facHour() {
    return state.sel !== null ? state.sel : (state.tab === "tro" ? D.fac.startTro : D.fac.start);
  }
  var CHEV = { "-1": "M15 6l-6 6 6 6", "1": "M9 6l6 6-6 6" };
  function step(dir) {
    var i = facHour() + dir;
    return '<button type="button" class="fstep" data-step="' + dir + '" aria-label="' +
      (dir < 0 ? "Ora precedente" : "Ora successiva") + '"' + (i < 0 || i >= N ? " disabled" : "") + '>' +
      '<svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="' + CHEV[String(dir)] +
      '" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      "</button>";
  }
  // Casella di acqua o ossigeno: nome, valore con l'unità, riga sotto (cls "warn" / "alert" colora la riga).
  function tile(name, val, unit, note, cls) {
    return '<div class="wt"><span class="wn">' + esc(name) + '</span><span class="wv">' +
      (val === null ? "n/d" : esc(val) + "<small>" + unit + "</small>") + '</span><span class="ws' +
      (cls ? " " + cls : "") + '">' + esc(note || "\u00a0") + "</span></div>";
  }
  function factors() {
    var F = D.fac, W = D.wat, i = facHour(), color = state.tab === "tro" ? D.tro.color : D.att.color;
    var rows = F.names.map(function (nm, k) {
      var v = F.vals[i][k];
      return '<div class="frow"><span class="fname">' + esc(nm) + '</span><span class="ftrack"><span style="width:' +
        (v === null ? 0 : v) + "%;background:" + color + '"></span></span><span class="fval">' +
        (v === null ? "n/d" : v) + "</span></div>";
    }).join("");
    var tiles = '<div class="wq">' + tile(W.name, W.temp[i], "°C", W.trend, "") +
      tile("Ossigeno", W.o2[i], "mg/L", W.o2txt[i], W.o2cls[i]) + "</div>";
    fac.innerHTML = '<div class="fhead"><span class="ftitle">' + (state.sel === null ? "Ora migliore" :
      "Ora selezionata") + '</span><span class="fnav">' + step(-1) + '<span class="fhour">' + esc(D.labels[i]) +
      "</span>" + step(1) + "</span></div>" + tiles + '<div class="fsub">' +
      esc(["Fattori", F.weak[i]].filter(Boolean).join(" · ")) + '</div><div class="frows">' + rows + "</div>";
  }

  function render(scroll) {
    view.innerHTML = state.tab === "cmp" ?
      '<div class="cmp">' + stackCard(D.att) + stackCard(D.tro) + "</div>" : mainCard(series());
    var keep = strip.scrollLeft;
    strip.innerHTML = chips();
    strip.scrollLeft = keep;
    for (var k = 0; k < tabs.length; k++) {
      var on = tabs[k].getAttribute("data-tab") === state.tab;
      tabs[k].className = "tab" + (on ? " on" : "");
      tabs[k].setAttribute("aria-pressed", on ? "true" : "false");
    }
    factors();
    if (scroll) center(scroll);
  }

  function clearSel() {
    if (state.sel !== null) { state.sel = null; render(null); }
  }

  // Un solo gestore: colonnina o riquadro -> seleziona (o deseleziona la stessa ora); frecce dei fattori -> ora
  // precedente o successiva; scheda -> cambia vista; riquadro dei fattori -> niente (si legge senza perdere l'ora);
  // qualsiasi altro punto (spazio vuoto sopra una colonnina compreso) -> chiude il fumetto.
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target : null;
    var stepBtn = t ? t.closest("[data-step]") : null;
    if (stepBtn) {
      if (!stepBtn.disabled) {
        state.sel = Math.max(0, Math.min(N - 1, facHour() + parseInt(stepBtn.getAttribute("data-step"), 10)));
        render("smooth");
      }
      return;
    }
    if (t && t.closest("#fac")) return;
    var hit = t ? t.closest("[data-i]") : null;
    if (hit) {
      var i = parseInt(hit.getAttribute("data-i"), 10);
      state.sel = state.sel === i ? null : i;
      render(state.sel !== null ? "smooth" : null);
      return;
    }
    var tab = t ? t.closest("[data-tab]") : null;
    if (tab) {
      state.tab = tab.getAttribute("data-tab");
      render(state.sel === null ? "auto" : null);
      return;
    }
    clearSel();
  });

  // Tocchi fuori dal grafico (resto della pagina Streamlit): st.iframe dà accesso alla pagina che lo contiene.
  try {
    var host = window.parent && window.parent !== window ? window.parent.document : null;
    if (host) {
      var outside = function () { clearSel(); };
      host.addEventListener("click", outside, true);
      window.addEventListener("pagehide", function () {
        try { host.removeEventListener("click", outside, true); } catch (e) { /* pagina già chiusa */ }
      });
    }
  } catch (e) { /* senza accesso alla pagina: si chiude toccando dentro il grafico */ }

  render(null);
  center("auto");
  window.addEventListener("load", function () { if (state.sel === null) center("auto"); });
})();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------------------
# GRAFICO 1 — TELEMETRIA ORARIA (Plotly: dalla v3 è la riserva del grafico a colonnine)
# ------------------------------------------------------------------------------
def create_mobile_plotly_chart(
    sim: dict,
    astro: dict,
    target_mode: str = "Entrambi",
    focus_hour: dict = None
) -> go.Figure:
    """
    Telemetria oraria a righe separate, leggibile a colpo d'occhio su iPhone.

    target_mode:
        "Numeri"   -> una riga: Attività (BAI)
        "Trophy"   -> una riga: Trophy (big bass > 2 kg)
        "Entrambi" -> due righe (BAI sopra, Trophy sotto), ciascuna con la propria scala
    In fondo c'è sempre una striscia sottile con la temperatura dell'acqua (se disponibile).

    sim:        dict del Blocco 2 (con 'timeline', 'best_hour', 'best_trophy_hour') oppure, come
                nella v1, la sola lista timeline.
    astro:      dict con 'sunrise_dec' e 'sunset_dec' (ore decimali). Facoltativo: None va bene.
    focus_hour: facoltativo. Riga oraria (dict) o ora numerica da evidenziare con una linea
                verticale (es. l'ora scelta dall'utente o l'ora attuale). Nella v1 era ignorato.

    Ogni riga mostra: titolo + picco, "ore migliori" evidenziate, curva con area. Se la curva è
    piatta non si disegna alcun picco. Se `sim` contiene no_good_window=True (chiave futura del
    Blocco 2) il titolo lo dice e non vengono evidenziate finestre.
    """
    ctx = _b4_prepare(sim, astro, target_mode)
    rows = ctx["rows"]
    if not rows:
        return _b4_empty_figure("Nessun dato orario disponibile")

    mode = ctx["mode"]
    flags = ctx["flags"]
    astro = ctx["astro"]
    recs = [d["r"] for d in rows]
    hours = [d["h"] for d in rows]

    # --- asse dei tempi: vero asse "date" (ticks ogni 3 ore, tooltip con l'ora) ---
    day_first = ctx["day0"]
    has_date = day_first is not None
    if day_first is None:
        day_first = _b4_dt.datetime(2000, 1, 10)
    xs = [_b4_ts(day_first, h) for h in hours]
    x_lo = _b4_ts(day_first, hours[0] - 0.5)
    x_hi = _b4_ts(day_first, hours[-1] + 0.5)
    span_h = hours[-1] - hours[0]       # ticks ogni 3 h per un giorno; più radi se i dati coprono più giorni
    tick_step_h = 3 if span_h <= 30 else (6 if span_h <= 54 else (12 if span_h <= 100 else 24))
    tick_fmt = "%d/%m" if tick_step_h >= 24 else "%H:%M"
    tickvals_x, ticktext_x = _b4_time_ticks(day_first, hours, tick_step_h, tick_fmt)
    first_k = int(math.floor(hours[0] / 24.0))
    n_days = int(math.floor(hours[-1] / 24.0)) - first_k + 1
    day_ks = list(range(first_k, first_k + max(1, min(n_days, 8))))

    # --- alba / tramonto ---
    sr = _b4_f(astro.get("sunrise_dec"), None)
    ss = _b4_f(astro.get("sunset_dec"), None)
    sun_ok = sr is not None and ss is not None and 0.0 <= sr < ss <= 24.0
    twilights = []
    if sun_ok:
        for dk in day_ks:
            twilights += [24.0 * dk + sr, 24.0 * dk + ss]

    # --- curve da mostrare ---
    metrics = []
    if mode in ("Numeri", "Entrambi"):
        metrics.append({"key": "catch_rate", "title": "Attività (BAI)", "short": "Attività",
                        "color": B4_COL_BAI, "symbol": "star", "psize": 13,
                        "best": ctx["best_hour"]})
    if mode in ("Trophy", "Entrambi"):
        metrics.append({"key": "trophy_rate", "title": "Trophy (big bass >2 kg)", "short": "Trophy",
                        "color": B4_COL_TROPHY, "symbol": "diamond", "psize": 12,
                        "best": ctx["best_trophy_hour"]})
    row_h = B4_ROW_H_DUAL if len(metrics) > 1 else B4_ROW_H_SINGLE

    # --- temperatura dell'acqua (striscia) ---
    water = [_b4_f(r.get("water_temp_used", r.get("water_temp")), None) for r in recs]
    water_ok = sum(1 for w in water if w is not None) >= 2

    # --- piano dei blocchi (dall'alto in basso) ---
    blocks = []
    for m in metrics:
        vals = [_b4_f(r.get(m["key"]), 0.0) for r in recs]
        best_h = _b4_cont_hour(m["best"], ctx["day0"]) if m["best"] else None
        idx = _b4_find_peak(hours, vals, best_h, twilights)
        wins, step = _b4_windows(hours, vals)
        m.update({"vals": vals, "peak": idx, "wins": [] if flags["no_good_window"] else wins, "step": step})
        blocks.append({"kind": "main", "m": m, "header_h": B4_HEADER_H, "plot_h": row_h})
    if water_ok:
        blocks.append({"kind": "strip", "header_h": B4_STRIP_HEADER_H, "plot_h": B4_STRIP_H})

    # --- tooltip: UNA lettura completa dell'ora (ora + tutte le serie + contesto), uguale su ogni grafico ---
    labels = [str(r.get("time_label") or _b4_hhmm(h)) for r, h in zip(recs, hours)]
    readout_rows = []
    for b in blocks:
        if b["kind"] == "main":
            readout_rows.append((b["m"]["short"], b["m"]["color"], [_b4_vtxt(v) for v in b["m"]["vals"]]))
    if water_ok:
        readout_rows.append(("Acqua", B4_COL_WATER, [("%.1f °C" % w) if w is not None else None for w in water]))
    readouts = []
    for i, r in enumerate(recs):
        lines = ["<b>%s</b>" % _b4_esc(labels[i])]
        for name, rcolor, texts in readout_rows:
            if texts[i] is not None:
                lines.append("%s %s <b>%s</b>" % (_b4_dot(rcolor), name, texts[i]))
        lines.extend(_b4_muted(t) for t in _b4_details(r))
        readouts.append("<br>".join(lines))

    y_px = 0.0
    for b in blocks:
        y_px += b["header_h"]
        b["top_px"] = y_px
        y_px += b["plot_h"]
        b["bot_px"] = y_px
    plot_total = y_px
    fig_h = int(round(B4_MARGIN_T + plot_total + B4_MARGIN_B))
    for b in blocks:
        b["y_top"] = 1.0 - b["top_px"] / plot_total
        b["y_bot"] = 1.0 - b["bot_px"] / plot_total

    # --- focus: linea verticale opzionale ---
    focus_h = _b4_cont_hour(focus_hour, ctx["day0"]) if focus_hour is not None else None

    traces, shapes, annotations = [], [], []
    layout_axes = {}
    n = len(blocks)

    for k, b in enumerate(blocks, start=1):
        xid = "x" if k == 1 else "x%d" % k
        yid = "y" if k == 1 else "y%d" % k
        xkey = "xaxis" if k == 1 else "xaxis%d" % k
        ykey = "yaxis" if k == 1 else "yaxis%d" % k
        last = (k == n)

        # fascia "luce del giorno" (velo caldo) su ogni riga
        if sun_ok:
            for dk in day_ks:
                shapes.append(dict(type="rect", xref=xid, yref="paper",
                                   x0=_b4_ts(day_first, 24.0 * dk + sr), x1=_b4_ts(day_first, 24.0 * dk + ss),
                                   y0=b["y_bot"], y1=b["y_top"], fillcolor=B4_DAYLIGHT,
                                   line=dict(width=0), layer="below"))

        if b["kind"] == "main":
            m = b["m"]
            vals = m["vals"]
            peak_val = max(vals) if vals else 0.0
            tickvals, range_top = _b4_ticks(peak_val)
            color = m["color"]

            # ore migliori: fasce evidenziate
            for h0, h1 in m["wins"]:
                shapes.append(dict(type="rect", xref=xid, yref="paper",
                                   x0=_b4_ts(day_first, h0 - m["step"] / 2.0),
                                   x1=_b4_ts(day_first, h1 + m["step"] / 2.0),
                                   y0=b["y_bot"], y1=b["y_top"],
                                   fillcolor=_b4_rgba(color, 0.16), line=dict(width=0), layer="below"))

            # linea di focus
            if focus_h is not None:
                shapes.append(dict(type="line", xref=xid, yref="paper",
                                   x0=_b4_ts(day_first, focus_h), x1=_b4_ts(day_first, focus_h),
                                   y0=b["y_bot"], y1=b["y_top"],
                                   line=dict(color="rgba(242, 242, 247, 0.80)", width=1.6)))

            # curva (tooltip completo al tocco)
            traces.append(go.Scatter(
                x=xs, y=vals, xaxis=xid, yaxis=yid, mode="lines", name=m["short"],
                line=dict(color=color, width=2.6, shape="linear"),
                fill="tozeroy", fillcolor=_b4_rgba(color, 0.12),
                customdata=readouts,
                hovertemplate="%{customdata}<extra></extra>", showlegend=False))

            # picco: un solo punto con l'ora
            pk = m["peak"]
            if pk is not None and not flags["no_good_window"]:
                px = hours[pk]
                span = (hours[-1] - hours[0]) or 1.0
                rel = (px - hours[0]) / span
                tpos = "top right" if rel < 0.08 else ("top left" if rel > 0.92 else "top center")
                traces.append(go.Scatter(
                    x=[xs[pk]], y=[vals[pk]], xaxis=xid, yaxis=yid, mode="markers+text",
                    marker=dict(size=m["psize"], symbol=m["symbol"], color=B4_INK_1,
                                line=dict(width=2, color=B4_SURFACE)),
                    text=[_b4_hhmm(px)], textposition=tpos,
                    textfont=dict(size=12, color=B4_INK_1), cliponaxis=False,
                    hoverinfo="skip", showlegend=False))

            # titolo a due righe sopra il grafico
            head = "%s <b>%s</b>" % (_b4_dot(color), m["title"])
            if pk is None:
                l1 = head + " · nessun picco"
                l2 = "andamento piatto: nessuna ora si distingue"
            elif flags["no_good_window"]:
                l1 = head + " · poco favorevole"
                l2 = "nessuna finestra buona oggi"
            else:
                l1 = head + " · picco <b>%s</b> (%.0f)" % (_b4_hhmm(hours[pk]), vals[pk])
                l2 = ("ore migliori: " + _b4_windows_text(m["wins"])) if m["wins"] else ""
                if flags["window_quality"] == "scarsa":
                    l2 = (l2 + " · " if l2 else "") + "qualità scarsa"
            annotations.append(dict(
                text=l1 + ("<br>" + _b4_muted(l2) if l2 else ""),
                xref="paper", yref="paper", x=0, y=b["y_top"], xanchor="left", yanchor="bottom",
                xshift=-(B4_MARGIN_L - 6), yshift=B4_HEADER_GAP, align="left", showarrow=False,
                font=dict(size=13, color=B4_INK_1)))

            layout_axes[ykey] = dict(
                domain=[b["y_bot"], b["y_top"]], anchor=xid, range=[0, range_top], automargin=False,
                tickvals=tickvals, tickformat=".0f", ticks="", showgrid=True, gridcolor=B4_GRID,
                gridwidth=1, zeroline=False, showline=False, fixedrange=True,
                tickfont=dict(size=11, color=B4_INK_3))
        else:
            ws = [w for w in water if w is not None]
            lo, hi = min(ws), max(ws)
            pad = max(1.0, 0.5 * (hi - lo))
            traces.append(go.Scatter(
                x=xs, y=[w if w is not None else None for w in water], xaxis=xid, yaxis=yid,
                mode="lines", name="Acqua", connectgaps=True,
                line=dict(color=B4_COL_WATER, width=2.2, shape="linear"),
                customdata=readouts,
                hovertemplate="%{customdata}<extra></extra>",
                showlegend=False))
            rng = ("%.1f–%.1f" % (lo, hi)) if (hi - lo) >= 0.05 else ("%.1f" % hi)
            annotations.append(dict(
                text="%s Acqua <b>%s</b> °C" % (_b4_dot(B4_COL_WATER), rng),
                xref="paper", yref="paper", x=0, y=b["y_top"], xanchor="left", yanchor="bottom",
                xshift=-(B4_MARGIN_L - 6), yshift=B4_STRIP_GAP, align="left", showarrow=False,
                font=dict(size=12, color=B4_INK_2)))
            layout_axes[ykey] = dict(
                domain=[b["y_bot"], b["y_top"]], anchor=xid, range=[lo - pad, hi + pad], automargin=False,
                showticklabels=False, ticks="", showgrid=False, zeroline=False, showline=False,
                fixedrange=True)

        layout_axes[xkey] = dict(
            type="date", domain=[0, 1], anchor=yid, range=[x_lo, x_hi], automargin=False,
            tickmode="array", tickvals=tickvals_x, ticktext=ticktext_x, hoverformat="%H:%M",
            showticklabels=last, ticks="outside", ticklen=6, tickcolor="rgba(0, 0, 0, 0)", tickangle=0,
            showgrid=True, gridcolor=B4_GRID, gridwidth=1,
            zeroline=False, showline=False, fixedrange=True,
            tickfont=dict(size=11, color=B4_INK_3),
            showspikes=True, spikemode="across", spikesnap="data", spikedash="solid",
            spikethickness=1, spikecolor="rgba(242, 242, 247, 0.35)")

    # piè di pagina: data, alba/tramonto, avvertenza sulla scala. "sole" e non "alba–tramonto": con quest'ultimo la riga
    # (Arial 10.5 px) arriva a 334 px ed esce dal riquadro sugli schermi da 320 e 360 px; con "sole" si ferma a 286 px.
    foot = []
    if has_date:
        foot.append(_b4_day_label(day_first))
    if sun_ok:
        foot.append("sole %s–%s" % (_b4_hhmm(sr), _b4_hhmm(ss)))
    if B4_FOOTER_NOTE:
        foot.append(B4_FOOTER_NOTE)
    foot = [f for f in foot if f]
    if foot:
        annotations.append(dict(
            text=_b4_esc(" · ").join(_b4_esc(f) for f in foot),
            xref="paper", yref="paper", x=0, y=0, xanchor="left", yanchor="top",
            xshift=-(B4_MARGIN_L - 6), yshift=-28, align="left", showarrow=False,
            font=dict(size=10.5, color=B4_INK_3)))

    layout = dict(
        template="plotly_dark", height=fig_h,
        margin=dict(l=B4_MARGIN_L, r=B4_MARGIN_R, t=B4_MARGIN_T, b=B4_MARGIN_B, autoexpand=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=B4_PANEL,
        font=dict(family=B4_FONT, size=12, color=B4_INK_1),
        hovermode="closest", hoverdistance=-1, spikedistance=-1, dragmode=False, showlegend=False,
        hoverlabel=dict(bgcolor=B4_UI["overlay_solid"], bordercolor=B4_UI["overlay_border"],
                        font=dict(size=12, color=B4_INK_1, family=B4_FONT), align="left"),
        shapes=shapes, annotations=annotations)
    layout.update(layout_axes)
    return go.Figure(data=traces, layout=layout)


# ------------------------------------------------------------------------------
# FATTORI DELL'ORA DI PICCO (usati da radar e barre)
# ------------------------------------------------------------------------------
# (nome mostrato, chiave nella riga oraria). Tutti i punteggi sono 0-1 "più alto = più favorevole".
_B4_FACTORS = (
    ("Metabolismo", "s_temp"),
    ("Barometro", "s_press"),
    ("Luce", "s_sol"),
    ("Vento", "s_vento"),
    ("Torbidità", "s_torb"),
    ("Ossigeno", "do_saturation_index"),
)


def _b4_resolve_hour(obj, mode):
    """
    Riga oraria da mostrare in radar/barre -> (riga, nota).
    * Se `obj` è già una riga oraria: la usa così com'è (nota vuota).
    * Se `obj` è l'intero `sim`: sceglie lo stesso picco del grafico orario. In modalità Trophy,
      se la curva Trophy è piatta (nessuna ora si distingue) usa l'ora migliore per l'Attività e
      lo dice nel titolo, invece di mostrare un'ora "migliore" che non lo è.
    """
    if isinstance(obj, dict) and isinstance(obj.get("timeline"), (list, tuple)):
        day0, pairs = _b4_chrono(obj["timeline"])
        hours = [p[0] for p in pairs]
        recs = [p[1] for p in pairs]

        def pick(rate_key, best_key):
            best = obj.get(best_key)
            vals = [_b4_f(r.get(rate_key), 0.0) for r in recs]
            idx = _b4_find_peak(hours, vals, _b4_cont_hour(best, day0) if isinstance(best, dict) else None, [])
            return recs[idx] if idx is not None else None

        if mode == "Trophy":
            rec = pick("trophy_rate", "best_trophy_hour")
            if rec is not None:
                return rec, ""
            rec = pick("catch_rate", "best_hour")
            if rec is not None:
                return rec, "Trophy piatto: ora migliore dell'Attività"
        else:
            rec = pick("catch_rate", "best_hour")
            if rec is not None:
                return rec, ""
        fallback = obj.get("best_hour")
        if not isinstance(fallback, dict):
            fallback = obj.get("best_trophy_hour")
        if isinstance(fallback, dict):
            return fallback, "andamento piatto: ora indicativa"
        return (recs[0] if recs else {}), ""
    return (obj if isinstance(obj, dict) else {}), ""


def _b4_factor_list(rec):
    """[(nome, punteggio 0-100 oppure None se la chiave manca)]."""
    out = []
    for name, key in _B4_FACTORS:
        v = _b4_f(rec.get(key), None) if isinstance(rec, dict) else None
        out.append((name, None if v is None else max(0.0, min(100.0, v * 100.0))))
    return out


def _b4_hour_label(rec):
    if not isinstance(rec, dict):
        return ""
    label = rec.get("time_label")
    if label:
        return str(label)
    h = _b4_hour_of(rec)
    return _b4_hhmm(h) if h is not None else ""


def _b4_extremes_text(facts):
    """Riga di sintesi sotto il titolo: quale fattore frena di più l'ora mostrata."""
    valid = [(n, v) for n, v in facts if v is not None]
    if len(valid) < 2:
        return ""
    lo_v = min(v for _, v in valid)
    hi_v = max(v for _, v in valid)
    if hi_v - lo_v < 5.0:
        return "fattori tutti allineati"
    lows = [n for n, v in valid if v <= lo_v + 0.5]
    if len(lows) == 1:
        return "più debole: %s" % lows[0]
    if len(lows) == 2:
        return "più deboli: %s e %s" % (lows[0], lows[1])
    return "più deboli: %s e altri %d" % (lows[0], len(lows) - 1)


def _b4_factor_header(rec, facts, title, note=""):
    hl = _b4_hour_label(rec)
    l1 = "<b>%s</b>" % title + ((" alle <b>%s</b>" % hl) if hl else "")
    l2 = note or _b4_extremes_text(facts)
    return l1 + ("<br>" + _b4_muted(_b4_esc(l2)) if l2 else "")


# ------------------------------------------------------------------------------
# GRAFICO 2 — ESAGONO DEI FATTORI (radar)
# ------------------------------------------------------------------------------
def create_mobile_radar(best_hour: dict, target_mode: str = "Entrambi") -> go.Figure:
    """
    Esagono a 6 assi con il punteggio (0-100) di ogni fattore nell'ora di picco.

    best_hour:   riga oraria del Blocco 2 oppure l'intero `sim` (in modalità "Trophy" usa
                 automaticamente best_trophy_hour: non serve più scegliere l'ora a mano).
    target_mode: "Trophy" -> viola; "Numeri"/"Entrambi" -> verde. Il colore indica la modalità,
                 NON un giudizio: la v1 usava un semaforo a soglie (70/45) che col BAI reale
                 risultava quasi sempre rosso anche nelle ore migliori.
    I valori sono scritti sotto il nome di ogni asse (non servono dita sul grafico) e il titolo
    indica il fattore più debole, cioè ciò che frena quell'ora. "n/d" = chiave assente nei dati.
    Per una lettura ancora più rapida su telefono vedi create_mobile_factors_chart().
    """
    mode = _b4_norm_mode(target_mode)
    rec, note = _b4_resolve_hour(best_hour, mode)
    facts = _b4_factor_list(rec)
    if all(v is None for _, v in facts):
        return _b4_empty_figure("Fattori non disponibili per questa ora", height=120)

    color = B4_COL_TROPHY if mode == "Trophy" else B4_COL_BAI
    n = len(facts)
    theta = [i * 360.0 / n for i in range(n)]
    r_vals = [0.0 if v is None else v for _, v in facts]
    custom = [[nm, "n/d" if v is None else "%.0f su 100" % v] for nm, v in facts]
    ticktext = ["%s<br><b>%s</b>" % (nm, "n/d" if v is None else "%d" % int(round(v))) for nm, v in facts]

    top, bottom, side, height = 72, 36, 64, 306
    fig = go.Figure(
        data=[go.Scatterpolar(
            r=r_vals + [r_vals[0]], theta=theta + [360.0], thetaunit="degrees",
            mode="lines+markers", fill="toself", fillcolor=_b4_rgba(color, 0.22),
            line=dict(color=color, width=2.6),
            marker=dict(size=9, color=color, line=dict(width=2, color=B4_SURFACE)),
            customdata=custom + [custom[0]],
            hovertemplate="<b>%{customdata[0]}</b>: %{customdata[1]}<extra></extra>",
            showlegend=False)],
        layout=dict(
            template="plotly_dark", height=height,
            margin=dict(l=side, r=side, t=top, b=bottom, autoexpand=False),
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family=B4_FONT, size=12, color=B4_INK_1),
            dragmode=False, showlegend=False,
            hoverlabel=dict(bgcolor=B4_UI["overlay_solid"], bordercolor=B4_UI["overlay_border"],
                            font=dict(size=12, color=B4_INK_1, family=B4_FONT), align="left"),
            polar=dict(
                bgcolor=B4_PANEL,
                radialaxis=dict(range=[0, 112], tickvals=[25, 50, 75, 100], showticklabels=False,
                                ticks="", showline=False, gridcolor="rgba(255, 255, 255, 0.12)"),
                angularaxis=dict(type="linear", thetaunit="degrees", rotation=90, direction="clockwise",
                                 tickmode="array", tickvals=theta, ticktext=ticktext, ticks="",
                                 tickfont=dict(size=12, color=B4_INK_1),
                                 gridcolor="rgba(255, 255, 255, 0.12)", showline=False)),
            annotations=[dict(
                text=_b4_factor_header(rec, facts, "Fattori", note),
                xref="paper", yref="paper", x=0, y=1, xanchor="left", yanchor="top",
                xshift=-(side - 6), yshift=top - 4, align="left", showarrow=False,
                font=dict(size=13, color=B4_INK_1))]))
    return fig


# ------------------------------------------------------------------------------
# GRAFICO 3 — BARRE DEI FATTORI (alternativa più immediata al radar)
# ------------------------------------------------------------------------------
def create_mobile_factors_chart(best_hour: dict, target_mode: str = "Entrambi") -> go.Figure:
    """
    Stessi 6 fattori del radar ma in barre orizzontali, con i valori in una colonna a destra.
    Confrontare lunghezze è molto più rapido che confrontare vertici di un poligono: la barra
    più corta è subito "ciò che frena" quell'ora. Colore unico per modalità (verde / viola):
    la lunghezza porta già il valore, non serve ricolorare le barre.

    best_hour / target_mode: come in create_mobile_radar (accetta anche l'intero `sim`).
    """
    mode = _b4_norm_mode(target_mode)
    rec, note = _b4_resolve_hour(best_hour, mode)
    facts = _b4_factor_list(rec)
    if all(v is None for _, v in facts):
        return _b4_empty_figure("Fattori non disponibili per questa ora", height=120)

    color = B4_COL_TROPHY if mode == "Trophy" else B4_COL_BAI
    n = len(facts)
    names = [nm for nm, _ in facts]
    vals = [0.0 if v is None else v for _, v in facts]
    texts = ["n/d" if v is None else "%d" % int(round(v)) for _, v in facts]
    custom = ["n/d" if v is None else "%.0f su 100" % v for _, v in facts]

    left, right, top, bottom, slot = 104, 10, 48, 8, 32
    height = top + n * slot + bottom

    track = go.Bar(x=[100] * n, y=names, orientation="h",
                   marker=dict(color=B4_UI["track"]),
                   hoverinfo="skip", showlegend=False)
    bar_kw = dict(x=vals, y=names, orientation="h",
                  customdata=custom, hovertemplate="<b>%{y}</b> · %{customdata}<extra></extra>",
                  showlegend=False)
    try:    # angoli arrotondati (anche il fondo: con valori vicini a 100 non resta un gradino in punta)
        bars = go.Bar(marker=dict(color=color, cornerradius=4), **bar_kw)
        track.marker.cornerradius = 4
    except ValueError:
        bars = go.Bar(marker=dict(color=color), **bar_kw)
    # numeri in una colonna a destra, allineati: si confrontano senza inseguire la punta delle barre
    numbers = go.Scatter(x=[B4_BARS_XMAX] * n, y=names, mode="text", text=texts,
                         textposition="middle left", textfont=dict(size=14, color=B4_INK_1),
                         cliponaxis=False, hoverinfo="skip", showlegend=False)

    return go.Figure(
        data=[track, bars, numbers],
        layout=dict(
            template="plotly_dark", height=height,
            margin=dict(l=left, r=right, t=top, b=bottom, autoexpand=False),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family=B4_FONT, size=12, color=B4_INK_1),
            barmode="overlay", bargap=0.42, dragmode=False, showlegend=False, hovermode="closest",
            hoverlabel=dict(bgcolor=B4_UI["overlay_solid"], bordercolor=B4_UI["overlay_border"],
                            font=dict(size=12, color=B4_INK_1, family=B4_FONT), align="left"),
            xaxis=dict(range=[0, B4_BARS_XMAX], visible=False, fixedrange=True, automargin=False),
            yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=names, automargin=False,
                       tickfont=dict(size=14, color=B4_INK_1), ticks="outside", ticklen=8,
                       tickcolor="rgba(0, 0, 0, 0)", showgrid=False,
                       zeroline=False, showline=False, fixedrange=True),
            annotations=[dict(
                text=_b4_factor_header(rec, facts, "Fattori", note),
                xref="paper", yref="paper", x=0, y=1, xanchor="left", yanchor="top",
                xshift=-(left - 2), yshift=top - 2, align="left", showarrow=False,
                font=dict(size=14, color=B4_INK_1))]))


# ------------------------------------------------------------------------------
# CONTROLLO DEL CONTRATTO DATI (utile per i test di integrazione tra i blocchi)
# ------------------------------------------------------------------------------
B4_ROW_KEYS_REQUIRED = ("hour", "catch_rate", "trophy_rate")
B4_ROW_KEYS_OPTIONAL = (
    "time_label", "date_str", "water_temp_used", "water_temp", "wind", "pressure_delta",
    "depth_zone", "do_saturation_index", "s_temp", "s_press", "s_sol", "s_vento", "s_torb",
)


def check_block4_contract(sim):
    """
    Verifica che `sim` (o la sola lista timeline) contenga ciò che il Blocco 4 legge.
    Ritorna una lista di avvisi in italiano; lista vuota = tutto in ordine.
    Non solleva mai eccezioni: pensata per i test di integrazione tra Blocco 2 e Blocco 4.
    """
    rows = sim.get("timeline") if isinstance(sim, dict) else sim
    if not isinstance(rows, (list, tuple)) or not rows:
        return ["timeline assente o vuota: il grafico mostrerà solo un messaggio"]
    problems = []
    dict_rows = [r for r in rows if isinstance(r, dict)]
    if len(dict_rows) != len(rows):
        problems.append("%d righe del timeline non sono dizionari (ignorate)" % (len(rows) - len(dict_rows)))
    for key in B4_ROW_KEYS_REQUIRED:
        missing = sum(1 for r in dict_rows if r.get(key) is None)
        if missing:
            problems.append("chiave '%s' mancante in %d/%d righe (obbligatoria)" % (key, missing, len(dict_rows)))
    for key in B4_ROW_KEYS_OPTIONAL:
        if dict_rows and all(r.get(key) is None for r in dict_rows):
            problems.append("(opzionale) '%s' assente: il grafico ne omette la parte relativa" % key)
    if isinstance(sim, dict):
        for key in ("best_hour", "best_trophy_hour"):
            if not isinstance(sim.get(key), dict):
                problems.append("(opzionale) '%s' assente: il picco verrà ricalcolato dal timeline" % key)
    return problems


# >>> BLOCCO: Blocco5-BF-V5.py <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ==============================================================================
# MACRO-BLOCCO 5 (v5): INTERFACCIA STREAMLIT NATIVA, MOBILE-FIRST + CONTROLLER main()
# ==============================================================================
# Tre sezioni, scelte con la pillola galleggiante in basso: "Pesca", "Meteo" e "Diario". Pesca: intestazione (luogo,
# data, sole, luna, impostazioni in uso) -> Giorno sempre visibile -> Blocco 1 -> astronomia -> Blocco 2 -> Blocco 3 ->
# tre tab: "Grafici", "Strategia", "Ore". Meteo: adesso, avvisi, giorno per giorno, pressione. Diario: le uscite di chi
# pesca con condizioni e previsione salvate, e il confronto tra previsione e catture. Località e
# condizioni dello spot si cambiano in due cassetti che entrano da destra: il primo si apre toccando il nome del luogo
# (ricerca, posizione attuale, mappa), il secondo con il pulsante :material/tune: in alto a destra.
#
# IMPAGINAZIONE A CASSETTI (01/11/2026; scelta tra due prove, l'altra era una fila di chip con riquadri)
#   * Via dalla pagina i due expander "Cambia località" e "Spot, acqua e sonda" e la riga riassuntiva sotto di loro.
#   * Il nome del luogo nell'intestazione è il pulsante del cassetto "Località" (freccina accanto, come l'indirizzo
#     nelle app di consegne); in alto a destra un solo pulsante, :material/tune:, per il cassetto "Condizioni dello
#     spot". Cassetti = st.dialog con position="right": pannello a tutta altezza che entra da destra. Le impostazioni
#     in uso restano scritte nell'intestazione.
#   * Ogni scelta nel cassetto vale subito; la previsione si ricalcola una volta sola, quando il cassetto si chiude
#     (X, tocco fuori o "Mostra la previsione"), non a ogni tocco come con gli expander.
#   * Località: con un solo risultato, o toccando un risultato dell'elenco, il cassetto si chiude da solo.
#   * Le scelte stanno in chiavi normali di st.session_state (b5_spot, b5_water, ...); i widget del cassetto usano
#     chiavi "b5d_..." e le copiano (_b5_cb_open, _b5_cb_commit). Streamlit cancella lo stato dei widget non disegnati
#     e i widget del cassetto esistono solo mentre è aperto: con le chiavi dei widget le scelte andrebbero perse.
#   * Etichetta "Giorno" nascosta: Oggi / Domani / Dopodomani / Passato si spiegano da soli.
#
# ACQUA E OSSIGENO NEL GRAFICO ORARIO (01/11/2026)
#   * Via dal tab "Grafici" le caselle Acqua °C / O₂ mg/L e la riga "Alle 16:00 · acqua ... · ossigeno minimo ..."
#     sotto di esse: erano ferme sull'ora migliore mentre il grafico orario cambiava ora. Ora stanno nel riquadro
#     dell'ora del Blocco 4 (insieme ai fattori) e seguono la selezione: tocco su una colonnina, sulla striscia delle
#     ore o sulle frecce ‹ ›. La variazione in 3 giorni (dato del giorno) sta sotto l'acqua, il giudizio
#     sull'ossigeno di quell'ora sotto l'ossigeno. L'avviso "Ossigeno basso" (minimo del giorno) resta qui.
#   * Caselle e riga restano solo con il grafico Plotly di riserva (_b5_water_metrics), ferme sull'ora migliore.
#
# LOGO E NOME (01/11/2026)
#   * Nella fascia in alto, al centro, il logo orizzontale: pesce + "Bassometro" (nome provvisorio), "Bass" bianco e
#     marcato, "ometro" nel verde dell'app (B5_LOGO_FILES). Via la riga "BASS ENGINE" in cima all'intestazione: il nome
#     sta nel logo, una sola volta. Scheda del browser: "Bassometro".
#   * Via dalla fascia il menu ⋮ e i pulsanti di Streamlit Cloud (B5_CSS, punto 7).
#
# POSIZIONE ATTUALE E MAPPA NEL CASSETTO LOCALITÀ (02/11/2026)
#   * Sotto la ricerca due pulsanti: "Posizione attuale" (GPS del telefono, chiede il permesso; solo con indirizzo
#     https, quindi nell'app pubblicata o su localhost, non da http://192.168...) e "Scegli sulla mappa" (mappa
#     OpenStreetMap con segnaposto fisso al centro e "Usa questo punto"). Componente st.components.v2 (_b5_where):
#     nessun pacchetto in più; Leaflet arriva da unpkg alla prima apertura della mappa (B5_LEAFLET).
#   * Il punto scelto prende il nome da OpenStreetMap (_b5_place_names): il lago se il punto è sul lago o sulla
#     riva, altrimenti il comune; sotto, comune e regione. 2-4 s, con la rotellina; poi il cassetto si chiude.
#   * Le coordinate vanno solo a Open-Meteo e a Nominatim (OpenStreetMap) per previsione e nome; non si salvano.
#
# STRATEGIA A RIQUADRI (02/11/2026)
#   * Il tab era lungo 3.000-3.800 px, partiva dal "perché" (condizione fisiologica, hPa, citazioni) e ripeteva gli
#     stessi dati in più sezioni. Ora sette riquadri, due per riga, nell'ordine di chi pesca: Quando, Dove, Esca,
#     Recupero, Colori, Canna e filo, Perché. Ogni riquadro ha una riga presa dal testo del Blocco 3, senza frasi
#     nuove (_b5_strategy_sections); toccandolo, il testo completo si apre nel cassetto da destra (_b5_section_drawer).
#     All'apertura del tab circa 690 px.
#   * Via il riquadro BIO-ALERT: picco, strike zone e stato del pesce sono i riassunti di Quando, Dove e Perché. Con
#     "Trophy" il primo riquadro è la Strategia Big Bass e l'esca da trofeo apre le esche.
#   * Scartata la variante "Elenco" (piano di pesca in cima, sezioni in cassetti chiusi sotto, circa 830 px).
#
# BARRA IN BASSO E SEZIONE METEO (02/11/2026)
#   * Pillola galleggiante in basso, centrata, con icona e scritta per sezione (B5_SECTIONS: Pesca, Meteo e,
#     dallo stesso giorno, Diario). Componente st.components.v2 (_b5_nav): la barra sta in <body> con position:fixed, sopra la
#     pagina, sotto i cassetti. Toccando una voce la pagina torna in cima e si ridisegna con l'altra sezione.
#   * Fascia in alto (B5_TOPBAR_MODE, scelta "compatta" tra due prove): scendendo diventa una riga di 40 px con luogo
#     e giorno (toccandola si torna in cima) e la pillola perde le scritte; risalendo la pillola torna intera. L'altra
#     prova, "nascondi", toglieva la fascia scendendo e la riportava risalendo.
#   * Meteo "da pescatore" (_b5_page_meteo), dall'alto: adesso (tempo, temperatura, vento con direzione e raffiche,
#     pressione con tendenza in 3 h, pioggia nelle prossime 3 ore); avvisi compatti delle prossime 48 ore (temporali,
#     raffiche da B5_GUST_WARN_KMH); "Giorno per giorno" (_b5_meteo_week): titolo del giorno scelto, sotto la
#     striscia dei 7 giorni tutta visibile, con l'indice di pesca dei primi tre, e poi i dati del giorno: riquadri
#     (temperature, pioggia, vento, raffiche), collegamento alla sezione Pesca su quel giorno (Oggi, Domani,
#     Dopodomani) e ore in una tabella che scorre di lato, con la pressione come linea allineata alle colonne.
#     Cambiare giorno è istantaneo (tutto già
#     nel browser); oggi parte da adesso, gli altri giorni alle B5_DAY_START_H. Il grafico della pressione su 3 giorni
#     è facoltativo, in un expander chiuso con la tendenza nel titolo. Dati: Forecast API di Open-Meteo, una chiamata
#     in cache per B5_METEO_TTL_S; simboli del tempo in SVG disegnati qui.
#   * Ultimi dati validi (B5_STALE_MAX_H, B5_STALE_DIR): ogni download riuscito di Pesca e Meteo resta salvato; se
#     Open-Meteo non risponde (il 02/11/2026 è stato giù più di un'ora), la pagina usa l'ultimo per lo stesso luogo
#     con un avviso e l'ora del download. Nel Meteo "Adesso" e le ore partono dall'ora attuale, prese dalla previsione
#     oraria salvata (la temperatura percepita non c'è).
#   * Prima versione del Meteo (scartata lo stesso giorno): sezioni una sotto l'altra (prossime 24 ore, grafico della
#     pressione sempre aperto, elenco dei 7 giorni), 2.200 px; le ore c'erano solo per le prossime 24 e gli avvisi
#     erano riquadri st.warning grandi.
#   * Giorno e obiettivo scelti in Pesca restano dopo un passaggio dal Meteo (_B5_KEEP_KEYS): Streamlit cancella lo
#     stato dei widget non disegnati, non quello riassegnato a mano in testa a ogni giro.
#
# DIARIO DELLE USCITE (02/11/2026)
#   * Terza voce della pillola. Si segnano le uscite, non solo le catture: anche i cappotti, che servono a capire se la
#     previsione funziona. "Inizia adesso" salva luogo, ora e la previsione di quel momento, prima delle catture
#     (Blocchi 1-2 con le impostazioni in uso, ora per ora: Attività, Trophy, acqua, ossigeno, aria, pressione, vento,
#     nuvole); "Cattura" segna l'ora con un tocco (peso, lunghezza ed esca si aggiungono dopo); "Fine uscita" la
#     chiude. "Già fatta" aggiunge un'uscita passata: la previsione si calcola allora, con il meteo del giorno (solo
#     per gli ultimi 14 giorni, B5_OFFSET_MIN), ed è segnata come calcolata dopo.
#   * "Come va la previsione": in ogni uscita conclusa le ore in acqua si dividono in forti (Attività prevista sopra la
#     mediana di quell'uscita) e altre; si sommano ore e catture di tutte le uscite e si confrontano le catture all'ora.
#     Ogni uscita fa da confronto a sé stessa, quindi bravura, lago e stagione pesano poco. Compare dopo
#     B5_DIARY_MIN_TRIPS uscite; sotto B5_DIARY_FEW_CATCHES catture dice che è presto per conclusioni.
#   * Elenco per mese, con una striscia delle ore per uscita (colonne alte quanto l'Attività prevista, verdi in acqua,
#     un pallino per cattura); toccando un'uscita il dettaglio si apre nel cassetto da destra (condizioni nelle ore in
#     acqua, catture, modifica, elimina).
#   * Salvataggio nel browser (localStorage, chiave B5_DIARY_STORE_KEY) con un componente invisibile
#     (_b5_diary_store), non sul server: Streamlit Cloud cancella i file a ogni riavvio. Coordinate a 3 decimali.
#     Copia di sicurezza in JSON da scaricare e ricaricare (unione per uscita). Limiti: un telefono e un browser; Safari
#     su iPhone può cancellare i dati di un sito non aperto da una settimana.
#
# ACCOUNT E DATABASE DEL DIARIO (02/11/2026)
#   * Facoltativi: si accendono solo con i secrets [auth] (accesso con Google, st.login) e [firestore] (chiave del
#     service account di un progetto Firebase con Cloud Firestore) e con i pacchetti streamlit[auth] e google-auth.
#     Senza, il Diario resta com'era, solo nel browser. Guida passo passo: GUIDA-ACCOUNT.md.
#   * Con l'accesso il diario sta nel database, un documento per uscita (utenti/{uid}/uscite/{id}); ogni modifica va
#     subito al database (se non ci riesce resta in attesa, con un avviso e "Riprova adesso"); entrando nel Diario si
#     rilegge dopo B5_DIARY_RELOAD_S secondi, così le modifiche fatte da un altro telefono compaiono. Le uscite rimaste
#     nel browser si copiano nell'account con un tocco ("Copiale nel mio account"), poi il browser si svuota.
#   * Scelte: Firestore e non Supabase perché il piano gratuito di Supabase mette in pausa il database dopo 7 giorni
#     senza uso (in inverno capita); accesso e database nello stesso progetto Google. Il database si usa solo dal
#     server con la chiave segreta: le regole di Firestore restano chiuse a tutti. Si salvano uscite, nome ed email
#     (per riconoscere i tester); "Cancella il mio diario dal database" toglie tutto. Dopo Accedi / Esci l'app
#     riparte da capo: il browser segna l'ora (B5_AFTER_LOGIN_KEY) e la pillola riapre il Diario.
#
# ALBA, TRAMONTO E LUNA NELL'INTESTAZIONE (01/11/2026)
#   * Alba e tramonto in un solo riquadro, "06:46 ⌒ 17:04": tra le due ore l'arco del sole (orizzonte, percorso a
#     puntini, sole a mezzogiorno). Prima erano due riquadri con la stessa icona Material (wb_twilight) che da piccola
#     sembrava un lampeggiante. Provate anche mezzo sole con freccia su/giù (a 14 px sembrava l'icona di upload e
#     download), l'arco a tratto pieno (una campanella) e le parole "alba" e "tramonto" (chiare ma lunghe).
#   * Luna: disegnata con la parte illuminata della percentuale calcolata e dal lato giusto, invece dell'emoji, che
#     cambiava disegno e colori da un telefono all'altro. Icone SVG in _B5_ICONS e _b5_moon_icon.
#
# COSA CAMBIA RISPETTO ALLA v4 (30/10/2026)
#   * Via il selettore "Obiettivo" (Entrambi / Numeri / Trophy) in cima alla pagina: nel tab "Grafici" doppiava le
#     schede del grafico senza seguirle, e "Numeri" ed "Entrambi" davano lo stesso risultato.
#   * Nel tab "Strategia" un selettore Numeri / Trophy (B5_GOALS) sceglie per quale obiettivo il Blocco 3 v3 scrive
#     il report: con "Trophy" ora di riferimento, esche, recupero, setup e colori sono quelli per i pesci grandi.
#   * "Grafici" e "Ore" mostrano sempre Attività e Trophy (come faceva "Entrambi"); acqua, ossigeno e fattori sono
#     riferiti all'ora migliore dell'attività (dal 01/11/2026 acqua e ossigeno seguono l'ora selezionata, vedi sopra).
#   * La strike zone nel Bio-alert compare anche con "Trophy", con l'ora del picco Trophy (la v4 la nascondeva).
#   * Richiede il Blocco 3 v3 per i testi dei due obiettivi; con il Blocco 3 v2 funziona, con i testi della v2.
#   * Guida alla scelta dello spot: il "?" accanto a "Morfologia dello spot" spiega i quattro tipi e come sceglierli
#     (in base all'acqua che si pesca, non al nome del lago); sotto le pillole una riga pratica sullo spot scelto
#     (B5_SPOT_HELP, B5_SPOT_HINTS) al posto della descrizione tecnica del Blocco 1.
#   * Stile unico: colori, superfici e carattere dalla tavolozza del Blocco 4 (B4_UI) e dal tema in
#     .streamlit/config.toml. Riquadri "?" rialzati (_b5_css: grigio più chiaro, sfocatura, ombra) per non
#     confondersi con i riquadri della pagina.
#   * I fattori stanno nel grafico orario del Blocco 4 e seguono l'ora selezionata; il grafico Plotly dei fattori
#     (in un riquadro con bordo) resta solo quando il grafico orario non è disponibile.
#   * Tutti i "?" sono pulsanti st.popover (_b5_info): si aprono con un tocco e restano aperti finché non si tocca un
#     altro punto. I tooltip di Streamlit (help=) sul telefono si aprivano a fatica e si chiudevano subito. Via i "?"
#     dalle colonne della tabella oraria: la legenda sotto la tabella dice le stesse cose.
#   * Sopra "Aggiorna i dati meteo" l'ora in cui sono stati scaricati i dati in uso ("Dati meteo scaricati alle 14:32",
#     ora del luogo): un cambio dei numeri dovuto a un aggiornamento delle previsioni si capisce subito.
#   * Logo (bozza D) con st.logo nella fascia vuota sopra il primo riquadro (dal 01/11/2026 al centro, con la
#     scritta: vedi LOGO E NOME) e come icona della scheda del browser. File cercati nella cartella Logo accanto
#     all'app oppure direttamente accanto all'app (pubblicazione senza cartelle); senza file l'app resta com'era
#     (B5_LOGO_FILES, B5_PAGE_ICON_FILE).
#   * Avviso in cima alla pagina se il tema scuro non è attivo (manca .streamlit/config.toml), oltre a quello per la
#     magic: su Streamlit Cloud, con i file caricati senza cartelle, l'app si apriva illeggibile senza spiegazioni.
#
# COSA CAMBIAVA RISPETTO ALLA v3 (v4; solo il tab "Grafici")
#   * Il grafico orario è quello a colonnine del Blocco 4 v3 (create_mobile_hourly_widget), mostrato con st.iframe:
#     schede Attività / Trophy / Confronta, corona sull'ora migliore, ore scorrevoli, valore al tocco.
#     Se il Blocco 4 è una versione vecchia, o il widget non è disponibile, torna il grafico Plotly di prima.
#   * Via le due schede Attività / Trophy sopra il grafico: il numero del picco ora sta dentro il grafico.
#     Per rimetterle: B5_SHOW_INDEX_METRICS = True. Restano Acqua e O₂ con la riga di note.
#
# COSA CAMBIAVA RISPETTO ALLA v2 (v3)
#   * Solo componenti nativi di Streamlit: niente HTML scritto a mano e poche regole CSS (B5_CSS: margine in
#     alto e testo a 16 px nei campi su iPhone). I testi del Blocco 3 vanno a st.markdown così come sono (la v2 li
#     convertiva in HTML con un parser fatto in casa).
#   * Nessun selectbox: su iPhone mostrava il cursore senza aprire la tendina. Al loro posto segmented control,
#     pills, radio e uno slider per le date passate.
#   * Controlli nella pagina principale, non nella sidebar.
#   * Ossigeno in mg/L (do_used_mg_l del Blocco 2 v2, con la sonda già riportato alla sua temperatura), non "DO %".
#   * Indici senza "%": sono indici relativi 0-100, non probabilità (come nei testi del Blocco 3 v2).
#   * Curva piatta da trophy_flat / bai_flat del Blocco 2 v2: la v2 la ricalcolava e sostituiva l'ora Trophy.
#   * Al Blocco 1 passa anche target_date; al Blocco 3 passa astro con la latitudine (sponde nell'emisfero sud).
#
# COME ASSEMBLARE: build_app.py (stessa cartella) unisce Blocchi 1, 2, 3, 4 e questo file in app.py.
#   Usa: SPOT_TYPES, fetch_thermal_and_weather_series, ProTourBiologicalEngine, TacticalAdvisorV2,
#   create_mobile_plotly_chart e, se ci sono, create_mobile_hourly_widget, B4_W_HEIGHT, create_mobile_factors_chart,
#   create_mobile_radar, MOBILE_PLOTLY_CONFIG.
#   Se manca un blocco l'app lo dice invece di andare in errore. Nomi nuovi con prefisso `_b5_` / `B5_` (salvo main).
#
# REQUISITI: Python 3.10+, streamlit >= 1.66 (segmented_control, pills, st.columns(wrap=False), st.metric con
#   border e delta_description), plotly, requests, tzdata su Windows. Nessuna chiave API. Solo per gli account del
#   Diario (facoltativi): streamlit[auth] (Authlib), google-auth e i secrets [auth] e [firestore].
#
# OBBLIGATORIO: `.streamlit/config.toml` accanto ad app.py con `[runner] magicEnabled = false`. Con la "magic"
#   attiva Streamlit stampa nella pagina ogni espressione isolata del file: le docstring dei Blocchi 1-3 e le righe
#   `requests` / `st` del Blocco 1 (cioè l'intera documentazione dei due moduli). Lo stesso file imposta il tema
#   scuro: i grafici del Blocco 4 sono disegnati per uno sfondo nero. Se la magic è attiva l'app mostra un avviso.
#
# DA SAPERE
#   * Cambi rapidi: le costanti B5_* qui sotto (località iniziale, opzioni ed etichette dei controlli, intervallo
#     di date, testi dei tab e del piè di pagina).
#   * Date: da -14 a +2 giorni rispetto a oggi nel fuso del luogo. Il Blocco 1 v2 andrebbe oltre, ma dopo 2-3
#     giorni la previsione meteo perde affidabilità.
#   * Alba, tramonto e luna li calcola questo blocco (nessun altro li fornisce): precisione ~1-2 minuti.
#   * Ossigeno e temperatura dell'acqua sono stime del modello, non misure.
#   * Icone: Material Symbols di Streamlit (":material/nome:", stile rounded) in etichette, avvisi e Markdown.
#     _b5_mdx farebbe l'escape dei ":" e le romperebbe: un'icona in testa a un testo protetto passa da _b5_mdx_icon.
#     Eccezioni: le icone dei riquadri sotto il nome (data, alba e tramonto, luna), SVG disegnati qui (_B5_ICONS), e
#     👑 nella tabella oraria (st.dataframe non disegna le icone).
import datetime as _b5_dt
import hashlib as _b5_hashlib
import html as _b5_html
import json as _b5_json
import math as _b5_math
import os as _b5_os
import re as _b5_re
import tempfile as _b5_tempfile
import time as _b5_time

import requests
import streamlit as st


# ------------------------------------------------------------------------------
# COSTANTI (modificabili senza toccare la logica)
# ------------------------------------------------------------------------------
B5_PAGE_TITLE = "Bassometro"       # nome provvisorio dell'app (scheda del browser e logo)
# Logo al centro della fascia in alto (st.logo, alto 32 px) e icona della scheda del browser: file della cartella Logo
# accanto all'app, o accanto all'app. Logo: il primo file trovato di B5_LOGO_FILES (pesce + scritta "Bassometro";
# se manca, solo il pesce ritagliato, che a 32 px resta leggibile).
B5_LOGO_FILES = ("bassometro-orizzontale.svg", "bass-D-colori-stretto.svg")
B5_PAGE_ICON_FILE = "favicon-32.png"

# Località mostrata al primo avvio (poi si cambia toccando il nome nell'intestazione). Cambiala con il tuo lago.
B5_DEFAULT_LOCATION = {
    "name": "Lago Trasimeno", "admin": "Umbria", "country": "Italia",
    "lat": 43.13, "lon": 12.10, "tz": "Europe/Rome",
}

# Valori dei controlli: stringhe identiche a quelle attese dai Blocchi 2 e 3 (l'ordine è quello mostrato).
# Le etichette sono solo per lo schermo.
# Obiettivo della strategia (tab "Strategia"): passato al Blocco 3 come target_mode.
B5_GOALS = ["Numeri", "Trophy"]
B5_GOAL_LABELS = {
    "Numeri": ":material/local_fire_department: Numeri",
    "Trophy": ":material/workspace_premium: Trophy",
}
B5_GOAL_NOTES = {
    "Numeri": "Più catture possibili: esche di ricerca e molti lanci, spostandosi finché si trova pesce attivo.",
    "Trophy": "Pesci oltre 2 kg: esche grandi, meno lanci e più tempo sui punti migliori. Di solito meno tocchi.",
}
B5_WATER_LEVELS = ["Stabile", "In Crescita", "In Calo"]
B5_WATER_LABELS = {"Stabile": "Stabile", "In Crescita": "In crescita ↑", "In Calo": "In calo ↓"}
B5_FORAGE_BASES = [
    "Misto",
    "Pesce Foraggio (Alborella / Shad)",
    "Gamberi / Crostacei / Gobbio",
    "Rane / Insetti / Shallow",
]
B5_FORAGE_LABELS = {
    "Misto": "Misto",
    "Pesce Foraggio (Alborella / Shad)": ":material/set_meal: Pesce foraggio",
    "Gamberi / Crostacei / Gobbio": "Gamberi e gobbi",
    "Rane / Insetti / Shallow": "Rane e insetti",
}
B5_PRESSURES = ["Bassa", "Media", "Alta"]
B5_TURBIDITIES = ["Non specificato", "Limpida", "Velata", "Torbida", "Fangosa"]
B5_TURBIDITY_LABELS = {"Non specificato": "Non so"}
# Etichette brevi delle morfologie di SPOT_TYPES, nello stesso ordine del Blocco 1 (la quarta dal Blocco 1 v3).
B5_SPOT_SHORT = ("Cava profonda", "Lago medio", "Acqua bassa", "Grande lago")
# Guida alla scelta dello spot, nello stesso ordine. Profondità coerenti con mean_depth_m / max_depth_m del Blocco 1
# (12/30, 6/15, 1.5/2.5 m; grandi laghi 100 m). B5_SPOT_HINTS: riga sotto le pillole; B5_SPOT_HELP: il "?".
B5_SPOT_HINTS = (
    "Cave e laghi profondi fino a circa 30 m, sponde ripide e drop-off: l'acqua cambia temperatura lentamente.",
    "Laghi e bacini fino a circa 15 m, con acqua aperta e zone basse insieme. Nel dubbio, scegli questo.",
    "Fondali fino a 2-3 m (canali, paludi, lanche, baie con canneti): l'acqua si scalda e si raffredda in fretta.",
    "Garda, Maggiore, Como e simili, pescando in acqua aperta: l'acqua cambia temperatura molto lentamente.",
)
B5_SPOT_HELP = (
    "**Scegli in base all'acqua che peschi, non al nome del lago.**\n\n"
    "**Cava profonda** · cave e laghi stretti e profondi fino a circa 30 m, sponde ripide e drop-off. L'acqua "
    "cambia temperatura lentamente.\n\n"
    "**Lago medio** · laghi e bacini fino a circa 15 m, con acqua aperta e zone basse insieme: laghi di pianura e "
    "di collina, bacini artificiali, il Trasimeno. Nel dubbio, scegli questo.\n\n"
    "**Acqua bassa** · fondali fino a 2-3 m: canali, paludi, lanche, bozzi, baie basse con canneti e ninfee, anche "
    "dentro un lago grande. L'acqua si scalda e si raffredda in fretta.\n\n"
    "**Grande lago** · Garda, Maggiore, Como, Iseo, Bolsena, Bracciano, quando peschi punte, drop-off e sponde "
    "aperte. In una baia bassa e riparata scegli Lago medio o Acqua bassa."
)

B5_DEFAULTS = {
    "b5_goal": "Numeri", "b5_when": "Oggi", "b5_water": "Stabile", "b5_forage": "Misto",
    "b5_press": "Media", "b5_turb": "Non specificato", "b5_probe_on": False, "b5_probe_c": 15.0,
}

# Scelte che si cambiano nel cassetto "Condizioni dello spot" (chiavi di st.session_state lette dal resto dell'app).
B5_DRAWER_KEYS = ("b5_spot", "b5_water", "b5_forage", "b5_press", "b5_turb", "b5_probe_on", "b5_probe_c")
B5_DRAWER_POSITION = "right"     # st.dialog: "right" cassetto da destra, "left" da sinistra, "center" finestra al centro

B5_WHEN_OPTIONS = ["Oggi", "Domani", "Dopodomani", "Passato"]
B5_WHEN_OFFSETS = {"Oggi": 0, "Domani": 1, "Dopodomani": 2}
B5_OFFSET_MIN = -14      # giorni nel passato
B5_OFFSET_MAX = 2        # giorni nel futuro

B5_PROBE_MIN = 0.0
B5_PROBE_MAX = 38.0

B5_DO_LIMITED_MG_L = 5.0     # sotto: attività limitata (criteri EPA 1986, come Blocchi 1 e 2)
B5_DO_STRESS_MG_L = 4.0      # sotto: stress

B5_TAB_LABELS = (":material/monitoring: Grafici", ":material/target: Strategia", ":material/schedule: Ore")
# Sezioni nella pillola in basso: (chiave, scritta). Le icone sono in _B5_NAV_ICONS, con la stessa chiave.
B5_SECTIONS = (("pesca", "Pesca"), ("meteo", "Meteo"), ("diario", "Diario"))
# Fascia in alto scorrendo la pagina: "compatta" (diventa una riga sottile con luogo e giorno e la pillola perde le
# scritte; scelta il 02/11/2026) oppure "nascondi" (sparisce scendendo, torna risalendo; l'altra prova).
B5_TOPBAR_MODE = "compatta"
# Chiavi dei widget della sezione Pesca da conservare quando si passa al Meteo (vedi note in testa).
_B5_KEEP_KEYS = ("b5_when", "b5_goal")
# Meteo: giorni di previsione, durata della cache (s) e raffiche da cui scatta l'avviso. 40 km/h: inizio del grado 6
# della scala Beaufort ("vento forte", 39-49 km/h), già impegnativo per barchini, belly boat e kayak.
B5_METEO_DAYS = 7
B5_METEO_TTL_S = 900
B5_GUST_WARN_KMH = 40
# Ora mostrata per prima nella tabella dei giorni dopo oggi (prima dell'alba; si può scorrere indietro fino alle 00).
B5_DAY_START_H = 5
# Diario: chiave del browser (localStorage) in cui sta il diario; uscite concluse con la previsione prima di mostrare il
# confronto tra ore forti e altre ore; catture sotto cui il confronto dice che è presto; giorni nel passato per
# un'uscita già fatta (la previsione si calcola solo fino a B5_OFFSET_MIN giorni fa).
B5_DIARY_STORE_KEY = "bassometro.diario.v1"
B5_DIARY_MIN_TRIPS = 5
B5_DIARY_FEW_CATCHES = 20
B5_DIARY_MAX_DAYS = 365
# Account del Diario (facoltativi, vedi SEZIONE DIARIO): API REST di Cloud Firestore; secondi dopo cui il diario
# dell'account si rilegge dal database entrando nel Diario; chiave del browser con l'ora di Accedi / Esci (per riaprire
# il Diario al ritorno da Google).
B5_FIRESTORE_URL = "https://firestore.googleapis.com/v1/"
B5_DIARY_RELOAD_S = 120
B5_AFTER_LOGIN_KEY = "bassometro.dopo-accesso"

# Schede Attività / Trophy sopra il grafico orario. False: il grafico a colonnine del Blocco 4 v3 mostra già il
# picco e le ore migliori. Con un Blocco 4 vecchio (grafico Plotly) le schede tornano comunque.
B5_SHOW_INDEX_METRICS = False
B5_WIDGET_ALT = "Grafico orario di attività e trophy"     # nome accessibile dell'iframe

B5_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
B5_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Nomi dei punti scelti con il GPS o sulla mappa: Nominatim di OpenStreetMap, gratuito e senza chiave. Le sue regole
# d'uso chiedono un'app riconoscibile nelle richieste e al massimo una richiesta al secondo.
B5_NOMINATIM_URL = "https://nominatim.openstreetmap.org/"
B5_HTTP_HEADERS = {"User-Agent": "Bassometro/0.1 (+https://github.com/Guttalax05/Basscast-alpha)"}
# Mappa del cassetto Località: Leaflet 1.9.4 da unpkg (con l'impronta SHA-256 dei file pubblicata da Leaflet: un
# file alterato non viene eseguito) e le mappe di OpenStreetMap, gratuite con l'attribuzione e per un uso leggero.
# Le mappe CARTO ora vogliono una chiave: senza, ogni riquadro mostra "API KEY REQUIRED" (prova del 02/11/2026).
B5_LEAFLET = {
    "base": "https://unpkg.com/leaflet@1.9.4/dist/",
    "css": "sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=",
    "js": "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
}
B5_MAP_TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
B5_MAP_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
# Testi dei "?" (pulsanti _b5_info). Il "?" dello spot è B5_SPOT_HELP.
B5_INFO_TURBIDITY = "Se non la conosci scegli «Non so»: il modello assume acqua velata."
B5_INFO_PROBE = (
    "Se hai misurato la temperatura dell'acqua (termometro o ecoscandaglio), l'app usa la tua misura al posto della "
    "stima del modello; l'andamento nell'arco del giorno resta quello calcolato."
)
B5_INFO_WATER = (
    "**Acqua °C** · temperatura dell'acqua stimata dal modello all'ora indicata qui sotto, non misurata. Con la "
    "sonda è la tua misura.\n\n"
    "**O₂ mg/L** · ossigeno disciolto stimato dal modello, non misurato. Da 5 mg/L in su nessun limite; sotto 5 "
    "attività limitata, sotto 4 stress (criteri EPA 1986)."
)

# Durata della cache dei dati meteo, s: la stessa di fetch_thermal_and_weather_series (Blocco 1, ttl=1800). Le due
# cache scadono insieme, quindi l'ora mostrata sopra "Aggiorna i dati meteo" è quella del download dei dati in uso.
B5_WEATHER_TTL_S = 1800
# Ultimi dati validi: ogni download riuscito (Pesca e Meteo) resta in un file JSON nella cartella temporanea del
# sistema; se Open-Meteo non risponde la pagina usa l'ultimo per lo stesso luogo (e giorno), con un avviso e l'ora del
# download, fino a B5_STALE_MAX_H ore. Su Streamlit Cloud i file restano finché il server non riparte. Il 02/11/2026
# Open-Meteo ha risposto 503 "The service is overloaded" a ogni chiamata per più di un'ora.
B5_STALE_MAX_H = 12
B5_STALE_DIR = _b5_os.path.join(_b5_tempfile.gettempdir(), "bassometro-dati")
B5_FOOTER_TEXT = (
    "Indici relativi del modello (0-100), non probabilità · Temperatura e ossigeno dell'acqua sono stime · "
    "Dati meteo: Open-Meteo · Rispetta le norme di pesca locali"
)

# Le uniche regole CSS dell'app (tutto il resto è stile nativo di Streamlit + tema in config.toml):
#   1. su schermi stretti il contenuto parte subito sotto la testata di Streamlit (vuota), non 96 px più in basso;
#   2. sui touchscreen i campi di testo a 16 px: sotto, Safari su iPhone ingrandisce la pagina quando li tocchi;
#   3. pulsanti "?" (_b5_info, chiavi b5_info_*): area di tocco 44x44 px (era 27x40) con margini negativi, così la
#      riga dell'etichetta non si allunga; senza la freccina che st.popover aggiunge accanto all'icona;
#   4. pulsante Condizioni nell'intestazione (chiave b5_actions): tondo, 44x44 px;
#   5. nome del luogo (pulsante b5_open_loc): stesso carattere del titolo che sostituisce (st.subheader: 28 px, 600,
#      margini 12/16 px), allineato a sinistra e a capo se lungo; freccina grigia che diventa verde al tocco;
#   6. logo (st.logo) al centro della fascia in alto invece che a sinistra;
#   7. nella fascia in alto niente menu ⋮, pulsante Deploy e pulsanti aggiunti da Streamlit Cloud (condividi,
#      GitHub...): servono a chi sviluppa, non a chi pesca, e al telefono si sovrapporrebbero al logo centrato. Il menu
#      permetteva anche di passare al tema chiaro, per cui l'app non è disegnata. Resta l'indicatore di caricamento;
#   8. riquadri sotto il nome (data, alba e tramonto, luna; _b5_chip): stesso aspetto dei badge grigi di Streamlit
#      (colori, 14 px, angoli da 4 px), in HTML perché le icone sono SVG disegnati qui. Margine sotto di 1rem:
#      Streamlit toglie 1rem sotto ogni testo Markdown (il margine dei paragrafi, che qui non ci sono).
B5_CSS = (
    '@media (max-width:640px){[data-testid="stMainBlockContainer"]{padding-top:3.75rem}}'
    "@media (pointer:coarse){input,textarea{font-size:16px !important}}"
    '[class*="st-key-b5_info"] [data-testid="stPopoverButton"]{min-width:44px;min-height:44px;'
    "margin:-10px 0 -10px -6px;justify-content:center}"
    '[class*="st-key-b5_info"] [data-testid="stPopoverButton"] div[aria-hidden="true"]{display:none}'
    ".st-key-b5_actions button{width:44px;min-height:44px;padding:0;border-radius:22px}"
    ".st-key-b5_open_loc button{min-height:44px;padding:12px 0 8px;justify-content:flex-start;text-align:left}"
    ".st-key-b5_open_loc button p{font-size:28px;font-weight:600;line-height:1.2;white-space:normal}"
    # la freccina nel testo è uno span role="img" del Markdown di Streamlit (non stIconMaterial)
    '.st-key-b5_open_loc button p span[role="img"]{color:rgba(242,242,247,.55)}'
    '.st-key-b5_open_loc button:hover p span[role="img"],.st-key-b5_open_loc button:active p span[role="img"]'
    "{color:inherit}"
    '[data-testid="stHeaderLogo"]{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)}'
    '[data-testid="stMainMenu"],[data-testid="stAppDeployButton"],[data-testid="stToolbarActions"]{display:none}'
    # riquadri del tab Strategia toccabili per intero (pulsante invisibile sopra), freccina a destra
    '[class*="st-key-b5_tile_"]{position:relative;transition:border-color .15s}'
    '[class*="st-key-b5_tile_"]:has(button:focus-visible){border-color:#0fa874}'
    '@media (hover:hover){[class*="st-key-b5_tile_"]:has(button:hover){border-color:#0fa874}}'
    '[class*="st-key-b5_tile_"]::after{content:"\\203A";position:absolute;right:14px;top:10px;font-size:22px;'
    "line-height:1;color:rgba(242,242,247,.45)}"
    '[class*="st-key-b5_tbtn_"]{position:absolute;inset:0;width:100% !important;z-index:2;margin:0}'
    '[class*="st-key-b5_tbtn_"] div,[class*="st-key-b5_tbtn_"] button{width:100% !important;'
    "height:100% !important}"
    '[class*="st-key-b5_tbtn_"] button{opacity:0;cursor:pointer}'
    '[class*="st-key-b5_tile_"] [data-testid="stMarkdownContainer"] p{display:-webkit-box;-webkit-line-clamp:3;'
    "-webkit-box-orient:vertical;overflow:hidden}"
    ".b5-chips{display:flex;flex-wrap:wrap;gap:3px 5px;margin-bottom:1rem}"
    ".b5-chip{position:relative;display:inline-flex;align-items:center;gap:4px;padding:0 5px;border-radius:4px;"
    "background:rgba(128,132,149,.2);color:rgba(250,250,250,.6);font-size:14px;line-height:22.4px;white-space:nowrap}"
    ".b5-chip svg{flex:none}"
    ".b5-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}"
    # sezione Meteo: riquadro "Adesso" con lo stesso bordo dei riquadri di Streamlit, tabella delle ore che scorre di lato
    ".b5m-card{border:1px solid rgba(242,242,247,.2);border-radius:8px;padding:12px 14px 14px;margin-bottom:1rem}"
    ".b5m-cap{color:rgba(242,242,247,.6);font-size:14px}"
    ".b5m-now{display:flex;align-items:center;gap:10px;margin:2px 0 12px}"
    ".b5m-now svg{flex:none}"
    ".b5m-now-t{font-size:48px;font-weight:600;line-height:1;letter-spacing:-.02em}"
    ".b5m-now-d{display:flex;flex-direction:column;min-width:0;line-height:1.3}"
    ".b5m-now-d b{font-weight:600}"
    ".b5m-now-d span{color:rgba(242,242,247,.6);font-size:14px}"
    ".b5m-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding-top:12px;"
    "border-top:1px solid rgba(242,242,247,.1)}"
    ".b5m-stats>div{display:flex;flex-direction:column;gap:2px;min-width:0}"
    ".b5m-lab{color:rgba(242,242,247,.6);font-size:12px;text-transform:uppercase;letter-spacing:.04em}"
    ".b5m-val{display:flex;align-items:center;gap:4px;font-size:20px;font-weight:600;line-height:1.2;"
    "font-variant-numeric:tabular-nums}"
    ".b5m-val svg{flex:none;color:rgba(242,242,247,.6)}"
    ".b5m-val small{font-size:13px;font-weight:400;color:rgba(242,242,247,.6)}"
    ".b5m-sub{color:rgba(242,242,247,.6);font-size:12.5px;line-height:1.3}"
    # avvisi del Meteo: bordo e fondo ambra (l'occhio del logo), icona, frase in grassetto e consiglio
    ".b5m-alerts{display:flex;flex-direction:column;gap:8px;margin-bottom:1rem}"
    ".b5m-alert{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border:1px solid rgba(227,176,75,.35);"
    "border-radius:8px;background:rgba(227,176,75,.1);font-size:14.5px;line-height:1.4}"
    ".b5m-alert svg{flex:none;margin-top:1px;color:#E3B04B}"
    ".b5m-alert p{margin:0}"
    ".b5m-alert b{font-weight:600}"
    # sezione Diario: titolo come il nome del luogo; uscite toccabili per intero (pulsante invisibile sopra, come i
    # riquadri della Strategia) con la striscia delle ore a destra; uscita in corso con il bordo verde
    ".b5d{margin-bottom:1rem}"
    ".b5d-title{padding:12px 0 6px;font-size:28px;font-weight:600;line-height:1.2}"
    ".b5d-head{display:flex;justify-content:space-between;gap:8px;margin-bottom:8px}"
    ".st-key-b5_dundo button{min-height:32px}"
    ".st-key-b5_dundo button p{color:rgba(242,242,247,.6);font-size:14px}"
    ".st-key-b5_dloc button{min-height:40px;justify-content:flex-start}"
    ".st-key-b5_dlive{border-color:rgba(15,168,116,.6) !important}"
    ".b5d-live{color:#0fa874;font-size:13px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}"
    ".b5d-place{color:rgba(242,242,247,.6);font-size:14px}"
    ".b5d-big{margin:8px 0 4px;font-size:44px;font-weight:600;line-height:1;letter-spacing:-.02em;"
    "font-variant-numeric:tabular-nums}"
    ".b5d-big small{margin-left:6px;font-size:18px;letter-spacing:0}"
    ".b5d-zero{color:rgba(242,242,247,.6)}"
    ".b5d-times{display:flex;flex-wrap:wrap;gap:3px 5px;margin:8px 0 4px}"
    ".b5d-sub{color:rgba(242,242,247,.6);font-size:14px;line-height:1.4}"
    ".b5d-sub b{color:#F2F2F7;font-weight:600}"
    ".st-key-b5_dcatch button{min-height:56px}"
    ".st-key-b5_dcatch button p{font-size:18px;font-weight:600}"
    ".b5d-intro ol{margin:6px 0 8px;padding-left:1.25em}"
    ".b5d-intro li{margin:4px 0;line-height:1.4}"
    ".b5d-intro p{margin:0;color:rgba(242,242,247,.6);font-size:14px}"
    ".b5d-cmp{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:8px 0 10px}"
    ".b5d-cmp>div{display:flex;flex-direction:column;gap:3px;min-width:0}"
    ".b5d-bar{display:block;height:6px;margin:2px 0;border-radius:3px;background:rgba(242,242,247,.08);overflow:hidden}"
    ".b5d-bar i{display:block;height:100%;border-radius:3px}"
    ".b5d-verdict{margin-bottom:6px;font-weight:600;line-height:1.4}"
    ".b5d-month{margin:.5rem 0 -.25rem;color:rgba(242,242,247,.6);font-size:13px;font-weight:600;letter-spacing:.06em;"
    "text-transform:uppercase}"
    '[class*="st-key-b5_dcard_"]{position:relative;transition:border-color .15s}'
    '[class*="st-key-b5_dcard_"]:has(button:focus-visible){border-color:#0fa874}'
    '@media (hover:hover){[class*="st-key-b5_dcard_"]:has(button:hover){border-color:#0fa874}}'
    '[class*="st-key-b5_dcbtn_"]{position:absolute;inset:0;width:100% !important;z-index:2;margin:0}'
    '[class*="st-key-b5_dcbtn_"] div,[class*="st-key-b5_dcbtn_"] button{width:100% !important;'
    "height:100% !important}"
    '[class*="st-key-b5_dcbtn_"] button{opacity:0;cursor:pointer}'
    ".b5d-row{display:flex;align-items:center;gap:12px}"
    ".b5d-txt{display:flex;flex:1;flex-direction:column;gap:1px;min-width:0;line-height:1.35}"
    ".b5d-when{overflow:hidden;color:rgba(242,242,247,.6);font-size:13px;letter-spacing:.04em;text-transform:uppercase;"
    "text-overflow:ellipsis;white-space:nowrap}"
    ".b5d-res{font-size:18px;font-weight:600}"
    ".b5d-res small{font-size:14px;font-weight:400;color:rgba(242,242,247,.6)}"
    ".b5d-txt .b5d-sub{overflow:hidden;font-size:13.5px;text-overflow:ellipsis;white-space:nowrap}"
    ".b5d-strip{display:block;flex:none}"
    ".b5d-go{flex:none;color:rgba(242,242,247,.45);font-size:22px;line-height:1}"
    ".b5d-chart{margin:12px 0 4px;overflow-x:auto}"
    ".b5d-legend{display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;margin-bottom:8px;"
    "color:rgba(242,242,247,.6);font-size:12.5px}"
    ".b5d-key{display:inline-block;width:10px;height:10px;border-radius:2px;background:#0fa874}"
    ".b5d-key.b5d-off{margin-left:6px;background:rgba(242,242,247,.16)}"
    ".b5d-dot{display:inline-block;width:8px;height:8px;margin-left:6px;border-radius:50%;background:#F2F2F7}"
    ".b5d-stats{margin-bottom:1rem}"
)

_B5_DOW = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")
_B5_MON = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")


# ------------------------------------------------------------------------------
# UTILITÀ DI TESTO (nessuna dipendenza da Streamlit)
# ------------------------------------------------------------------------------
def _b5_f(value, default=0.0):
    """float sicuro: None / testo / NaN / inf -> default."""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return x if _b5_math.isfinite(x) else default


# Caratteri con un significato nel Markdown di Streamlit (\` * _ [ ] < > # ~ $ LaTeX | tabelle : emoji e colori).
_B5_RE_MD_SPECIAL = _b5_re.compile(r"([\\`*_\[\]<>#~$|:])")


def _b5_mdx(text):
    """Testo semplice (da geocoding o da altri blocchi) da inserire in una riga di Markdown: escape dei simboli."""
    return _B5_RE_MD_SPECIAL.sub(r"\\\1", " ".join(str(text if text is not None else "").split()))


# Icona Material in testa a un testo (":material/nome: ..."), come nelle etichette di questo blocco e del Blocco 3.
_B5_RE_ICON = _b5_re.compile(r"^\s*(:material/[a-z0-9_]+:)\s*")


def _b5_mdx_icon(text):
    """Come _b5_mdx, ma l'icona Material in testa resta fuori dall'escape (con i ':' protetti non verrebbe disegnata)."""
    m = _B5_RE_ICON.match(str(text if text is not None else ""))
    return m.group(1) + " " + _b5_mdx(m.string[m.end():]) if m else _b5_mdx(text)


_B5_RE_CODE = _b5_re.compile(r"`([^`\n]+)`")
_B5_RE_HR = _b5_re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_B5_RE_LIST = _b5_re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")


def _b5_md_text(text):
    """Testo del Blocco 3 -> Markdown pronto per st.markdown, senza cambiarne il contenuto.

    * `strike zone` tra apici inversi -> grassetto (come codice sembrava un frammento di programma);
    * riga vuota prima di "---" (subito sotto una riga di testo diventerebbe un titolo) e prima/dopo gli elenchi;
    * a capo reale tra due righe di testo consecutive (in Markdown un solo a capo vale uno spazio);
    * $ e ~ protetti (formule LaTeX e barrato in Streamlit).
    """
    out = []
    for raw in str(text or "").replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if _B5_RE_HR.match(line):
            out += ["", "---", ""]
            continue
        line = _B5_RE_CODE.sub(r"**\1**", line).replace("$", r"\$").replace("~", r"\~")
        if line.lstrip().startswith("•"):
            line = "- " + line.lstrip()[1:].lstrip()
        prev = out[-1] if out else ""
        if line and prev and prev != "---":
            is_list, prev_list = bool(_B5_RE_LIST.match(line)), bool(_B5_RE_LIST.match(prev))
            if is_list != prev_list:
                out.append("")
            elif not is_list:
                out[-1] = prev + "  "
        out.append(line)
    return _b5_re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _b5_trim_seps(text):
    """Toglie righe '---' e spazi ai bordi del testo (non quelle in mezzo)."""
    t = str(text or "").strip()
    changed = True
    while changed and t:
        changed = False
        for edge in ("---", "***", "___"):
            if t.startswith(edge):
                t = t[len(edge):].lstrip("-*_ \n")
                changed = True
            if t.endswith(edge):
                t = t[: -len(edge)].rstrip("-*_ \n")
                changed = True
    return t.strip()


def _b5_remove_part(text, part):
    """Toglie `part` da `text` (se presente) e ripulisce i separatori ai bordi: serve perché il Blocco 3
    compone alcuni campi unendo altri (es. 'approccio' = condizione + posizionamento)."""
    t = str(text or "")
    p = str(part or "").strip()
    if p and p in t:
        t = t.replace(p, "", 1)
    return _b5_trim_seps(t)


def _b5_alert_parts(alert, state=""):
    """bio_alert -> ([righe di picco], stato biologico).

    Il Blocco 3 compone 'A | B — stato' (Entrambi) oppure 'Focus — Picco — stato' (Numeri / Trophy), con lo stato
    biologico della simulazione in coda. Se `state` è noto lo si toglie dalla coda; altrimenti si taglia all'ultimo ' — '.
    """
    text = str(alert or "").strip()
    state = str(state or "").strip()
    if state and text.endswith(state):
        head, tail = text[: -len(state)].rstrip(), state
        if head.endswith("—"):
            head = head[:-1].rstrip()
    else:
        head, sep, tail = text.rpartition(" — ")
        if not sep:
            head, tail = text, ""
    lines = [s.strip() for s in _b5_re.split(r" \| | — ", head) if s.strip()]
    return lines, tail.strip()


def _b5_hhmm(hour):
    total = int(round((_b5_f(hour, 0.0) % 24.0) * 60.0)) % 1440
    return "%02d:%02d" % divmod(total, 60)


def _b5_idx(value):
    """Indice 0-100 del Blocco 2 come numero intero, senza '%'."""
    return "%d" % int(round(_b5_f(value, 0.0)))


def _b5_fmt_date(d):
    return "%s %d %s" % (_B5_DOW[d.weekday()], d.day, _B5_MON[d.month - 1])


def _b5_rel_label(offset):
    named = {-1: "Ieri", 0: "Oggi", 1: "Domani", 2: "Dopodomani"}
    if offset in named:
        return named[offset]
    return "%d giorni fa" % -offset if offset < 0 else "tra %d giorni" % offset


def _b5_row_label(rec):
    """'06:00' dalla riga oraria del Blocco 2."""
    if not isinstance(rec, dict):
        return "--:--"
    label = rec.get("time_label")
    if label:
        return str(label)
    return "%02d:00" % int(_b5_f(rec.get("hour"), 0.0))


def _b5_do_mg_l(rec):
    """Ossigeno disciolto (mg/L) di una riga: quello usato dal Blocco 2 (sonda inclusa), altrimenti quello del Blocco 1."""
    if not isinstance(rec, dict):
        return None
    value = _b5_f(rec.get("do_used_mg_l"), None)
    return value if value is not None else _b5_f(rec.get("do_actual_mg_l"), None)


def _b5_short_exc(exc, limit=180):
    text = "%s: %s" % (type(exc).__name__, " ".join(str(exc).split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ------------------------------------------------------------------------------
# ASTRONOMIA (alba, tramonto, luna): nessun blocco la fornisce, quindi la calcola la UI
# ------------------------------------------------------------------------------
# Sole: algoritmo NOAA (equazione del tempo + declinazione), alba/tramonto con refrazione (zenit 90.833°).
# Luna: formula ridotta di Meeus, cap. 48 (frazione illuminata). Precisione attesa: ~1-2 minuti per il
# sole alle medie latitudini, ~1% per la luna: più che sufficiente per il fotoperiodo del Blocco 2.
_B5_EU_STD = {
    "Europe/Rome": 1, "Europe/Paris": 1, "Europe/Madrid": 1, "Europe/Berlin": 1, "Europe/Zurich": 1,
    "Europe/Vienna": 1, "Europe/Amsterdam": 1, "Europe/Brussels": 1, "Europe/Prague": 1,
    "Europe/Budapest": 1, "Europe/Warsaw": 1, "Europe/Stockholm": 1, "Europe/Copenhagen": 1,
    "Europe/Oslo": 1, "Europe/Belgrade": 1, "Europe/Zagreb": 1, "Europe/Ljubljana": 1,
    "Europe/Luxembourg": 1, "Europe/Malta": 1, "Europe/Monaco": 1, "Europe/San_Marino": 1,
    "Europe/Vatican": 1, "Europe/Andorra": 1, "Europe/Sarajevo": 1, "Europe/Skopje": 1,
    "Europe/Tirane": 1, "Europe/Bratislava": 1, "Europe/Vaduz": 1,
    "Europe/Athens": 2, "Europe/Helsinki": 2, "Europe/Bucharest": 2, "Europe/Sofia": 2,
    "Europe/Riga": 2, "Europe/Tallinn": 2, "Europe/Vilnius": 2, "Europe/Kyiv": 2, "Europe/Kiev": 2,
    "Europe/London": 0, "Europe/Dublin": 0, "Europe/Lisbon": 0,
}


def _b5_zone(tz_name):
    """ZoneInfo oppure None (su Windows senza il pacchetto `tzdata` il database dei fusi può mancare)."""
    if not tz_name:
        return None
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(str(tz_name))
    except Exception:
        return None


def _b5_last_sunday(year, month):
    d = _b5_dt.date(year, month, 31)
    return d - _b5_dt.timedelta(days=(d.weekday() + 1) % 7)


def _b5_fallback_offset(tz_name, lon, date):
    """Scarto UTC (ore) senza database dei fusi: ora legale UE per i fusi europei noti, altrimenti dalla longitudine."""
    std = _B5_EU_STD.get(str(tz_name or ""))
    if std is None:
        return float(round(_b5_f(lon, 12.0) / 15.0))
    dst = _b5_last_sunday(date.year, 3) <= date < _b5_last_sunday(date.year, 10)
    return float(std + (1 if dst else 0))


def _b5_utc_offset_hours(tz_name, lon, date):
    zi = _b5_zone(tz_name)
    if zi is not None:
        try:
            off = _b5_dt.datetime(date.year, date.month, date.day, 12, 0, tzinfo=zi).utcoffset()
            if off is not None:
                return off.total_seconds() / 3600.0
        except Exception:
            pass
    return _b5_fallback_offset(tz_name, lon, date)


def _b5_today(tz_name, lon):
    """Data di oggi nel fuso della località (Open-Meteo raggruppa i giorni con l'ora locale del luogo)."""
    now_utc = _b5_dt.datetime.now(_b5_dt.timezone.utc)
    zi = _b5_zone(tz_name)
    if zi is not None:
        try:
            return now_utc.astimezone(zi).date()
        except Exception:
            pass
    off = _b5_fallback_offset(tz_name, lon, now_utc.date())
    return (now_utc + _b5_dt.timedelta(hours=off)).date()


def _b5_julian_day(year, month, day, hour_ut=0.0):
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + b - 1524.5 + hour_ut / 24.0


def _b5_sun_times(jd, lat, lon, utc_off):
    """-> (alba, tramonto, stato): ore decimali locali; stato 'normale', 'sempre_su' (sole di mezzanotte) o 'sempre_giu' (notte polare)."""
    rad, deg = _b5_math.radians, _b5_math.degrees
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = rad(m)
    c = (_b5_math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + _b5_math.sin(2 * mr) * (0.019993 - 0.000101 * t) + _b5_math.sin(3 * mr) * 0.000289)
    omega = 125.04 - 1934.136 * t
    app_long = l0 + c - 0.00569 - 0.00478 * _b5_math.sin(rad(omega))
    obliq = (23.0 + (26.0 + ((21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60.0)) / 60.0
             + 0.00256 * _b5_math.cos(rad(omega)))
    decl = deg(_b5_math.asin(_b5_math.sin(rad(obliq)) * _b5_math.sin(rad(app_long))))
    vy = _b5_math.tan(rad(obliq / 2.0)) ** 2
    l0r = rad(l0)
    eq_time = 4.0 * deg(vy * _b5_math.sin(2 * l0r) - 2 * e * _b5_math.sin(mr)
                        + 4 * e * vy * _b5_math.sin(mr) * _b5_math.cos(2 * l0r)
                        - 0.5 * vy * vy * _b5_math.sin(4 * l0r) - 1.25 * e * e * _b5_math.sin(2 * mr))
    cos_ha = (_b5_math.cos(rad(90.833)) / (_b5_math.cos(rad(lat)) * _b5_math.cos(rad(decl)))
              - _b5_math.tan(rad(lat)) * _b5_math.tan(rad(decl)))
    if cos_ha > 1.0:
        return 12.0, 12.0, "sempre_giu"
    if cos_ha < -1.0:
        return 0.0, 24.0, "sempre_su"
    ha = deg(_b5_math.acos(cos_ha))
    noon_utc_min = 720.0 - 4.0 * lon - eq_time
    sunrise = ((noon_utc_min - 4.0 * ha) / 60.0 + utc_off) % 24.0
    sunset = ((noon_utc_min + 4.0 * ha) / 60.0 + utc_off) % 24.0
    return sunrise, sunset, "normale"


def _b5_moon(jd):
    """-> (illuminazione 0-100 %, elongazione 0-360°: 0 nuova, 180 piena)."""
    rad = _b5_math.radians
    t = (jd - 2451545.0) / 36525.0
    d = (297.8501921 + 445267.1114034 * t - 0.0018819 * t * t + t ** 3 / 545868.0 - t ** 4 / 113065000.0) % 360.0
    m = (357.5291092 + 35999.0502909 * t - 0.0001536 * t * t + t ** 3 / 24490000.0) % 360.0
    mp = (134.9633964 + 477198.8675055 * t + 0.0087414 * t * t + t ** 3 / 69699.0 - t ** 4 / 14712000.0) % 360.0
    inc = (180.0 - d - 6.289 * _b5_math.sin(rad(mp)) + 2.100 * _b5_math.sin(rad(m))
           - 1.274 * _b5_math.sin(rad(2 * d - mp)) - 0.658 * _b5_math.sin(rad(2 * d))
           - 0.214 * _b5_math.sin(rad(2 * mp)) - 0.110 * _b5_math.sin(rad(d)))
    illum = 50.0 * (1.0 + _b5_math.cos(rad(inc)))
    return max(0.0, min(100.0, illum)), d


_B5_MOON_PHASES = ("Luna nuova", "Crescente", "Primo quarto", "Gibbosa crescente", "Luna piena", "Gibbosa calante",
                   "Ultimo quarto", "Calante")


def _b5_compute_astro(date, lat, lon, tz_name):
    """Dizionario `astro` per i Blocchi 2-3-4: sunrise_dec, sunset_dec (ore locali decimali), moon_illum (0-100), lat."""
    off = _b5_utc_offset_hours(tz_name, lon, date)
    jd = _b5_julian_day(date.year, date.month, date.day, 12.0 - off)      # mezzogiorno locale
    sunrise, sunset, status = _b5_sun_times(jd, _b5_f(lat, 43.0), _b5_f(lon, 12.0), off)
    illum, elong = _b5_moon(jd)
    name = _B5_MOON_PHASES[int(((elong + 22.5) % 360.0) // 45.0)]
    length = max(0.0, sunset - sunrise) if sunset >= sunrise else 24.0 - sunrise + sunset
    return {
        "sunrise_dec": round(sunrise, 3),
        "sunset_dec": round(sunset, 3),
        "moon_illum": round(illum, 1),
        "moon_phase": name,
        "moon_elong": round(elong, 1),   # 0-180 crescente, 180-360 calante: lato illuminato nell'icona della luna
        "sunrise_str": _b5_hhmm(sunrise),
        "sunset_str": _b5_hhmm(sunset),
        "day_length_str": "%dh%02d" % divmod(int(round(length * 60.0)), 60),
        "utc_offset": off,
        "date_str": date.isoformat(),
        "sun_status": status,            # 'normale' | 'sempre_su' (sole di mezzanotte) | 'sempre_giu' (notte polare)
        "lat": _b5_f(lat, 43.0),         # il Blocco 3 v2 la usa per le sponde nell'emisfero sud
        "lon": _b5_f(lon, 12.0),
        "source": "calcolo astronomico (NOAA / Meeus)",
    }


def _b5_fallback_astro(date_str=""):
    """Se il calcolo astronomico fallisce (non dovrebbe): valori medi, dichiarati come stima."""
    return {"sunrise_dec": 6.5, "sunset_dec": 19.0, "moon_illum": 50.0, "moon_phase": "n/d",
            "sunrise_str": "06:30", "sunset_str": "19:00", "day_length_str": "", "utc_offset": 0.0,
            "date_str": date_str, "source": "stima (calcolo non riuscito)"}


# ------------------------------------------------------------------------------
# GEOCODING (Open-Meteo, gratuito e senza chiave)
# ------------------------------------------------------------------------------
_B5_RE_COORDS = _b5_re.compile(
    r"^\s*([+-]?\d{1,2}(?:[.,]\d+)?)\s*(?:[,;]\s*|\s+)([+-]?\d{1,3}(?:[.,]\d+)?)\s*$")


def _b5_parse_coords(text):
    """'43.1234, 12.5678' (anche copiato da Google Maps) -> (lat, lon) oppure None."""
    m = _B5_RE_COORDS.match(str(text or ""))
    if not m:
        return None
    lat = _b5_f(m.group(1).replace(",", "."), None)
    lon = _b5_f(m.group(2).replace(",", "."), None)
    if lat is None or lon is None or not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


@st.cache_data(ttl=3600, show_spinner=False)
def _b5_geocode(query: str) -> list:
    """Nome di luogo -> elenco di località (max 8). Solleva eccezione se la rete non risponde: l'errore non viene messo in cache."""
    resp = requests.get(
        B5_GEOCODE_URL,
        params={"name": query, "count": 8, "language": "it", "format": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json() or {}
    out = []
    for r in data.get("results") or []:
        lat, lon = _b5_f(r.get("latitude"), None), _b5_f(r.get("longitude"), None)
        if lat is None or lon is None:
            continue
        out.append({
            "name": str(r.get("name") or "Località").strip(),
            "admin": str(r.get("admin1") or r.get("admin2") or "").strip(),
            "country": str(r.get("country") or "").strip(),
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "tz": str(r.get("timezone") or "").strip(),
        })
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def _b5_tz_for_coords(lat: float, lon: float) -> str:
    """Fuso orario di una coppia di coordinate (dal campo `timezone` della previsione Open-Meteo)."""
    resp = requests.get(
        B5_FORECAST_URL,
        params={"latitude": lat, "longitude": lon, "hourly": "temperature_2m", "timezone": "auto", "forecast_days": 1},
        timeout=10,
    )
    resp.raise_for_status()
    return str((resp.json() or {}).get("timezone") or "")


def _b5_guess_tz(lat, lon):
    """Ultima spiaggia per coordinate senza fuso noto: Italia e dintorni -> Europe/Rome, altrove solo dalla longitudine."""
    return "Europe/Rome" if (36.0 <= lat <= 47.5 and 6.0 <= lon <= 19.0) else ""


# L'archivio del geocoding contiene località abitate, non laghi: "Lago di Garda" non dà risultati, "Garda" sì.
_B5_RE_WATER_PREFIX = _b5_re.compile(
    r"^(?:lago|laghetto|laghi|bacino|invaso|diga|cava|fiume|canale|lake)\s+"
    r"(?:(?:di|del|della|dello|dei|degli|delle)\s+|d['’]\s*)?", _b5_re.I)


def _b5_search_location(query):
    """-> (elenco località, messaggio per l'utente oppure ''). Con risultati il messaggio è solo informativo."""
    q = " ".join(str(query or "").split())
    if len(q) < 2:
        return [], "Scrivi il nome di un lago o di una città, oppure incolla le coordinate."
    coords = _b5_parse_coords(q)
    if coords:
        lat, lon = coords
        try:
            tz = _b5_tz_for_coords(round(lat, 4), round(lon, 4))
        except Exception:
            tz = ""
        return [{"name": "Coordinate", "admin": "%.4f, %.4f" % (lat, lon), "country": "",
                 "lat": round(lat, 4), "lon": round(lon, 4), "tz": tz or _b5_guess_tz(lat, lon)}], ""
    short = _B5_RE_WATER_PREFIX.sub("", q).strip()
    try:
        found = _b5_geocode(q)
        if not found and len(short) >= 2 and short.lower() != q.lower():
            found = _b5_geocode(short)
            if found:
                return found, ("I laghi non sono nell'archivio dei luoghi: ecco le località «%s». Per un punto "
                               "preciso sul lago usa «Scegli sulla mappa»." % short)
    except Exception as exc:
        return [], "Ricerca non riuscita (%s). Controlla la connessione e riprova." % type(exc).__name__
    if not found:
        return [], ("Nessun risultato per «%s». I laghi non sono nell'archivio: cerca il comune più vicino o "
                    "scegli il punto sulla mappa." % q)
    return found, ""


def _b5_loc_label(loc):
    parts = [str(loc.get("name") or "").strip(), str(loc.get("admin") or "").strip(), str(loc.get("country") or "").strip()]
    return " · ".join(p for p in parts if p) or "Località"


_B5_WATER_TYPES = {"water", "lake", "reservoir", "pond", "basin", "lagoon", "oxbow"}


def _b5_osm(path, **params):
    """Richiesta a Nominatim (B5_NOMINATIM_URL + path) in italiano -> JSON. Solleva eccezione se non risponde."""
    params.update({"format": "jsonv2", "accept-language": "it"})
    resp = requests.get(B5_NOMINATIM_URL + path, params=params, headers=B5_HTTP_HEADERS, timeout=8)
    resp.raise_for_status()
    return resp.json()


def _b5_is_water(item):
    return isinstance(item, dict) and bool(item.get("name")) and (
        item.get("type") in _B5_WATER_TYPES or item.get("category") == "water")


@st.cache_data(ttl=86400, show_spinner=False)
def _b5_place_names(lat: float, lon: float) -> dict:
    """
    Coordinate -> {"water": lago (o ""), "town": comune, "state": regione, "country": paese} da OpenStreetMap.

    Il lago lo cercano due richieste che si completano (prova su dieci laghi italiani, 02/11/2026): "che oggetto
    naturale c'è qui" trova i laghi grandi (Garda, Maggiore, Iseo) ma per gli altri risponde "Penisola italiana";
    "laghi qui intorno" trova quelli medi e piccoli (Trasimeno, Bolsena, Vico, Piediluco, Corbara, Chiusi) e si tiene
    il più piccolo il cui riquadro contiene il punto, così vale anche dalla riva. Una richiesta al secondo.
    Il comune non trovato solleva eccezione (non va in cache); il lago non trovato lascia solo il comune.
    """
    addr = (_b5_osm("reverse", lat=lat, lon=lon, zoom=10, addressdetails=1) or {}).get("address") or {}
    out = {"water": "", "state": str(addr.get("state") or ""), "country": str(addr.get("country") or ""),
           "town": str(addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality")
                       or addr.get("county") or "")}
    try:
        _b5_time.sleep(1.0)
        here = _b5_osm("reverse", lat=lat, lon=lon, layer="natural", zoom=16)
        if _b5_is_water(here):
            out["water"] = str(here["name"])
            return out
        _b5_time.sleep(1.0)
        d, m = 0.06, 0.003                         # raggio della ricerca e margine della riva, in gradi
        found = _b5_osm("search", q="lago", bounded=1, limit=20,
                        viewbox="%.4f,%.4f,%.4f,%.4f" % (lon - d, lat + d, lon + d, lat - d)) or []
        near = []
        for item in found:
            try:
                s, n, w, e = (float(v) for v in item.get("boundingbox"))
            except (TypeError, ValueError):
                continue
            if _b5_is_water(item) and s - m <= lat <= n + m and w - m <= lon <= e + m:
                near.append(((n - s) * (e - w), str(item["name"])))
        if near:
            out["water"] = min(near)[1]
    except Exception:
        pass
    return out


def _b5_point_location(lat, lon, source):
    """Punto dal GPS o dalla mappa -> località dell'app: nome del lago (o del comune), regione, paese e fuso."""
    lat, lon = round(lat, 4), round(lon, 4)
    try:
        names = _b5_place_names(round(lat, 3), round(lon, 3))
    except Exception:
        names = {}
    try:
        tz = _b5_tz_for_coords(lat, lon)
    except Exception:
        tz = ""
    town, state = names.get("town", ""), names.get("state", "")
    if names.get("water"):
        name, admin = names["water"], " · ".join(p for p in (town, state) if p)
    elif town:
        name, admin = town, state
    else:
        name = "Posizione attuale" if source == "gps" else "Punto sulla mappa"
        admin = "%.4f, %.4f" % (lat, lon)
    return {"name": name, "admin": admin, "country": names.get("country", ""), "lat": lat, "lon": lon,
            "tz": tz or _b5_guess_tz(lat, lon)}


# ------------------------------------------------------------------------------
# STATO DI SESSIONE E CALLBACK
# ------------------------------------------------------------------------------
# I valori dei controlli stanno in st.session_state con la chiave del widget. Vengono messi qui prima che i widget
# esistano (scrittura consentita), così i widget non ricevono anche un default e Streamlit non avvisa del conflitto.
_B5_REQUIRED_NAMES = (
    "SPOT_TYPES", "fetch_thermal_and_weather_series", "ProTourBiologicalEngine", "TacticalAdvisorV2",
    "create_mobile_plotly_chart",
)


def _b5_missing_blocks():
    """Nomi dei Blocchi 1-4 non trovati (file assemblato male)."""
    g = globals()
    return [name for name in _B5_REQUIRED_NAMES if name not in g]


def _b5_spot_keys():
    return list(SPOT_TYPES.keys())


def _b5_spot_hint(key):
    """Riga pratica sotto le pillole (B5_SPOT_HINTS); per uno spot nuovo del Blocco 1, la sua descrizione."""
    keys = _b5_spot_keys()
    if key in keys and keys.index(key) < len(B5_SPOT_HINTS):
        return B5_SPOT_HINTS[keys.index(key)]
    return str((SPOT_TYPES.get(key) or {}).get("desc") or "")


def _b5_spot_label(key):
    keys = _b5_spot_keys()
    if key in keys and keys.index(key) < len(B5_SPOT_SHORT):
        return B5_SPOT_SHORT[keys.index(key)]
    return str(key).split(" (")[0]


def _b5_init_state():
    ss = st.session_state
    if not isinstance(ss.get("b5_loc"), dict):
        ss["b5_loc"] = dict(B5_DEFAULT_LOCATION)
    ss.setdefault("b5_geo_results", [])
    ss.setdefault("b5_geo_msg", "")
    ss.setdefault("b5_geo_n", 0)
    choices = {"b5_goal": B5_GOALS, "b5_when": B5_WHEN_OPTIONS, "b5_water": B5_WATER_LEVELS,
               "b5_forage": B5_FORAGE_BASES, "b5_press": B5_PRESSURES, "b5_turb": B5_TURBIDITIES}
    for key, value in B5_DEFAULTS.items():
        if key not in ss or (key in choices and ss[key] not in choices[key]):
            ss[key] = value
    if ss.get("b5_spot") not in _b5_spot_keys():
        ss["b5_spot"] = _b5_default_spot()


def _b5_default_spot():
    spots = _b5_spot_keys()
    return spots[1] if len(spots) > 1 else spots[0]


def _b5_cb_search():
    """
    Invio della ricerca nel cassetto Località. Un solo risultato: diventa la località e il cassetto si chiude. Più
    risultati: restano nell'elenco finché non se ne tocca uno (la previsione dietro il cassetto non si vede).
    """
    ss = st.session_state
    found, msg = _b5_search_location(ss.get("b5_q"))
    ss["b5_geo_results"] = found if len(found) > 1 else []
    ss["b5_geo_msg"] = msg
    ss["b5_geo_found"] = bool(found)
    ss["b5_geo_n"] = int(ss.get("b5_geo_n", 0)) + 1      # nuova chiave = l'elenco riparte senza scelta
    if len(found) == 1:
        ss["b5_loc"] = found[0]
        ss["b5_drawer_close"] = True


def _b5_cb_pick(key):
    ss = st.session_state
    results, idx = ss.get("b5_geo_results") or [], ss.get(key)
    if isinstance(idx, int) and 0 <= idx < len(results):
        ss["b5_loc"] = results[idx]
        ss["b5_drawer_close"] = True


def _b5_dk(key):
    """Chiave del widget nel cassetto per una scelta salvata: b5_spot -> b5d_spot."""
    return "b5d_" + key[3:]


def _b5_cb_open(which):
    """Tocco su Località o Condizioni: il cassetto riparte dalle scelte salvate e senza risultati di ricerche vecchie."""
    ss = st.session_state
    for key in B5_DRAWER_KEYS:
        ss[_b5_dk(key)] = ss[key]
    ss["b5_geo_results"], ss["b5_geo_msg"] = [], ""
    ss["b5_drawer"] = which


def _b5_cb_commit(key):
    st.session_state[key] = st.session_state[_b5_dk(key)]


def _b5_cb_reset():
    """"Valori iniziali" nel cassetto: B5_DEFAULTS e lo spot iniziale, salvati e mostrati subito."""
    ss = st.session_state
    defaults = dict(B5_DEFAULTS, b5_spot=_b5_default_spot())
    for key in B5_DRAWER_KEYS:
        ss[key] = ss[_b5_dk(key)] = defaults[key]


def _b5_cb_refresh():
    for cached in (_b5_fetch_cached, fetch_thermal_and_weather_series):     # entrambe: l'ora resta quella dei dati
        try:
            cached.clear()
        except Exception:
            pass


# ------------------------------------------------------------------------------
# CONTROLLI (cassetti Località e Condizioni, giorno nella pagina)
# ------------------------------------------------------------------------------
def _b5_css():
    """
    B5_CSS più le regole che leggono la tavolozza del Blocco 4 (B4_UI): riquadri "?" rialzati (più chiari della pagina,
    con sfocatura e ombra, come i popup di iOS) e, se la tavolozza ha superfici piene, il fondo di riquadri con
    bordo (chiavi b5_card_*), expander e metriche. Senza B4_UI resta B5_CSS.
    """
    ui = globals().get("B4_UI") or {}
    css = B5_CSS
    if ui.get("overlay"):
        css += ('[data-testid="stPopoverBody"]{background:%s !important;border-color:%s !important;'
                "-webkit-backdrop-filter:blur(18px) saturate(1.4);backdrop-filter:blur(18px) saturate(1.4);"
                "box-shadow:0 16px 40px rgba(0,0,0,.6),0 2px 8px rgba(0,0,0,.4)}" % (ui["overlay"], ui["overlay_border"]))
    if ui.get("card") and ui["card"] != "transparent":
        css += ('[class*="st-key-b5_card"],[data-testid="stExpander"] details,[data-testid="stMetric"]'
                "{background:%s}" % ui["card"])
        # pulsanti non scelti trasparenti: col fondo nero del tema sembravano buchi nei riquadri pieni
        css += '[data-testid="stButtonGroup"] button[aria-checked="false"]{background:transparent !important}'
    return css


def _b5_info(text, key):
    """
    Pulsante "?" che apre `text` (Markdown) in un riquadro: si apre con un tocco e resta aperto finché non si tocca un
    altro punto dello schermo. Sostituisce il parametro help (tooltip che sul telefono si apre a fatica e si chiude
    subito).
    """
    with st.popover(":material/help:", type="tertiary", key=key):
        st.markdown(text)


def _b5_info_label(label, text, key):
    """Etichetta di un controllo con il suo "?" accanto; il controllo va creato con label_visibility="collapsed"."""
    with st.container(horizontal=True, vertical_alignment="center", gap="xsmall"):
        st.markdown(":small[%s]" % _b5_mdx(label), width="content")
        _b5_info(text, key)


def _b5_show_button():
    """"Mostra la previsione" in fondo al cassetto: lo chiude ricalcolando la pagina (come la X o un tocco fuori)."""
    if st.button(":material/check: Mostra la previsione", key="b5_drawer_done", type="primary", width="stretch"):
        st.rerun()


# "Posizione attuale" e "Scegli sulla mappa" nel cassetto Località: componente st.components.v2 (HTML e JavaScript
# nella pagina, nessun pacchetto in più). Tutto avviene nel browser (GPS, mappa, spostamenti) e a Python arriva un solo
# valore, il punto scelto ("punto": {lat, lon, src}). La mappa ha un segnaposto fisso al centro: si sposta la mappa
# sotto il segnaposto (o si tocca un punto e la mappa ci scorre), come nelle app di consegne; Leaflet si carica solo
# alla prima apertura. Stili con prefisso b5w- come quelli dei pulsanti di Streamlit (secondario e primario).
_B5_WHERE_CSS = """
.b5w{display:flex;flex-direction:column;gap:8px}
.b5w-btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;min-height:40px;margin:0;
  padding:4px 12px;border:1px solid rgba(242,242,247,.2);border-radius:8px;background:transparent;color:inherit;
  font:inherit;line-height:1.6;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:border-color .15s,color .15s}
.b5w-btn:focus-visible{border-color:var(--st-primary-color,#0fa874);color:var(--st-primary-color,#0fa874);outline:none}
@media (hover:hover){.b5w-btn:hover{border-color:var(--st-primary-color,#0fa874);color:var(--st-primary-color,#0fa874)}}
.b5w-btn:active{background:rgba(15,168,116,.15)}
.b5w-btn:disabled{opacity:.65;cursor:progress}
.b5w-btn svg{flex:none}
.b5w-primary,.b5w-primary:hover,.b5w-primary:focus-visible{background:var(--st-primary-color,#0fa874);
  border-color:var(--st-primary-color,#0fa874);color:#fff}
.b5w-primary:active{filter:brightness(.9)}
.b5w-msg,.b5w-hint,.b5w-xy{margin:0;font-size:14px;line-height:1.5}
.b5w-msg{color:#E3B04B}
.b5w-hint,.b5w-xy{color:rgba(242,242,247,.6)}
.b5w-xy{text-align:center;font-variant-numeric:tabular-nums}
.b5w-pick{display:flex;flex-direction:column;gap:8px}
.b5w-pick[hidden]{display:none}
.b5w-frame{position:relative;height:300px;border:1px solid rgba(242,242,247,.2);border-radius:8px;overflow:hidden;
  isolation:isolate}
.b5w-map{position:absolute;inset:0;background:#1c1c1f}
.b5w-map.leaflet-container{font:inherit;font-size:12px}
.b5w-pin{position:absolute;left:50%;top:50%;width:28px;height:38px;margin:-37px 0 0 -14px;pointer-events:none;
  z-index:1000;filter:drop-shadow(0 2px 2px rgba(0,0,0,.45))}
"""
_B5_WHERE_JS = r"""
const ICON = (d) => '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" ' +
  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>';
const GPS = ICON('<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none"/>' +
  '<path d="M12 1.5v3M12 19.5v3M1.5 12h3M19.5 12h3"/>');
const MAP = ICON('<path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4zM9 4v14M15 6v14"/>');
const PIN = '<svg viewBox="0 0 28 38" width="28" height="38" aria-hidden="true"><path d="M14 1C7 1 1.5 6.5 1.5 ' +
  '13.4 1.5 23 14 37 14 37s12.5-14 12.5-23.6C26.5 6.5 21 1 14 1z" fill="#0fa874" stroke="#fff" stroke-width="2"/>' +
  '<circle cx="14" cy="13.5" r="4.5" fill="#fff"/></svg>';
const ERR = {
  https: "La posizione del telefono si può usare solo nell'app pubblicata (indirizzo https). Da qui usa la mappa o la ricerca.",
  policy: "Il sito che ospita l'app non permette di leggere la posizione: usa la mappa o la ricerca.",
  1: "Permesso negato: consenti la posizione a questo sito nelle impostazioni del browser e riprova, oppure usa la mappa.",
  2: "Posizione non disponibile: controlla che la localizzazione del telefono sia attiva e riprova.",
  3: "Il GPS non ha risposto in tempo: riprova, meglio all'aperto.",
  map: "Mappa non disponibile: controlla la connessione e riprova.",
};

function leaflet(cfg) {                       // una sola volta per pagina, con verifica dell'impronta (integrity)
  if (window.L && window.L.map) return Promise.resolve(window.L);
  if (!window.__b5Leaflet) {
    window.__b5Leaflet = new Promise((ok, ko) => {
      const css = document.createElement("link");
      css.rel = "stylesheet"; css.href = cfg.base + "leaflet.css"; css.integrity = cfg.css; css.crossOrigin = "";
      document.head.appendChild(css);
      const js = document.createElement("script");
      js.src = cfg.base + "leaflet.js"; js.integrity = cfg.js; js.crossOrigin = "";
      js.onload = () => (window.L ? ok(window.L) : ko());
      js.onerror = () => { window.__b5Leaflet = null; js.remove(); ko(); };
      document.head.appendChild(js);
    });
  }
  return window.__b5Leaflet;
}

export default function ({ data, parentElement, setTriggerValue }) {
  const d = data || {};
  const root = document.createElement("div");
  root.className = "b5w";
  root.innerHTML =
    '<button type="button" class="b5w-btn" data-a="gps">' + GPS + '<span>Posizione attuale</span></button>' +
    '<button type="button" class="b5w-btn" data-a="map" aria-expanded="false">' + MAP +
    '<span>Scegli sulla mappa</span></button>' +
    '<p class="b5w-msg" role="status" hidden></p>' +
    '<div class="b5w-pick" hidden>' +
    '<p class="b5w-hint">Sposta la mappa finché il segnaposto è sul tuo spot, oppure tocca il punto.</p>' +
    '<div class="b5w-frame"><div class="b5w-map"></div><div class="b5w-pin">' + PIN + '</div></div>' +
    '<p class="b5w-xy"></p>' +
    '<button type="button" class="b5w-btn b5w-primary" data-a="use">Usa questo punto</button></div>';
  parentElement.appendChild(root);
  const q = (s) => root.querySelector(s);
  const gps = q('[data-a="gps"]'), open = q('[data-a="map"]'), use = q('[data-a="use"]');
  const pick = q(".b5w-pick"), xy = q(".b5w-xy");
  const say = (t) => { const m = q(".b5w-msg"); m.textContent = t || ""; m.hidden = !t; };
  const label = (b, t) => { b.querySelector("span").textContent = t; };
  let map = null, ro = null;

  gps.onclick = () => {
    say("");
    if (!window.isSecureContext || !navigator.geolocation) { say(ERR.https); return; }
    // l'app pubblicata gira dentro una cornice (iframe) del sito che la ospita: se la cornice non concede la
    // posizione, Chrome ed Edge lo dicono qui; Firefox invece non risponde affatto, da cui il controllo a 25 s
    const policy = document.permissionsPolicy || document.featurePolicy;
    if (policy && policy.allowsFeature && !policy.allowsFeature("geolocation")) { say(ERR.policy); return; }
    gps.disabled = true;
    label(gps, "Cerco la posizione…");
    let done = false;
    const fail = (code) => {
      if (done) return;
      done = true; gps.disabled = false; label(gps, "Posizione attuale"); say(ERR[code] || ERR[2]);
    };
    const watchdog = setTimeout(() => fail(3), 25000);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        if (done) return;
        done = true; clearTimeout(watchdog);
        setTriggerValue("punto", { lat: p.coords.latitude, lon: p.coords.longitude, src: "gps" });
      },
      (e) => { clearTimeout(watchdog); fail(e.code); },
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 60000 });
  };

  const center = () => {
    const c = map.getCenter().wrap();
    xy.textContent = c.lat.toFixed(4) + ", " + c.lng.toFixed(4);
    return c;
  };
  open.onclick = () => {
    const opening = pick.hidden;
    pick.hidden = !opening;
    open.setAttribute("aria-expanded", String(opening));
    label(open, opening ? "Chiudi la mappa" : "Scegli sulla mappa");
    if (!opening) return;
    say("");
    if (map) { map.invalidateSize(); return; }
    leaflet(d.leaflet).then((L) => {
      if (!root.isConnected || map) return;
      map = L.map(q(".b5w-map")).setView([d.lat, d.lon], d.zoom || 12);
      map.attributionControl.setPrefix(false);
      L.tileLayer(d.tiles, { maxZoom: 19, attribution: d.attr }).addTo(map);
      map.on("move", center);
      map.on("click", (e) => map.panTo(e.latlng));
      center();
      ro = new ResizeObserver(() => map && map.invalidateSize());
      ro.observe(q(".b5w-map"));
    }).catch(() => say(ERR.map));
  };
  use.onclick = () => {
    if (!map) return;
    const c = center();
    use.disabled = true;
    setTriggerValue("punto", { lat: c.lat, lon: c.lng, src: "mappa" });
  };

  return () => { if (ro) ro.disconnect(); if (map) map.remove(); root.remove(); };
}
"""


def _b5_where(loc):
    """Pulsanti GPS e mappa (componente qui sopra) -> punto scelto in questo giro {lat, lon, src} oppure None."""
    try:
        from streamlit.components import v2 as components_v2
        comp = components_v2.component("b5_dove", css=_B5_WHERE_CSS, js=_B5_WHERE_JS, isolate_styles=False)
        res = comp(key="b5_where", on_punto_change=lambda: None,
                   data={"lat": _b5_f(loc.get("lat"), 43.13), "lon": _b5_f(loc.get("lon"), 12.10), "zoom": 11,
                         "tiles": B5_MAP_TILES, "attr": B5_MAP_ATTRIBUTION, "leaflet": B5_LEAFLET})
    except Exception:
        return None                     # Streamlit senza componenti v2: restano ricerca e coordinate
    pt = res.get("punto") if hasattr(res, "get") else None
    if not isinstance(pt, dict):
        return None
    lat, lon = _b5_f(pt.get("lat"), None), _b5_f(pt.get("lon"), None)
    if lat is None or lon is None or not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return {"lat": lat, "lon": lon, "src": "gps" if pt.get("src") == "gps" else "mappa"}


# Cassetti (st.dialog): ogni tocco al loro interno riesegue solo la funzione del cassetto; on_dismiss="rerun"
# ricalcola la pagina quando il cassetto si chiude, così la previsione usa subito le scelte nuove.
@st.dialog("Località", position=B5_DRAWER_POSITION, icon=":material/location_on:", on_dismiss="rerun")
def _b5_drawer_location():
    ss = st.session_state
    if ss.pop("b5_drawer_close", False):           # località scelta (callback): si chiude e mostra la previsione
        st.rerun()
    # enter_to_submit=False: senza, Streamlit scrive "Press Enter to submit form" (in inglese) dentro il campo
    with st.form("b5_form_search", border=False, enter_to_submit=False):
        st.text_input("Comune vicino al lago o coordinate", key="b5_q", placeholder="Bolsena · 43.12, 12.10")
        st.form_submit_button(":material/search: Cerca", on_click=_b5_cb_search, type="primary", width="stretch")
    if ss.get("b5_geo_msg"):
        (st.info if ss.get("b5_geo_found") else st.warning)(_b5_mdx(ss["b5_geo_msg"]))
    results = ss.get("b5_geo_results") or []
    if len(results) > 1:
        key = "b5_pick_%d" % int(ss.get("b5_geo_n", 0))
        labels = [_b5_mdx(_b5_loc_label(r)) for r in results]
        # index=None: nessun risultato già scelto, così anche il primo si sceglie con un tocco
        st.radio("Risultati: tocca quello giusto", list(range(len(results))), key=key, index=None,
                 format_func=lambda i: labels[i] if isinstance(i, int) and 0 <= i < len(labels) else "",
                 on_change=_b5_cb_pick, args=(key,))
    loc = ss["b5_loc"]
    point = _b5_where(loc)
    if point:                                       # punto dal GPS o dalla mappa: nome, fuso, e il cassetto si chiude
        with st.spinner("Cerco il nome del posto…"):
            ss["b5_loc"] = _b5_point_location(point["lat"], point["lon"], point["src"])
        st.rerun()
    st.caption("Ora: %s · %.3f, %.3f" % (_b5_mdx(_b5_loc_label(loc)), _b5_f(loc.get("lat")), _b5_f(loc.get("lon"))))


@st.dialog("Condizioni dello spot", position=B5_DRAWER_POSITION, icon=":material/tune:", on_dismiss="rerun")
def _b5_drawer_conditions():
    """Spot, acqua, prede, pressione, torbidità e sonda: widget "b5d_..." che salvano subito nelle chiavi "b5_..."."""
    ss = st.session_state

    def saves(key):
        return {"key": _b5_dk(key), "on_change": _b5_cb_commit, "args": (key,)}

    with st.container(gap="xsmall"):
        _b5_info_label("Morfologia dello spot", B5_SPOT_HELP, "b5_info_spot")
        spot = st.pills("Morfologia dello spot", _b5_spot_keys(), format_func=_b5_spot_label, required=True,
                        label_visibility="collapsed", **saves("b5_spot"))
    hint = _b5_spot_hint(spot)
    if hint:
        st.caption(_b5_mdx(hint))
    st.segmented_control("Livello dell'acqua", B5_WATER_LEVELS, format_func=B5_WATER_LABELS.get, required=True,
                         width="stretch", **saves("b5_water"))
    st.pills("Base foraggera", B5_FORAGE_BASES, format_func=B5_FORAGE_LABELS.get, required=True,
             **saves("b5_forage"))
    st.segmented_control("Pressione di pesca", B5_PRESSURES, required=True, width="stretch", **saves("b5_press"))
    with st.container(gap="xsmall"):
        _b5_info_label("Torbidità dell'acqua", B5_INFO_TURBIDITY, "b5_info_turb")
        st.pills("Torbidità dell'acqua", B5_TURBIDITIES, required=True,
                 format_func=lambda t: B5_TURBIDITY_LABELS.get(t, t), label_visibility="collapsed",
                 **saves("b5_turb"))
    # etichetta corta: con "Ho misurato la temperatura dell'acqua (sonda)" il "?" usciva dalla riga a 390 px
    with st.container(horizontal=True, vertical_alignment="center", gap="xsmall"):
        probe_on = st.toggle("Temperatura misurata (sonda)", **saves("b5_probe_on"))
        _b5_info(B5_INFO_PROBE, "b5_info_probe")
    if probe_on:
        st.number_input("Temperatura misurata (°C)", min_value=B5_PROBE_MIN, max_value=B5_PROBE_MAX, step=0.1,
                        format="%.1f", **saves("b5_probe_c"))
    st.space("small")
    _b5_show_button()
    st.button("Torna ai valori iniziali", key="b5_drawer_reset", type="tertiary", on_click=_b5_cb_reset,
              width="stretch")


def _b5_open_drawer():
    """Apre il cassetto chiesto dal pulsante dell'intestazione (callback _b5_cb_open), fuori da ogni contenitore."""
    which = st.session_state.pop("b5_drawer", None)
    if which == "loc":
        _b5_drawer_location()
    elif which == "cond":
        _b5_drawer_conditions()


def _b5_probe_value():
    """Temperatura della sonda salvata (°C, entro B5_PROBE_MIN-MAX) oppure None se la sonda è spenta."""
    ss = st.session_state
    if not ss.get("b5_probe_on"):
        return None
    probe = _b5_f(ss.get("b5_probe_c"), None)
    return None if probe is None else round(max(B5_PROBE_MIN, min(B5_PROBE_MAX, probe)), 1)


def _b5_settings_summary(ctl):
    """Riga riassuntiva nell'intestazione: le impostazioni in uso restano leggibili a cassetto chiuso."""
    parts = [
        _b5_spot_label(ctl["spot"]),
        "livello " + B5_WATER_LABELS.get(ctl["water_level"], ctl["water_level"]).lower(),
        "prede: " + _B5_RE_ICON.sub("", B5_FORAGE_LABELS.get(ctl["forage_base"], ctl["forage_base"])).lower(),
        "pressione " + ctl["fishing_pressure"].lower(),
        "torbidità " + ("stimata" if ctl["turbidity"] == "Non specificato" else ctl["turbidity"].lower()),
        "sonda %.1f °C" % ctl["probe"] if ctl["probe"] is not None else "senza sonda",
    ]
    return " · ".join(_b5_mdx(p) for p in parts)


def _b5_controls():
    """Disegna la scelta del giorno e restituisce le scelte dell'utente (dict); il resto si sceglie nei cassetti."""
    ss = st.session_state
    loc = ss["b5_loc"]
    today = _b5_today(loc.get("tz"), loc.get("lon"))

    when = st.segmented_control("Giorno", B5_WHEN_OPTIONS, key="b5_when", required=True, width="stretch",
                                label_visibility="collapsed")
    if when == "Passato":
        days = [today + _b5_dt.timedelta(days=k) for k in range(B5_OFFSET_MIN, 0)]
        # la chiave contiene "oggi": a mezzanotte (o cambiando fuso) lo slider riparte dentro l'intervallo valido
        picked = st.select_slider("Data", days, value=days[-1], format_func=_b5_fmt_date,
                                  key="b5_past_%s" % today.isoformat(), label_visibility="collapsed")
        offset = (picked - today).days if isinstance(picked, _b5_dt.date) else -1
    else:
        offset = B5_WHEN_OFFSETS.get(when, 0)
    return _b5_ctl(offset)


def _b5_ctl(offset):
    """Scelte in uso (località, impostazioni dei cassetti) per il giorno `offset` da oggi; serve anche al Meteo."""
    ss = st.session_state
    loc = ss["b5_loc"]
    today = _b5_today(loc.get("tz"), loc.get("lon"))
    offset = max(B5_OFFSET_MIN, min(B5_OFFSET_MAX, int(offset)))
    return {
        "loc": loc, "lat": _b5_f(loc.get("lat"), 43.13), "lon": _b5_f(loc.get("lon"), 12.10),
        "tz": str(loc.get("tz") or ""), "today": today, "day_offset": offset,
        "target_date": today + _b5_dt.timedelta(days=offset),
        "spot": ss["b5_spot"], "water_level": ss["b5_water"], "forage_base": ss["b5_forage"],
        "fishing_pressure": ss["b5_press"], "probe": _b5_probe_value(), "turbidity": ss["b5_turb"],
    }


# ------------------------------------------------------------------------------
# ESECUZIONE DEI MOTORI: Blocco 1 -> astronomia -> Blocco 2 -> Blocco 3
# ------------------------------------------------------------------------------
def _b5_analyze(sim):
    """Righe di riferimento dal `sim` del Blocco 2 v2: picchi scelti con pick_peak e curve piatte già segnalate."""
    tl = [r for r in (sim.get("timeline") or []) if isinstance(r, dict)]
    best = sim.get("best_hour") if isinstance(sim.get("best_hour"), dict) else (
        max(tl, key=lambda r: _b5_f(r.get("catch_rate"))) if tl else {})
    troph = sim.get("best_trophy_hour") if isinstance(sim.get("best_trophy_hour"), dict) else (
        max(tl, key=lambda r: _b5_f(r.get("trophy_rate"))) if tl else {})
    return {"timeline": tl, "best": best, "troph": troph,
            "flat": bool(sim.get("trophy_flat")), "flat_bai": bool(sim.get("bai_flat"))}


@st.cache_data(ttl=B5_WEATHER_TTL_S, show_spinner=False)
def _b5_fetch_cached(lat, lon, day_offset, spot, target_iso):
    """
    Blocco 1 con la data esplicita (target_date, Blocco 1 v2); un Blocco 1 più vecchio riceve solo l'offset.
    -> {"series": serie del Blocco 1, "fetched_utc": ora del download}. Errori di rete: non finiscono in cache.
    """
    args = (lat, lon, day_offset, spot)
    try:
        series = fetch_thermal_and_weather_series(*args, target_date=target_iso)
    except TypeError as exc:
        if "target_date" not in str(exc):
            raise
        series = fetch_thermal_and_weather_series(*args)
    now = _b5_dt.datetime.now(_b5_dt.timezone.utc)
    _b5_stale_save("pesca", (lat, lon, spot, target_iso), series, now)
    return {"series": series, "fetched_utc": now}


def _b5_stale_path(kind, key):
    return _b5_os.path.join(B5_STALE_DIR, "%s-%s.json" % (kind, _b5_hashlib.sha1(repr(key).encode()).hexdigest()[:20]))


def _b5_stale_save(kind, key, value, when_utc):
    """Salva l'ultimo download riuscito (JSON, scrittura atomica); toglie i file più vecchi di due giorni."""
    try:
        _b5_os.makedirs(B5_STALE_DIR, exist_ok=True)
        path = _b5_stale_path(kind, key)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            _b5_json.dump({"t": when_utc.isoformat(), "v": value}, fh)
        _b5_os.replace(path + ".tmp", path)
        limit = _b5_time.time() - 2 * 86400
        for name in _b5_os.listdir(B5_STALE_DIR):
            full = _b5_os.path.join(B5_STALE_DIR, name)
            if name.endswith(".json") and _b5_os.path.getmtime(full) < limit:
                _b5_os.remove(full)
    except Exception:
        pass                            # senza disco scrivibile resta solo la cache di Streamlit


def _b5_stale_load(kind, key):
    """Ultimo download riuscito -> (valore, ora UTC) se più recente di B5_STALE_MAX_H ore, altrimenti None."""
    try:
        with open(_b5_stale_path(kind, key), encoding="utf-8") as fh:
            got = _b5_json.load(fh)
        when = _b5_dt.datetime.fromisoformat(got["t"])
        if _b5_dt.datetime.now(_b5_dt.timezone.utc) - when > _b5_dt.timedelta(hours=B5_STALE_MAX_H):
            return None
        return got["v"], when
    except Exception:
        return None


def _b5_fetch(ctl):
    """
    -> (serie del Blocco 1, ora UTC del download, True se sono gli ultimi dati salvati perché Open-Meteo non risponde).
    """
    key = (round(ctl["lat"], 4), round(ctl["lon"], 4), int(ctl["day_offset"]), ctl["spot"],
           ctl["target_date"].isoformat())
    try:
        got = _b5_fetch_cached(*key)
    except Exception:
        old = _b5_stale_load("pesca", (key[0], key[1], key[3], key[4]))
        if old is None:
            raise
        return old[0], old[1], True
    return got["series"], got["fetched_utc"], False


def _b5_run(ctl, goal):
    """Esegue i Blocchi 1-2-3 con i controlli scelti. Non solleva eccezioni: gli errori finiscono nel dict."""
    res = {"error": None, "report_error": None, "ctl": ctl, "goal": goal, "date": ctl["target_date"]}

    # --- Blocco 1: meteo e modello termico -------------------------------------------------------------
    try:
        series, res["fetched_utc"], res["stale"] = _b5_fetch(ctl)
    except Exception as exc:
        res["error"] = ("meteo", exc)
        return res

    # Data reale della serie (con target_date coincide con quella scelta)
    try:
        day = _b5_dt.date.fromisoformat(str(series["hourly"][0]["date_str"]))
    except Exception:
        day = ctl["target_date"]
    res["date"] = day

    # --- astronomia (alba/tramonto/luna): richiesta dai Blocchi 2, 3 e 4 ------------------------------
    try:
        astro = _b5_compute_astro(day, ctl["lat"], ctl["lon"], ctl["tz"])
    except Exception:
        astro = _b5_fallback_astro(day.isoformat())
    res["astro"] = astro

    # --- Blocco 2: simulazione delle 24 ore -----------------------------------------------------------
    try:
        sim = ProTourBiologicalEngine.run_pro_simulation(
            series, astro, ctl["turbidity"], manual_water_temp=ctl["probe"], water_level=ctl["water_level"])
        if not isinstance(sim, dict) or not sim.get("timeline"):
            raise ValueError("La simulazione non ha prodotto la timeline oraria.")
    except Exception as exc:
        res["error"] = ("simulazione", exc)
        return res

    ana = _b5_analyze(sim)

    # --- Blocco 3: report tattico (se fallisce, restano grafici e tabella) ---------------------------
    report = None
    try:
        report = TacticalAdvisorV2.generate_pro_report(
            best_hour=ana["best"],
            trend_3d=_b5_f(sim.get("micro_trend_72h", sim.get("thermal_trend_3d", 0.0))),
            astro=astro,
            sim_results=sim,
            water_level=ctl["water_level"],
            forage_base=ctl["forage_base"],
            fishing_pressure=ctl["fishing_pressure"],
            target_mode=goal,
        )
    except Exception as exc:
        res["report_error"] = exc

    res.update({"series": series, "sim": sim, "ana": ana, "report": report})
    return res


# ------------------------------------------------------------------------------
# INTESTAZIONE E AVVISI
# ------------------------------------------------------------------------------
def _b5_badges(items, color="gray"):
    return " ".join(":%s-badge[%s]" % (color, _b5_mdx_icon(t)) for t in items if t)


# Icone dei riquadri sotto il nome (data, alba e tramonto, luna) disegnate qui in SVG: griglia alta 24, tratto 2 ed
# estremità tonde come le icone Material del resto dell'app, colore del testo. Vedi le note in testa al blocco.
_B5_SVG = ('<svg viewBox="0 0 %d 24" width="%s" height="%s" fill="none" stroke="currentColor" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>')
_B5_ICONS = {                           # nome: (larghezza della griglia, disegno)
    "data": (24, '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>'),
    # arco del sole: orizzonte tenue, percorso a puntini, sole pieno a mezzogiorno
    "arco": (36, '<path d="M1 20h34" stroke-opacity=".55"/><path d="M5 20A13 12 0 0 1 31 20" stroke-width="2.4" '
                 'stroke-dasharray="0 3.6"/><circle cx="18" cy="8" r="3.6" fill="currentColor" stroke="none"/>'),
    "sole": (24, '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 '
                 '17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
    # notte polare: il sole resta sotto l'orizzonte
    "notte": (24, '<path d="M2 10h20"/><path d="M7 10a5 5 0 0 0 10 0" stroke-opacity=".55"/>'),
    # sezione Meteo: riquadri del giorno scelto e avvisi
    "termometro": (24, '<path d="M10 14.2V5a2 2 0 0 1 4 0v9.2a4.2 4.2 0 1 1-4 0z"/><path d="M12 17.4v-5.6"/>'),
    "goccia": (24, '<path d="M12 3.2c3.2 3.8 5.8 7 5.8 10.3a5.8 5.8 0 0 1-11.6 0c0-3.3 2.6-6.5 5.8-10.3z"/>'),
    "raffica": (24, '<path d="M3 8.5h10.5a3 3 0 1 0-3-3M3 12.5h15.5a3 3 0 1 1-3 3M3 16.5h6"/>'),
    "temporale": (24, '<path d="M13.5 2.5 5.5 13.5h5.8l-1.3 8 8.5-11.5h-5.8l.8-7.5z"/>'),
    # sezione Diario: cappotto (cerchio barrato) e ore in acqua
    "zero": (24, '<circle cx="12" cy="12" r="7.5"/><path d="M6.7 17.3 17.3 6.7"/>'),
    "orologio": (24, '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
}


def _b5_icon(name, height=14):
    width, body = _B5_ICONS[name]
    return _B5_SVG % (width, "%g" % round(height * width / 24.0, 2), height, body)


def _b5_moon_icon(illum, elong, lat):
    """
    Luna com'è in cielo: disco con il contorno tenue e la parte illuminata piena (illum 0-100 %). Il terminatore è
    mezza ellisse larga |1 - 2k| volte il raggio. Crescente illuminata a destra, calante a sinistra; al contrario
    nell'emisfero sud.
    """
    k = max(0.0, min(1.0, _b5_f(illum, 50.0) / 100.0))
    lit = '<path d="M12 4a8 8 0 0 1 0 16A%.2f 8 0 0 %d 12 4z" fill="currentColor" stroke="none"/>' % (
        8.0 * abs(1.0 - 2.0 * k), 1 if k > 0.5 else 0)
    if (_b5_f(elong, 90.0) % 360.0 > 180.0) != (_b5_f(lat, 43.0) < 0.0):
        lit = '<g transform="matrix(-1 0 0 1 24 0)">%s</g>' % lit
    return _B5_SVG % (24, 14, 14, '<circle cx="12" cy="12" r="8" stroke-width="1.5" stroke-opacity=".5"/>' + lit)


def _b5_chip(icon, text, label=""):
    """Riquadro come i badge grigi di Streamlit; `label` è letto dai lettori di schermo e appare al passaggio."""
    tip = ' title="%s"' % _b5_html.escape(label) if label else ""
    sr = '<span class="b5-sr">%s</span>' % _b5_html.escape(label) if label else ""
    return '<span class="b5-chip"%s>%s%s<span>%s</span></span>' % (tip, icon, sr, _b5_html.escape(text))


def _b5_sun_chip(astro):
    """Alba e tramonto in un riquadro: le due ore ai lati dell'arco del sole, da sinistra a destra come il giorno."""
    esc = _b5_html.escape
    return ('<span class="b5-chip" title="Alba e tramonto"><span class="b5-sr">Alba</span><span>%s</span>%s'
            '<span class="b5-sr">tramonto</span><span>%s</span></span>'
            % (esc(astro.get("sunrise_str", "--:--")), _b5_icon("arco", 16), esc(astro.get("sunset_str", "--:--"))))


def _b5_render_header(ctl, day, astro, meteo=False):
    """Riquadro in cima alla pagina. Nel Meteo senza il pulsante Condizioni e senza la riga delle impostazioni."""
    loc = ctl["loc"]
    sub = " · ".join(p for p in (str(loc.get("admin") or ""), str(loc.get("country") or "")) if p)
    with st.container(border=True, gap="xsmall", key="b5_card_header"):
        with st.container(horizontal=True, vertical_alignment="top", gap="small"):
            with st.container(gap="xsmall"):
                # il nome è il pulsante del cassetto Località: la freccina accanto dice che si può toccare. Sta nel
                # testo, attaccata all'ultima parola (spazio unificatore): con icon= restava sul bordo destro, lontana
                # dal nome quando questo va a capo
                st.button("%s :material/expand_more:" % _b5_mdx(loc.get("name") or "Località"), key="b5_open_loc",
                          type="tertiary", on_click=_b5_cb_open, args=("loc",))
                if sub:
                    st.caption(_b5_mdx(sub))
            if not meteo:
                with st.container(width="content", key="b5_actions"):
                    st.button(":material/tune:", key="b5_open_cond", on_click=_b5_cb_open, args=("cond",))
        chips = [_b5_chip(_b5_icon("data"), "%s · %s" % (_b5_rel_label((day - ctl["today"]).days),
                                                           _b5_fmt_date(day)))]
        if astro:
            status = astro.get("sun_status", "normale")
            if status == "sempre_su":
                chips.append(_b5_chip(_b5_icon("sole"), "Sole di mezzanotte"))
            elif status == "sempre_giu":
                chips.append(_b5_chip(_b5_icon("notte"), "Notte polare"))
            else:
                chips.append(_b5_sun_chip(astro))
            illum = _b5_f(astro.get("moon_illum"), 0.0)
            phase = str(astro.get("moon_phase") or "")
            chips.append(_b5_chip(_b5_moon_icon(illum, astro.get("moon_elong"), astro.get("lat")),
                                  "%d %%" % int(round(illum)) + (" · " + phase.lower() if phase and phase != "n/d" else ""),
                                  "Luna"))
        # HTML nel Markdown: st.html toglierebbe gli SVG
        st.markdown('<div class="b5-chips">%s</div>' % "".join(chips), unsafe_allow_html=True)
        if not meteo:
            st.caption(_b5_settings_summary(ctl))
        if loc == B5_DEFAULT_LOCATION:
            st.caption("Per il tuo lago tocca il nome qui sopra.")


def _b5_config_warnings():
    """
    Avvisi per chi avvia l'app senza .streamlit/config.toml. Tema non scuro: grafici e testi sono disegnati per il nero
    e diventano poco leggibili. Magic attiva: build_app.py neutralizza le espressioni isolate dei Blocchi 1-3, ma un
    app.py assemblato in altro modo potrebbe ancora stamparle nella pagina.
    """
    try:
        base = str(st.get_option("theme.base") or "")
    except Exception:
        base = "dark"
    if base != "dark":
        st.warning("Tema scuro non attivo: manca il file `config.toml` dentro una cartella `.streamlit`, nella "
                   "cartella da cui parte l'app (su GitHub: `.streamlit/config.toml`). Senza, grafici e testi "
                   "disegnati per lo sfondo nero restano poco leggibili.", icon=":material/warning:")
    try:
        on = bool(st.get_option("runner.magicEnabled"))
    except Exception:
        on = False
    if on and "_b0_magia" not in globals():
        st.warning("La «magic» di Streamlit è attiva: in cima alla pagina compaiono le descrizioni dei blocchi e "
                   "la documentazione dei moduli. Metti la cartella `.streamlit` (con `config.toml`) accanto ad "
                   "`app.py`, oppure avvia con `streamlit run app.py --runner.magicEnabled false`.", icon=":material/warning:")


def _b5_render_missing(missing):
    st.error("Mancano: %s. Rigenera app.py con build_app.py (Blocchi 1, 2, 3, 4 e 5 nello stesso file)."
             % _b5_mdx(", ".join(missing)), title="File assemblato in modo incompleto", icon=":material/warning:")


def _b5_render_error(res):
    stage, exc = res["error"]
    if stage == "meteo":
        if isinstance(exc, requests.exceptions.HTTPError):
            text = "Open-Meteo ha risposto con un errore. Riprova tra qualche minuto."
        elif isinstance(exc, requests.exceptions.Timeout):
            text = "Open-Meteo non ha risposto in tempo. Riprova tra poco."
        elif isinstance(exc, requests.exceptions.RequestException):
            text = "Non riesco a contattare Open-Meteo. Controlla la connessione e riprova tra poco."
        elif isinstance(exc, ValueError):
            text = "Open-Meteo ha restituito una serie incompleta per la data scelta. Prova un'altra data o aggiorna i dati."
        else:
            text = "Errore imprevisto nel Blocco 1 (dati meteo e modello termico)."
        title = "Dati meteo non disponibili"
    else:
        text = "Errore imprevisto nel Blocco 2 (simulazione bio-energetica)."
        title = "Simulazione non riuscita"
    st.error(text, title=title, icon=":material/warning:")
    st.button(":material/refresh: Riprova", key="b5_retry", on_click=_b5_cb_refresh, width="stretch")
    with st.expander("Dettagli tecnici"):
        st.text(_b5_short_exc(exc, 600))


def _b5_render_notices(res):
    """Avvisi sopra i tab: dati salvati (Open-Meteo non risponde), sonda attiva, rischio ghiaccio."""
    ctl, series = res["ctl"], res.get("series") or {}
    if res.get("stale"):
        st.warning("Open-Meteo non risponde: uso gli ultimi dati scaricati (%s). Riprova più tardi con «Aggiorna i "
                   "dati meteo»." % _b5_mdx(_b5_fetched_text(res)[len("Dati meteo scaricati "):] or "ora non nota"),
                   icon=":material/cloud_off:")
    if ctl["probe"] is not None:
        model_t = _b5_f(series.get("hourly_mean_water_temp", series.get("base_water_temp")), None)
        txt = "Sonda attiva: **%.1f °C**" % ctl["probe"]
        if model_t is not None:
            txt += " (il modello stimava %.1f °C)" % model_t
        st.info(txt + ". Le temperature orarie usano la tua misura con l'andamento del modello; i trend restano "
                      "quelli del modello.", icon=":material/thermostat:")
    if series.get("ice_risk"):
        st.warning("Acqua vicina a 0 °C: possibile ghiaccio, il modello termico qui è poco affidabile.", icon=":material/ac_unit:")


def _b5_render_data_notes(res):
    """Avvisi tecnici dei Blocchi 1 e 2 (buchi nei dati, valori di riserva) in un pannello chiuso."""
    series, sim = res.get("series") or {}, res.get("sim") or {}
    notes = []
    for msg in list(series.get("warnings") or []) + list(sim.get("warnings") or []):
        msg = " ".join(str(msg).split())
        if msg and msg not in notes:
            notes.append(msg)
    if not notes and not series.get("low_confidence"):
        return
    title = ":material/info: Note sui dati" + (" · affidabilità ridotta" if series.get("low_confidence") else "")
    with st.expander(title):
        if series.get("low_confidence"):
            st.caption("Per questa data i dati meteo storici sono incompleti: la temperatura stimata dell'acqua "
                       "è meno affidabile del solito.")
        st.markdown("\n".join("- " + _b5_mdx(n) for n in notes))


# ------------------------------------------------------------------------------
# TAB 1 — GRAFICI
# ------------------------------------------------------------------------------
def _b5_plotly(fig, key):
    """Grafici del Blocco 4 con i loro colori (theme=None) e la sua configurazione per il touch."""
    cfg = globals().get("MOBILE_PLOTLY_CONFIG") or {"displayModeBar": False}
    st.plotly_chart(fig, width="stretch", theme=None, key=key, config=cfg)


def _b5_widget_html(sim, astro):
    """HTML del grafico orario a colonnine del Blocco 4 v3; "" se il Blocco 4 non lo offre, non ha dati adatti o va in
    errore (allora caselle Acqua / O₂ e grafico Plotly)."""
    make = globals().get("create_mobile_hourly_widget")
    if not callable(make):
        return ""
    try:
        return make(sim, astro) or ""
    except Exception:
        return ""


def _b5_hourly_widget(html):
    """
    Mostra il grafico orario in un iframe (il suo JavaScript gestisce schede, tocchi e riquadro dell'ora).
    st.iframe esiste da Streamlit 1.66 (quello richiesto); components.v1.html è la riserva per versioni vecchie.
    """
    height = int(globals().get("B4_W_HEIGHT", 524))
    frame = getattr(st, "iframe", None)
    if callable(frame):
        frame(html, height=height, alt=B5_WIDGET_ALT)
    else:
        import streamlit.components.v1 as _b5_components
        _b5_components.html(html, height=height, scrolling=False)


def _b5_water_metrics(ref, sim):
    """
    Caselle Acqua °C e O₂ mg/L all'ora `ref` con la riga di note e il "?". Solo con il grafico Plotly di riserva: col
    grafico a colonnine del Blocco 4 acqua e ossigeno stanno nel suo riquadro dell'ora e seguono l'ora selezionata.
    """
    wt = _b5_f(ref.get("water_temp_used", ref.get("water_temp")), None)
    micro = _b5_f(sim.get("micro_trend_72h", sim.get("thermal_trend_3d")), None)
    do_ref = _b5_do_mg_l(ref)
    do_all = [v for v in (_b5_do_mg_l(r) for r in sim.get("timeline") or [] if isinstance(r, dict)) if v is not None]
    # valori senza unità e niente sotto-valori: su 320-375 px "9.3 mg/L" e i sotto-valori venivano troncati
    c3, c4 = st.columns(2, wrap=False)
    with c3:
        st.metric("Acqua °C", "n/d" if wt is None else "%.1f" % wt, border=True)
    with c4:
        st.metric("O₂ mg/L", "n/d" if do_ref is None else "%.1f" % do_ref, border=True)
    notes = ["Alle %s" % _b5_row_label(ref)]
    if micro is not None:
        notes.append("acqua %+.1f °C in 72 h" % micro)
    if do_all:
        notes.append("ossigeno minimo del giorno %.1f mg/L" % min(do_all))
    with st.container(horizontal=True, vertical_alignment="center", gap="small", wrap=False):
        st.caption(" · ".join(notes))
        _b5_info(B5_INFO_WATER, "b5_info_water")


def _b5_tab_charts(res):
    sim, astro, ana = res["sim"], res["astro"], res["ana"]
    best, troph, flat, flat_bai = ana["best"], ana["troph"], ana["flat"], ana["flat_bai"]
    tl = ana["timeline"]
    ref = best                    # ora di riferimento delle caselle e dei fattori di riserva: il picco dell'attività

    if sim.get("no_good_window"):
        st.warning("Giornata difficile: l'indice di attività resta basso in tutte le ore.", icon=":material/ac_unit:")
    elif sim.get("window_quality") == "scarsa":
        st.info("Finestre di qualità scarsa: anche l'ora migliore ha un indice di attività basso.")

    widget = _b5_widget_html(sim, astro)
    # etichette corte (su 320-393 px quelle lunghe venivano troncate): l'ora del picco va nel sotto-valore.
    # Col grafico a colonnine (Blocco 4 v3) il picco è già nel grafico: schede solo se B5_SHOW_INDEX_METRICS.
    if B5_SHOW_INDEX_METRICS or not widget:
        c1, c2 = st.columns(2, wrap=False)
        with c1:
            st.metric(":material/local_fire_department: Attività", _b5_idx(best.get("catch_rate")), border=True,
                      delta="senza picco" if flat_bai else "picco %s" % _b5_row_label(best),
                      delta_color="off" if flat_bai else "green", delta_arrow="off")
        with c2:
            tmax = max([_b5_f(r.get("trophy_rate")) for r in tl] or [0.0])
            st.metric(":material/workspace_premium: Trophy", _b5_idx(tmax if flat else troph.get("trophy_rate")),
                      border=True, delta="senza picco" if flat else "picco %s" % _b5_row_label(troph),
                      delta_color="off" if flat else "violet", delta_arrow="off")

    if not widget:
        _b5_water_metrics(ref, sim)
    do_all = [v for v in (_b5_do_mg_l(r) for r in tl) if v is not None]
    do_min = min(do_all) if do_all else None
    if do_min is not None and do_min < B5_DO_LIMITED_MG_L:
        level = "stress" if do_min < B5_DO_STRESS_MG_L else "attività limitata"
        st.warning("Ossigeno basso: minimo %.1f mg/L nel giorno (%s secondo i criteri EPA 1986)." % (do_min, level),
                   icon=":material/water_drop:")

    # grafico orario: colonnine interattive (Blocco 4 v3); se non disponibili o in errore, le curve Plotly
    shown = False
    if widget:
        try:
            _b5_hourly_widget(widget)
            shown = True
        except Exception:
            _b5_water_metrics(ref, sim)          # l'iframe non è partito: le caselle tornano sopra il Plotly
    if not shown:
        try:
            _b5_plotly(create_mobile_plotly_chart(sim, astro), "b5_chart_main")
        except Exception as exc:
            st.warning("Grafico orario non disponibile: %s" % _b5_mdx(_b5_short_exc(exc)))

    # i fattori sono nel grafico orario (seguono l'ora selezionata): il grafico Plotly serve solo come riserva
    factors = None if shown else (globals().get("create_mobile_factors_chart") or globals().get("create_mobile_radar"))
    if factors is not None:
        try:
            with st.container(border=True, key="b5_card_factors"):
                _b5_plotly(factors(ref), "b5_chart_factors")
        except Exception as exc:
            st.warning("Grafico dei fattori non disponibile: %s" % _b5_mdx(_b5_short_exc(exc)))


# ------------------------------------------------------------------------------
# TAB 2 — STRATEGIA (report tattico del Blocco 3)
# ------------------------------------------------------------------------------
# Il report del Blocco 3 in sezioni (_b5_strategy_sections), nell'ordine di chi pesca: quando, dove, esche, recupero,
# colori, canna e filo e per ultimo il perché. Ogni sezione ha un riassunto di una riga preso dal suo testo (la
# riga-titolo o il primo punto dell'elenco, accorciati: nessuna frase nuova) e il testo completo. Il riquadro BIO-ALERT
# non c'è più: picco, strike zone e stato biologico sono i riassunti di "quando", "dove" e "perché".
_B5_RE_MD_MARKS = _b5_re.compile(r":material/[a-z0-9_]+:|\*\*|\*|`")
_B5_RE_CUT = _b5_re.compile(r"\s·\s|[:;]\s")
_B5_RE_RANGE_M = _b5_re.compile(r"(\d+(?:\.\d+)?)\s*m\s*-\s*(\d+(?:\.\d+)?)\s*m")
_B5_RE_TAIL_PAREN = _b5_re.compile(r"\s*\([^)]*\)\s*$")
_B5_RE_WORD_PAREN = _b5_re.compile(r"\s*\([^)\d]*\)")            # parentesi senza numeri: "(con un po' d'onda)"


def _b5_plain(text):
    """Testo del Blocco 3 senza icone e segni Markdown, spazi normalizzati."""
    return " ".join(_B5_RE_MD_MARKS.sub("", str(text or "")).split())


def _b5_head(text):
    """Prima riga non vuota, in chiaro: i testi del Blocco 3 si aprono con un titolo in grassetto."""
    for line in str(text or "").split("\n"):
        line = _b5_plain(line)
        if line and not _B5_RE_HR.match(line):
            return line
    return ""


def _b5_item(text, label=""):
    """Primo punto dell'elenco (o quello con l'etichetta `label`) senza etichetta: '- **Fondo:** neko rig' -> 'neko rig'."""
    for line in str(text or "").split("\n"):
        if not _B5_RE_LIST.match(line):
            continue
        plain = _b5_plain(_B5_RE_LIST.sub("", line, count=1))
        head, sep, tail = plain.partition(":")
        if label and head.strip().lower() != label.lower():
            continue
        return tail.strip() if sep and len(head) <= 40 and tail.strip() else plain
    return ""


def _b5_short(text, limit=80):
    """Riassunto: fino al primo ' · ', ':' o ';', fasce '2.5m - 5.0m' -> '2.5–5.0 m', maiuscola iniziale."""
    t = _B5_RE_CUT.split(str(text or ""), maxsplit=1)[0].strip().rstrip(".")
    t = _B5_RE_RANGE_M.sub("\\1–\\2 m", t)
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t[:1].upper() + t[1:]


def _b5_hint_for(title, hint):
    """Riassunto senza la parola del titolo in testa: "Colori" + "Colori pieni..." -> "Pieni..."."""
    h = str(hint or "")
    if title and h.lower().startswith(title.lower() + " "):
        h = h[len(title):].strip()
        h = h[:1].upper() + h[1:]
    return h


def _b5_kin_hint(text):
    """'Recupero molto lento (acqua 13.5 °C, ore 16:00)' -> 'Molto lento'."""
    t = _B5_RE_TAIL_PAREN.sub("", _b5_head(text))
    if t.lower().startswith("recupero "):
        t = t[len("recupero "):]
    return _b5_short(t)


def _b5_when_numbers(ana):
    """Testo di "Ore migliori" (obiettivo Numeri): le tre ore con l'attività più alta e il picco Trophy."""
    top = sorted(ana["timeline"], key=lambda r: -_b5_f(r.get("catch_rate")))[:3]
    lines = []
    if ana.get("flat_bai"):
        lines.append("Attività senza un picco netto: le ore si equivalgono.")
    elif top:
        lines.append("Ore con l'indice di attività più alto: %s." % ", ".join(
            "**%s** (%s)" % (_b5_row_label(r), _b5_idx(r.get("catch_rate"))) for r in top))
    if not ana["flat"]:
        lines.append("Pesci grandi: indice Trophy più alto alle **%s** (%s)."
                     % (_b5_row_label(ana["troph"]), _b5_idx(ana["troph"].get("trophy_rate"))))
    lines.append("Gli indici vanno da 0 a 100 e confrontano le ore del giorno: non sono probabilità. Ora per ora: "
                 "tab «Ore».")
    return "\n\n".join(lines)


def _b5_strategy_sections(report, ana, goal, state):
    """
    Sezioni del tab: dizionari con id, icon, title, hint (riassunto) e parts [(sottotitolo o None, testo Markdown)].
    Con "Trophy" la prima sezione è la Strategia Big Bass (ora, indice, condizioni e testo del Blocco 3) e l'esca
    da trofeo diventa la prima scelta tra le esche. Le sezioni senza testo non compaiono.
    """
    troph_txt = str(report.get("strategia_trophy") or "")
    trophy = goal == "Trophy" and bool(troph_txt.strip())
    if not trophy:
        troph_txt = ""
    condizione = str(report.get("condizione") or "")
    approccio = _b5_remove_part(report.get("approccio"), condizione)
    primarie = _b5_remove_part(report.get("esche_primarie"), troph_txt)
    secondarie = _b5_remove_part(report.get("esche_secondarie"), troph_txt)
    gear = str(report.get("gear_setup") or "")
    cinetica = _b5_remove_part(report.get("recupero"), gear)
    colore = str(report.get("colore") or report.get("colori") or "")

    if trophy:
        row = ana["troph"]
        when = ("Nessun picco Trophy oggi" if ana["flat"]
                else "Ore %s · indice Trophy %s" % (_b5_row_label(row), _b5_idx(row.get("trophy_rate"))))
        when_text = troph_txt.split("\n", 1)[1] if "\n" in troph_txt else ""   # la prima riga ripete ora e indice
        big = _b5_item(troph_txt, "Esca da trofeo")
        if big:
            primarie = "**Esca da trofeo:** %s" % big + ("\n\n" + primarie if primarie else "")
        lure = big or _b5_item(primarie) or _b5_head(primarie)
    else:
        row = ana["best"]
        when = ("Nessun picco di attività oggi" if ana.get("flat_bai")
                else "Ore %s · indice attività %s" % (_b5_row_label(row), _b5_idx(row.get("catch_rate"))))
        when_text = _b5_when_numbers(ana)
        lure = _b5_item(primarie) or _b5_head(primarie)
    lure = _b5_short(_B5_RE_WORD_PAREN.sub("", lure))

    def sec(sid, icon, title, hint, parts):
        return {"id": sid, "icon": icon, "title": title, "hint": hint, "trophy": trophy and sid == "quando",
                "parts": [(cap, txt) for cap, txt in parts if str(txt or "").strip()]}

    secs = [
        sec("quando", ":material/schedule:", "Strategia Big Bass" if trophy else "Ore migliori", when,
            [(None, when_text)]),
        sec("dove", ":material/location_on:", "Dove cercarli",
            _b5_short(report.get("strike_zone") or _b5_head(approccio)), [(None, approccio)]),
        sec("esche", ":material/phishing:", "Esche", lure,
            [("PRIMA SCELTA", primarie), ("SECONDA SCELTA", secondarie)]),
        sec("recupero", ":material/speed:", "Recupero", _b5_kin_hint(cinetica), [(None, cinetica)]),
        sec("colori", ":material/palette:", "Colori",
            _b5_hint_for("Colori", _b5_short(_b5_item(colore) or _b5_head(colore))),
            [(None, colore)]),
        sec("setup", ":material/build:", "Canna e filo", _b5_short(_b5_head(gear)), [(None, gear)]),
        sec("perche", ":material/ecg_heart:", "Perché: condizione del pesce",
            _b5_short(state or _b5_head(condizione)), [(None, condizione)]),
    ]
    return [s for s in secs if s["parts"] or s["trophy"]]


def _b5_trophy_stats(ana):
    """Ora migliore Trophy con indice e condizioni di quell'ora (temperatura, vento, pressione)."""
    row, flat = ana["troph"], ana["flat"]
    if flat:
        st.metric("Ora migliore", "nessuna", delta="curva Trophy piatta", delta_color="off", delta_arrow="off")
        return
    st.metric("Ora migliore", _b5_row_label(row), delta="indice Trophy %s" % _b5_idx(row.get("trophy_rate")),
              delta_color="violet", delta_arrow="off")
    chips = []
    wt = _b5_f(row.get("water_temp_used", row.get("water_temp")), None)
    if wt is not None:
        chips.append(":material/thermostat: %.1f °C" % wt)
    if row.get("wind") is not None:
        chips.append(":material/air: %.0f km/h" % _b5_f(row.get("wind")))
    if row.get("pressure_delta") is not None:
        chips.append(":material/explore: %+.1f hPa/3 h" % _b5_f(row.get("pressure_delta")))
    if chips:
        st.markdown(_b5_badges(chips, "violet"))


def _b5_section_body(sec, ana):
    if sec["trophy"]:
        _b5_trophy_stats(ana)
    for cap, text in sec["parts"]:
        if cap:
            st.caption(cap)
        st.markdown(_b5_md_text(text))


def _b5_goal_control():
    """Numeri / Trophy in cima al tab: cambiarlo rifà il report del Blocco 3 con l'altro obiettivo."""
    st.segmented_control("Obiettivo della strategia", B5_GOALS, format_func=B5_GOAL_LABELS.get, key="b5_goal",
                         required=True, width="stretch", label_visibility="collapsed")
    st.caption(_b5_mdx(B5_GOAL_NOTES.get(st.session_state["b5_goal"], "")))


def _b5_report_sections(res):
    """Selettore dell'obiettivo e sezioni del report; None (con l'errore mostrato) se il Blocco 3 non ha risposto."""
    _b5_goal_control()
    report = res.get("report")
    if not isinstance(report, dict):
        exc = res.get("report_error")
        st.error(_b5_mdx(_b5_short_exc(exc) if exc is not None else "Il Blocco 3 non ha restituito dati."),
                 title="Report tattico non disponibile", icon=":material/warning:")
        return None
    state = (res.get("sim") or {}).get("biological_state")
    return _b5_strategy_sections(report, res["ana"], res["goal"], state)


# Il piano è una griglia di riquadri (2 per riga), ognuno con il riassunto della sua sezione;
# toccandolo, il testo completo si apre nel cassetto da destra, come Località e Condizioni. Il cassetto si chiude
# senza ricalcolare la pagina (on_dismiss="ignore"). All'apertura il tab sta in circa una schermata.
_B5_TILE_ROWS = (("quando", "dove"), ("esche", "recupero"), ("colori", "setup"), ("perche",))
_B5_TILE_LABELS = {"quando": "Quando", "dove": "Dove", "esche": "Esca", "recupero": "Recupero", "colori": "Colori",
                   "setup": "Canna e filo", "perche": "Perché"}


def _b5_cb_strat(sid):
    st.session_state["b5_strat_open"] = sid


def _b5_tile(s):
    """Riquadro: etichetta, riassunto (al massimo 3 righe) e un pulsante invisibile grande quanto il riquadro."""
    with st.container(border=True, key="b5_tile_" + s["id"], gap="xsmall", height="stretch"):
        st.caption("%s %s" % (s["icon"], _B5_TILE_LABELS.get(s["id"], s["title"]).upper()))
        st.markdown("**%s**" % _b5_mdx(s["hint"] or s["title"]))
        st.button("Apri: %s" % s["title"], key="b5_tbtn_" + s["id"], on_click=_b5_cb_strat, args=(s["id"],))


def _b5_section_drawer(s, ana):
    @st.dialog(s["title"], position=B5_DRAWER_POSITION, icon=s["icon"], on_dismiss="ignore")
    def drawer():
        _b5_section_body(s, ana)
    drawer()


def _b5_tab_report(res):
    secs = _b5_report_sections(res)
    if secs is None:
        return
    by = {s["id"]: s for s in secs}
    st.caption("Tocca un riquadro per il dettaglio.")
    for row in _B5_TILE_ROWS:
        row = [sid for sid in row if sid in by]
        if not row:
            continue
        for col, sid in zip(st.columns(len(row), gap="small", wrap=False), row):
            with col:
                _b5_tile(by[sid])
    sid = st.session_state.pop("b5_strat_open", None)
    if sid in by:
        _b5_section_drawer(by[sid], res["ana"])


# ------------------------------------------------------------------------------
# TAB 3 — ORE (tabella oraria e strike zone del giorno)
# ------------------------------------------------------------------------------
def _b5_zone_runs(rows):
    """Fasce orarie consecutive con la stessa strike zone: [(ora inizio, ora fine, zona)]."""
    runs = []
    for r in rows:
        h = int(_b5_f(r.get("hour"), 0.0))
        zone = str(r.get("depth_zone") or "n/d")
        if runs and runs[-1][2] == zone and runs[-1][1] == h:
            runs[-1][1] = h + 1
        else:
            runs.append([h, h + 1, zone])
    return runs


def _b5_tab_hours(res):
    ana = res["ana"]
    rows = sorted(ana["timeline"], key=lambda r: _b5_f(r.get("hour")))
    best_h = _b5_f(ana["best"].get("hour"), -1.0)
    troph_h = -1.0 if ana["flat"] else _b5_f(ana["troph"].get("hour"), -1.0)

    data = {"Ora": [], "Acqua": [], "O₂": [], "Attività": [], "Trophy": []}
    for r in rows:
        h = _b5_f(r.get("hour"))
        # 👑 resta emoji: le celle di st.dataframe sono testo semplice, ":material/...:" comparirebbe tale e quale
        mark = ("▲" if h == best_h else "") + ("👑" if h == troph_h else "")
        data["Ora"].append(_b5_row_label(r) + (" " + mark if mark else ""))
        data["Acqua"].append(_b5_f(r.get("water_temp_used", r.get("water_temp")), None))
        data["O₂"].append(_b5_do_mg_l(r))
        data["Attività"].append(_b5_f(r.get("catch_rate")))
        data["Trophy"].append(_b5_f(r.get("trophy_rate")))
    order = ["Ora", "Acqua", "O₂", "Attività", "Trophy"]
    # larghezze in px pensate per 393 px (iPhone 15): con entrambi gli indici le colonne stanno in ~360 px
    bar_w = 86
    cc = st.column_config
    config = {
        "Ora": cc.TextColumn("Ora", pinned=True, width=74),
        "Acqua": cc.NumberColumn("Acqua", format="%.1f°", width=56),
        "O₂": cc.NumberColumn("O₂", format="%.1f", width=46),
        "Attività": cc.ProgressColumn("Attività", min_value=0, max_value=100, format="%.0f", width=bar_w,
                                      color=globals().get("B4_COL_BAI", "#0fa874")),
        "Trophy": cc.ProgressColumn("Trophy", min_value=0, max_value=100, format="%.0f", width=bar_w,
                                    color=globals().get("B4_COL_TROPHY", "#9C72DE")),
    }
    st.dataframe(data, hide_index=True, column_order=order, column_config=config, width="stretch",
                 height=35 * (len(rows) + 1) + 3)        # altezza piena: niente secondo scorrimento dentro la pagina
    legend = ["▲ picco Attività", "👑 picco Trophy" if not ana["flat"] else "Trophy senza picco oggi"]
    st.caption(" · ".join(legend + ["acqua in °C e O₂ (ossigeno disciolto) in mg/L, stimati dal modello",
                                    "indici relativi 0-100"]))

    st.markdown("**:material/location_on: Strike zone durante il giorno**")
    st.markdown("\n".join("- **%02d:00–%02d:00** · %s" % (a, b, _b5_mdx(z)) for a, b, z in _b5_zone_runs(rows)))


# ------------------------------------------------------------------------------
# SEZIONI E BARRA IN BASSO
# ------------------------------------------------------------------------------
# Pillola galleggiante in basso con le sezioni (Pesca, Meteo, Diario): componente st.components.v2 che disegna
# la barra fuori dal flusso della pagina (in <body>, position:fixed) e a Python manda solo la sezione toccata
# ("sezione"). Lo stesso componente segue lo scorrimento (l'elemento che scorre è stMain, non la pagina) e, secondo
# B5_TOPBAR_MODE, nasconde la fascia in alto scendendo e la riporta risalendo ("nascondi"), oppure la sostituisce con
# una riga sottile con luogo e giorno e toglie le scritte dalla pillola ("compatta"). Stili con prefisso b5-nav/b5-top.
_B5_NAV_ICONS = {                       # griglia 24, tratto 2, estremità tonde (come _B5_ICONS)
    # pesce di profilo verso destra, coda a sinistra
    "pesca": '<path d="M21.5 12c-2.2 3.4-5.2 5.2-8.6 5.2-2.6 0-4.9-1-6.9-3.1L2.5 17V7L6 9.9C8 7.8 10.3 6.8 12.9 6.8c3.4 '
             '0 6.4 1.8 8.6 5.2z"/><circle cx="16.6" cy="11" r="1.15" fill="currentColor" stroke="none"/>',
    # sole dietro una nuvola
    "meteo": '<path d="M5.2 11.6A4 4 0 0 1 12.4 8.1M8.5 2.6v1.6M3.4 4.7l1.1 1.1M1.6 9.8h1.6M13.6 4.7l-1.1 1.1"/>'
             '<path d="M8 20.5h9.5a3.9 3.9 0 0 0 .5-7.77A5.4 5.4 0 0 0 7.6 13.6a3.45 3.45 0 0 0 .4 6.9z"/>',
    # quaderno con il dorso a sinistra e due righe
    "diario": '<path d="M5.5 5A2 2 0 0 1 7.5 3h11v14.5h-11a2 2 0 0 0-2 2z"/><path d="M5.5 19.5a2 2 0 0 0 2 2h11v-4"/>'
              '<path d="M9.5 7.5h5M9.5 11h5"/>',
}
_B5_NAV_CSS = """
.st-key-b5_nav{position:absolute;width:0;height:0;overflow:hidden}
#b5-nav{position:fixed;left:50%;bottom:calc(14px + env(safe-area-inset-bottom,0px));z-index:999980;display:flex;gap:2px;
  padding:4px;border-radius:999px;transform:translateX(-50%);background:rgba(30,30,34,.9);
  -webkit-backdrop-filter:blur(20px) saturate(180%);backdrop-filter:blur(20px) saturate(180%);
  border:1px solid rgba(242,242,247,.12);box-shadow:0 10px 30px rgba(0,0,0,.55);
  font-family:"Source Sans","Source Sans 3",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
#b5-nav button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;min-width:84px;
  height:52px;margin:0;padding:0 16px;border:0;border-radius:999px;background:transparent;color:rgba(242,242,247,.6);
  font:inherit;font-size:11.5px;font-weight:600;line-height:1.1;cursor:pointer;-webkit-tap-highlight-color:transparent;
  transition:background-color .2s,color .2s,min-width .25s,height .25s}
#b5-nav button svg{flex:none}
#b5-nav button[aria-current="page"]{background:rgba(242,242,247,.12);color:#F2F2F7}
#b5-nav button[aria-current="page"] svg{color:var(--st-primary-color,#0fa874)}
#b5-nav button:focus-visible{outline:2px solid var(--st-primary-color,#0fa874);outline-offset:-2px}
@media (hover:hover){#b5-nav button:hover{color:#F2F2F7}}
.b5-mini #b5-nav button{min-width:60px;height:44px}
.b5-mini #b5-nav button span{display:none}
[data-testid="stHeader"]{transition:transform .28s ease}
.b5-hide [data-testid="stHeader"],.b5-compact [data-testid="stHeader"]{transform:translateY(-100%)}
#b5-top{position:fixed;top:0;left:0;right:0;z-index:999991;height:40px;padding:0 48px;overflow:hidden;
  background:rgba(0,0,0,.84);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);
  border-bottom:1px solid rgba(242,242,247,.1);color:#F2F2F7;
  font:600 15px/40px "Source Sans","Source Sans 3",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  text-align:center;white-space:nowrap;text-overflow:ellipsis;cursor:pointer;transform:translateY(-100%);
  transition:transform .28s ease}
.b5-compact #b5-top{transform:none}
@media (prefers-reduced-motion:reduce){#b5-nav,#b5-nav button,#b5-top,[data-testid="stHeader"]{transition:none}}
"""
_B5_NAV_JS = r"""
const main = () => document.querySelector('[data-testid="stMain"]');

export default function ({ data, setTriggerValue }) {
  const d = data || {};
  const S = window.__b5nav || (window.__b5nav = { y: 0 });
  S.set = setTriggerValue;
  S.mode = d.mode === "compatta" ? "compatta" : "nascondi";
  if (!S.after && d.after) {                   // ritorno da Google dopo Accedi / Esci nel Diario: si riapre il Diario
    S.after = true;
    try {
      const t = Number(window.localStorage.getItem(d.after) || 0);
      if (t) {
        window.localStorage.removeItem(d.after);
        if (Date.now() - t < 600000 && d.active !== "diario") setTriggerValue("sezione", "diario");
      }
    } catch (e) { /* senza localStorage si resta sulla Pesca */ }
  }
  let nav = document.getElementById("b5-nav");
  if (!nav) {                                  // una sola barra per pagina: resta tra un giro e l'altro dell'app
    nav = document.createElement("nav");
    nav.id = "b5-nav";
    nav.setAttribute("aria-label", "Sezioni");
    document.body.appendChild(nav);
    nav.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-id]");
      if (!b || b.getAttribute("aria-current") === "page") return;
      nav.querySelectorAll("button").forEach((x) => x.removeAttribute("aria-current"));
      b.setAttribute("aria-current", "page");
      const m = main();
      if (m) m.scrollTo({ top: 0 });
      S.set("sezione", b.dataset.id);
    });
  }
  nav.replaceChildren(...(d.items || []).map((it) => {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.id = it.id;
    if (it.id === d.active) b.setAttribute("aria-current", "page");
    b.innerHTML = it.icon;                      // SVG disegnato in Python
    const s = document.createElement("span");
    s.textContent = it.label;
    b.appendChild(s);
    return b;
  }));
  let top = document.getElementById("b5-top");
  if (S.mode === "compatta") {
    if (!top) {
      top = document.createElement("div");
      top.id = "b5-top";
      top.setAttribute("role", "button");
      top.setAttribute("aria-label", "Torna in cima");
      document.body.appendChild(top);
      top.addEventListener("click", () => { const m = main(); if (m) m.scrollTo({ top: 0, behavior: "smooth" }); });
    }
    top.textContent = d.title || "";
  } else if (top) {
    top.remove();
  }
  if (!S.onScroll) {                           // lo scroll di stMain non risale fino a document: si ascolta in cattura
    S.onScroll = (e) => {
      const el = e.target;
      if (!el || !el.getAttribute || el.getAttribute("data-testid") !== "stMain") return;
      const y = el.scrollTop, dy = y - S.y;
      S.y = y;
      const c = document.documentElement.classList;
      if (S.mode === "compatta") {
        c.toggle("b5-compact", y > 64);
        c.remove("b5-hide");
        if (y <= 64 || dy < -4) c.remove("b5-mini"); else if (dy > 4) c.add("b5-mini");
      } else {
        c.remove("b5-compact", "b5-mini");
        if (y <= 60 || dy < -4) c.remove("b5-hide"); else if (dy > 4) c.add("b5-hide");
      }
    };
    document.addEventListener("scroll", S.onScroll, { capture: true, passive: true });
  }
}
"""


def _b5_nav_icon(name):
    return _B5_SVG % (24, 24, 24, _B5_NAV_ICONS[name])


def _b5_nav_title():
    """Riga sottile della fascia compatta: luogo · giorno (Pesca) oppure luogo · Meteo."""
    ss = st.session_state
    loc = ss.get("b5_loc") or {}
    name = str(loc.get("name") or "Località")
    if ss.get("b5_section") == "meteo":
        return name + " · Meteo"
    if ss.get("b5_section") == "diario":
        return "Diario"
    when = ss.get("b5_when", "Oggi")
    if when == "Passato":
        today = _b5_today(loc.get("tz"), loc.get("lon"))
        picked = ss.get("b5_past_%s" % today.isoformat())
        when = _b5_fmt_date(picked) if isinstance(picked, _b5_dt.date) else "Passato"
    return "%s · %s" % (name, when)


def _b5_nav():
    """Pillola in basso con le sezioni -> sezione da mostrare in questo giro. Va chiamata prima del contenuto."""
    ss = st.session_state
    ids = [sid for sid, _ in B5_SECTIONS]
    if ss.get("b5_section") not in ids:
        ss["b5_section"] = ids[0]
    try:
        from streamlit.components import v2 as components_v2
        comp = components_v2.component("b5_barra", css=_B5_NAV_CSS, js=_B5_NAV_JS, isolate_styles=False)
        res = comp(key="b5_nav", on_sezione_change=lambda: None, data={
            "items": [{"id": sid, "label": label, "icon": _b5_nav_icon(sid)} for sid, label in B5_SECTIONS],
            "active": ss["b5_section"], "mode": B5_TOPBAR_MODE, "title": _b5_nav_title(),
            "after": B5_AFTER_LOGIN_KEY})
    except Exception:                   # Streamlit senza componenti v2: le sezioni in cima alla pagina
        st.segmented_control("Sezione", ids, format_func=dict(B5_SECTIONS).get, key="b5_section", required=True,
                             width="stretch", label_visibility="collapsed")
        return ss["b5_section"]
    pick = res.get("sezione") if hasattr(res, "get") else None
    if pick in ids and pick != ss["b5_section"]:
        ss["b5_section"] = pick
        st.rerun()                      # la barra riceve subito la sezione nuova come attiva
    return ss["b5_section"]


# ------------------------------------------------------------------------------
# SEZIONE METEO
# ------------------------------------------------------------------------------
# Meteo "da pescatore", non un'app meteo in piccolo: adesso, avvisi (temporali, raffiche), prossime 24 ore, pressione,
# prossimi 7 giorni con l'indice di pesca di Oggi, Domani e Dopodomani (gli stessi giorni della sezione Pesca: oltre,
# la previsione perde affidabilità). Una chiamata alla Forecast API di Open-Meteo, in cache per B5_METEO_TTL_S.
# Codici del tempo: WMO 4677 come li usa Open-Meteo (0 sereno ... 99 temporale con grandine).
_B5_WMO = {
    0: ("Sereno", "sereno"), 1: ("Prevalentemente sereno", "poco"), 2: ("Parzialmente nuvoloso", "poco"),
    3: ("Coperto", "coperto"), 45: ("Nebbia", "nebbia"), 48: ("Nebbia con brina", "nebbia"),
    51: ("Pioggerella debole", "pioggerella"), 53: ("Pioggerella", "pioggerella"),
    55: ("Pioggerella intensa", "pioggerella"), 56: ("Pioggerella gelata", "pioggerella"),
    57: ("Pioggerella gelata intensa", "pioggerella"), 61: ("Pioggia debole", "pioggia"), 63: ("Pioggia", "pioggia"),
    65: ("Pioggia forte", "pioggia"), 66: ("Pioggia gelata", "pioggia"), 67: ("Pioggia gelata forte", "pioggia"),
    71: ("Neve debole", "neve"), 73: ("Neve", "neve"), 75: ("Neve forte", "neve"), 77: ("Granelli di neve", "neve"),
    80: ("Rovesci deboli", "pioggia"), 81: ("Rovesci", "pioggia"), 82: ("Rovesci violenti", "pioggia"),
    85: ("Rovesci di neve", "neve"), 86: ("Rovesci di neve forti", "neve"), 95: ("Temporale", "temporale"),
    96: ("Temporale con grandine", "temporale"), 99: ("Temporale con grandine forte", "temporale"),
}
_B5_THUNDER = (95, 96, 99)
_B5_COMPASS = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
# Simboli del tempo a colori, griglia 32: sole ambra (l'occhio del logo), nuvole grigie, gocce nel blu dell'acqua del
# Blocco 4. Le nuvole davanti a sole e luna hanno un bordo nero (il fondo) che le stacca.
_B5_WX_SUN = ('<g stroke="#E3B04B" stroke-width="2" stroke-linecap="round"><circle cx="%(x)s" cy="%(y)s" r="%(r)s" '
              'fill="#E3B04B" stroke="none"/><path d="%(rays)s"/></g>')
_B5_WX_MOON = '<path d="M%(x0)s %(y0)sA%(r)s %(r)s 0 1 0 %(x1)s %(y1)sA%(r2)s %(r2)s 0 0 1 %(x0)s %(y0)sz" fill="#D9DDE6"/>'
_B5_WX_CLOUD = ('<g transform="translate(%s %s) scale(%s)"><g fill="#000" stroke="#000" stroke-width="%s">%s</g>'
                '<g fill="%s">%s</g></g>')
_B5_WX_CLOUD_PARTS = ('<circle cx="10.5" cy="20.5" r="5"/><circle cx="16.5" cy="15.5" r="7"/>'
                      '<circle cx="23" cy="19.5" r="6"/><rect x="10.5" y="19" width="12.5" height="6.5"/>')
_B5_RAIN = "#2b9fe0"


def _b5_sun_svg(x, y, r):
    rays = []
    for k in range(8):
        a = _b5_math.radians(45 * k)
        c, s = _b5_math.cos(a), _b5_math.sin(a)
        rays.append("M%.1f %.1fL%.1f %.1f" % (x + c * (r + 2.6), y + s * (r + 2.6), x + c * (r + 4.8), y + s * (r + 4.8)))
    return _B5_WX_SUN % {"x": x, "y": y, "r": r, "rays": "".join(rays)}


def _b5_moon_svg(x, y, r):
    """Falce di luna: cerchio di raggio r meno un cerchio spostato in alto a destra."""
    return _B5_WX_MOON % {"x0": round(x + r * 0.42, 2), "y0": round(y - r * 0.91, 2), "x1": round(x + r * 0.95, 2),
                          "y1": round(y + r * 0.32, 2), "r": r, "r2": round(r * 0.8, 2)}


def _b5_cloud_svg(dx=0.0, dy=0.0, scale=1.0, color="#C9CED8", ring=2.4):
    return _B5_WX_CLOUD % (dx, dy, scale, ring / scale, _B5_WX_CLOUD_PARTS, color, _B5_WX_CLOUD_PARTS)


def _b5_wx_body(kind, day):
    """Disegno (griglia 32) per un tipo di tempo; di notte la luna al posto del sole."""
    light = (lambda x, y, r: _b5_sun_svg(x, y, r)) if day else (lambda x, y, r: _b5_moon_svg(x, y, r * 1.15))
    if kind == "sereno":
        return light(16, 16, 6.5)
    if kind == "poco":
        return light(12, 11.5, 4.6) + _b5_cloud_svg(4.5, 5.5, 0.82)
    if kind == "coperto":
        return _b5_cloud_svg(0, 0.5, 1.0, "#B4BAC6")
    if kind == "nebbia":
        return (_b5_cloud_svg(1, -4, 0.92, "#B4BAC6") + '<path d="M5 25.5h16M9 29h18M24.5 25.5h2.5" stroke="#B4BAC6" '
                'stroke-width="2" stroke-linecap="round"/>')
    top = _b5_cloud_svg(0, -4, 1.0, "#9AA1B0")
    if kind == "pioggerella":
        return top + "".join('<circle cx="%s" cy="%s" r="1.3" fill="%s"/>' % (x, y, _B5_RAIN)
                             for x, y in ((11, 26), (17, 28.5), (23, 26)))
    if kind == "pioggia":
        return top + ('<path d="M11.5 24.5l-1.6 4.2M17.5 24.5l-1.6 4.2M23.5 24.5l-1.6 4.2" stroke="%s" stroke-width="2.2" '
                      'stroke-linecap="round"/>' % _B5_RAIN)
    if kind == "neve":
        return top + "".join('<circle cx="%s" cy="%s" r="1.6" fill="#E8EEF6"/>' % (x, y)
                             for x, y in ((11, 25.5), (17, 28.5), (23, 25.5)))
    if kind == "temporale":
        return _b5_cloud_svg(0, -4, 1.0, "#7E8596") + '<path d="M17.5 21l-4.5 6h3.6l-1.6 4.5 5.5-6.5h-3.6l1.6-4z" fill="#E3B04B"/>'
    return _b5_cloud_svg(0, 0.5, 1.0, "#B4BAC6")


def _b5_wx_icon(code, day=True, size=28, title=""):
    """Simbolo del tempo per un codice WMO (sconosciuto: nuvola)."""
    desc, kind = _B5_WMO.get(int(_b5_f(code, 3)), ("", "coperto"))
    label = title or desc
    return ('<svg viewBox="0 0 32 32" width="%d" height="%d" role="img" aria-label="%s">%s</svg>'
            % (size, size, _b5_html.escape(label), _b5_wx_body(kind, day)))


def _b5_wind_arrow(deg, size=14):
    """Freccia verso dove soffia il vento (deg = direzione di provenienza, gradi meteorologici)."""
    rot = (_b5_f(deg, 0.0) + 180.0) % 360.0
    return ('<svg viewBox="0 0 24 24" width="%d" height="%d" fill="none" stroke="currentColor" stroke-width="2.4" '
            'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><g transform="rotate(%.0f 12 12)">'
            '<path d="M12 20V4M6 10l6-6 6 6"/></g></svg>' % (size, size, rot))


def _b5_compass(deg):
    return _B5_COMPASS[int((_b5_f(deg, 0.0) % 360.0 + 22.5) // 45.0) % 8]


@st.cache_data(ttl=B5_METEO_TTL_S, show_spinner=False)
def _b5_meteo_fetch(lat: float, lon: float, tz: str) -> dict:
    """Adesso, ore e giorni dalla Forecast API di Open-Meteo (ieri incluso, per la tendenza della pressione)."""
    resp = requests.get(B5_FORECAST_URL, timeout=15, params={
        "latitude": lat, "longitude": lon, "timezone": tz or "auto", "past_days": 1, "forecast_days": B5_METEO_DAYS,
        "wind_speed_unit": "kmh",
        "current": "temperature_2m,apparent_temperature,is_day,weather_code,pressure_msl,wind_speed_10m,"
                   "wind_direction_10m,wind_gusts_10m",
        "hourly": "temperature_2m,weather_code,precipitation_probability,precipitation,wind_speed_10m,"
                  "wind_direction_10m,wind_gusts_10m,pressure_msl,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
                 "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant",
    })
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("Open-Meteo: %s" % ((data or {}).get("reason") or "risposta non valida"))
    now = _b5_dt.datetime.now(_b5_dt.timezone.utc)
    data["_fetched_utc"] = now.isoformat()
    _b5_stale_save("meteo", (lat, lon, tz), data, now)
    return data


def _b5_cb_meteo_refresh():
    try:
        _b5_meteo_fetch.clear()
    except Exception:
        pass


def _b5_pressure_trend(delta_3h):
    """Tendenza in 3 h: sotto 0.5 hPa stabile; 1.6 e 3.6 hPa sono i limiti delle classi del Met Office."""
    d = _b5_f(delta_3h, 0.0)
    if abs(d) < 0.5:
        return "→", "stabile"
    word = "calo" if d < 0 else "aumento"
    arrow = "↘" if d < 0 else "↗"
    if abs(d) < 1.6:
        return arrow, "in lieve " + word
    return arrow, "in %s rapido" % word if abs(d) >= 3.6 else "in " + word


def _b5_meteo_view(data, today, now_key=None):
    """
    Risposta di Open-Meteo -> dati pronti per la pagina: tutte le ore (da ieri), "next" (48 ore da adesso), giorni da
    oggi con le loro ore, pressione da ieri a dopodomani. `now_key` ("AAAA-MM-GGTHH", ora del luogo) per i dati salvati:
    "adesso" diventa la previsione oraria di quell'ora invece della misura del download.
    """
    cur, hr, dy = data.get("current") or {}, data.get("hourly") or {}, data.get("daily") or {}
    times = [str(t) for t in hr.get("time") or []]
    key = now_key or str(cur.get("time") or "")[:13]
    i0 = next((i for i, t in enumerate(times) if t[:13] == key), None)
    if i0 is None:
        raise ValueError("Ora attuale non trovata nelle previsioni orarie di Open-Meteo.")

    def col(name):
        vals = hr.get(name) or []
        return [vals[i] if i < len(vals) else None for i in range(len(times))]

    h = {k: col(k) for k in ("temperature_2m", "weather_code", "precipitation_probability", "precipitation",
                             "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m", "pressure_msl", "is_day")}
    if now_key:
        cur = {"time": times[i0], "temperature_2m": h["temperature_2m"][i0], "apparent_temperature": None,
               "is_day": h["is_day"][i0], "weather_code": h["weather_code"][i0], "pressure_msl": h["pressure_msl"][i0],
               "wind_speed_10m": h["wind_speed_10m"][i0], "wind_direction_10m": h["wind_direction_10m"][i0],
               "wind_gusts_10m": h["wind_gusts_10m"][i0]}
    hours = [{"t": t, "date": _b5_dt.date.fromisoformat(t[:10]), "hour": int(t[11:13]),
              "temp": h["temperature_2m"][i], "code": h["weather_code"][i], "pop": h["precipitation_probability"][i],
              "rain": h["precipitation"][i], "wind": h["wind_speed_10m"][i], "dir": h["wind_direction_10m"][i],
              "gust": h["wind_gusts_10m"][i], "p": h["pressure_msl"][i], "day": bool(_b5_f(h["is_day"][i], 1))}
             for i, t in enumerate(times)]
    press = [(r["t"], r["p"]) for r in hours[max(0, i0 - 24):i0 + 49] if r["p"] is not None]
    p_now = _b5_f(cur.get("pressure_msl"), _b5_f(hours[i0]["p"], None))
    p_3h = _b5_f(hours[i0 - 3]["p"], None) if i0 >= 3 else None
    p_24 = _b5_f(hours[i0 + 24]["p"], None) if i0 + 24 < len(hours) else None

    days = []
    for k, t in enumerate(str(t) for t in dy.get("time") or []):
        d = _b5_dt.date.fromisoformat(t)
        if d < today or len(days) >= B5_METEO_DAYS:
            continue

        def dv(name):
            vals = dy.get(name) or []
            return vals[k] if k < len(vals) else None
        days.append({"date": d, "off": (d - today).days, "code": dv("weather_code"), "tmax": dv("temperature_2m_max"),
                     "tmin": dv("temperature_2m_min"), "rain": dv("precipitation_sum"),
                     "pop": dv("precipitation_probability_max"), "wind": dv("wind_speed_10m_max"),
                     "gust": dv("wind_gusts_10m_max"), "dir": dv("wind_direction_10m_dominant"),
                     "hours": [r for r in hours if r["date"] == d]})
    return {"now": cur, "time": str(cur.get("time") or ""), "next": hours[i0:i0 + 48], "press": press,
            "p_now": p_now, "p_3h": None if p_now is None or p_3h is None else p_now - p_3h,
            "p_24": None if p_now is None or p_24 is None else p_24 - p_now, "days": days, "today": today,
            "fetched": str(data.get("_fetched_utc") or ""), "tz": str(data.get("timezone") or "")}


def _b5_day_word(d, today):
    return {0: "oggi", 1: "domani", 2: "dopodomani"}.get((d - today).days, _b5_fmt_date(d))


def _b5_hours_span(hs):
    a, b = min(hs), max(hs)
    return "alle %d" % a if a == b else "tra le %d e le %d" % (a, b)


def _b5_meteo_alerts(view):
    """Avvisi delle prossime 48 ore: temporali e raffiche da B5_GUST_WARN_KMH in su. -> [(tipo, frase, consiglio)]."""
    thunder, gusts = {}, {}
    for r in view["next"]:
        if int(_b5_f(r["code"], 0)) in _B5_THUNDER:
            thunder.setdefault(r["date"], []).append(r["hour"])
        if _b5_f(r["gust"], 0.0) >= B5_GUST_WARN_KMH:
            gusts.setdefault(r["date"], []).append((r["hour"], _b5_f(r["gust"], 0.0)))
    out = []
    for d in sorted(thunder):
        out.append(("temporale", "Temporali possibili %s %s." % (_b5_day_word(d, view["today"]), _b5_hours_span(thunder[d])),
                    "Con i fulmini fuori dall'acqua: la canna in carbonio conduce."))
    for d in sorted(gusts):
        peak = max(g for _, g in gusts[d])
        out.append(("raffica", "Raffiche fino a %d km/h %s %s." % (int(round(peak)), _b5_day_word(d, view["today"]),
                                                                   _b5_hours_span([hh for hh, _ in gusts[d]])),
                    "Attenzione in barca e in kayak."))
    return out


def _b5_alerts_html(alerts):
    """Avvisi compatti (bordo e fondo ambra, icona, frase in grassetto e consiglio) invece dei riquadri st.warning."""
    esc = _b5_html.escape
    return '<div class="b5m-alerts" role="note">%s</div>' % "".join(
        '<div class="b5m-alert">%s<p><b>%s</b> %s</p></div>' % (_b5_icon(kind, 18), esc(head), esc(tip))
        for kind, head, tip in alerts)


def _b5_meteo_now(view):
    esc = _b5_html.escape
    cur = view["now"]
    desc = _B5_WMO.get(int(_b5_f(cur.get("weather_code"), 3)), ("—", ""))[0]
    today = view["days"][0] if view["days"] and view["days"][0]["off"] == 0 else {}
    minmax = " · min %d° max %d°" % (round(_b5_f(today.get("tmin"))), round(_b5_f(today.get("tmax")))) if today else ""
    p_arrow, p_word = _b5_pressure_trend(view["p_3h"])
    nxt = view["next"][1:4]
    pop = max([_b5_f(r["pop"], 0.0) for r in nxt] or [0.0])
    mm = sum(_b5_f(r["rain"], 0.0) for r in nxt)
    rain_sub = "%.1f mm in 3 ore" % mm if mm >= 0.1 else "asciutto nelle prossime 3 ore"
    stats = (
        ("Vento", "%s%d <small>km/h</small>" % (_b5_wind_arrow(cur.get("wind_direction_10m"), 15),
                                               round(_b5_f(cur.get("wind_speed_10m")))),
         "da %s · raffiche %d" % (_b5_compass(cur.get("wind_direction_10m")), round(_b5_f(cur.get("wind_gusts_10m"))))),
        ("Pressione", "%d <small>hPa</small>" % round(_b5_f(view["p_now"])),
         "%s %s" % (p_arrow, p_word) + (" (%s in 3 h)" % ("%+.1f" % view["p_3h"]).replace("-", "−")
                                        if view["p_3h"] is not None else "")),
        ("Pioggia", "%d <small>%%</small>" % round(pop), rain_sub),
    )
    st.markdown(
        '<div class="b5m-card"><div class="b5m-cap">Adesso · %s</div><div class="b5m-now">%s<span class="b5m-now-t">%d°'
        '</span><span class="b5m-now-d"><b>%s</b><span>%s</span></span></div><div class="b5m-stats">%s'
        '</div></div>' % (
            esc(view["time"][11:16]), _b5_wx_icon(cur.get("weather_code"), bool(_b5_f(cur.get("is_day"), 1)), 60),
            round(_b5_f(cur.get("temperature_2m"))), esc(desc),
            esc(("Percepita %d°" % round(_b5_f(cur["apparent_temperature"])) if cur.get("apparent_temperature")
                 is not None else "Previsione per quest'ora") + minmax),
            "".join('<div><span class="b5m-lab">%s</span><span class="b5m-val">%s</span>'
                                 '<span class="b5m-sub">%s</span></div>' % (esc(a), b, esc(c)) for a, b, c in stats)),
        unsafe_allow_html=True)


# Giorno per giorno: in testa il titolo del giorno scelto ("Oggi · lunedì 2 novembre", cambia col tocco), sotto la
# striscia dei 7 giorni (tutti visibili, niente scorrimento) e poi i dati del giorno: riquadri, collegamento alla
# sezione Pesca (Oggi, Domani, Dopodomani) e ore in una tabella che scorre di lato, con la pressione
# come linea allineata alle colonne (stessa ora, stessa colonna: niente su e giù tra tabella e grafico). Tutti i giorni
# arrivano al browser insieme: cambiare giorno è istantaneo, senza ricalcolare la pagina. Oggi parte da adesso (24 ore,
# anche la notte e l'alba di domani); gli altri giorni da mezzanotte, con la tabella già scorsa alle 5 (B5_DAY_START_H).
# I simboli del tempo sono <symbol> SVG scritti una volta e richiamati con <use> in ogni ora.
_B5_COL_W = 46              # px di una colonna oraria: la linea della pressione si allinea alle colonne
_B5_LAB_W = 66              # px della colonna ferma con le etichette
_B5_DOW_FULL = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
_B5_MON_FULL = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
                "ottobre", "novembre", "dicembre")
_B5_WEEK_CSS = """
.b5k{display:flex;flex-direction:column;gap:12px}
.b5k-strip{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:2px}
.b5k-tab{display:flex;flex-direction:column;align-items:center;gap:1px;min-width:0;margin:0;padding:8px 0 8px;
  border:1px solid transparent;border-radius:10px;background:transparent;color:rgba(242,242,247,.6);font:inherit;
  font-size:13px;line-height:1.25;font-variant-numeric:tabular-nums;cursor:pointer;-webkit-tap-highlight-color:transparent;
  transition:background-color .15s,border-color .15s}
.b5k-tab[aria-selected="true"]{background:rgba(242,242,247,.1);border-color:rgba(242,242,247,.2)}
.b5k-tab:focus-visible{outline:2px solid var(--st-primary-color,#0fa874);outline-offset:-2px}
@media (hover:hover){.b5k-tab[aria-selected="false"]:hover{background:rgba(242,242,247,.05)}}
.b5k-d,.b5k-max{font-weight:600;color:#F2F2F7}
.b5k-n{font-size:11px}
.b5k-tab svg{margin:3px 0 1px}
.b5k-max{font-size:14px}
.b5k-pop{min-height:15px;font-size:11.5px;line-height:15px;color:#2b9fe0}
.b5k-fv{display:inline-flex;align-items:center;gap:2px;min-height:17px;margin-top:2px;font-size:12.5px;font-weight:600}
.b5k-fv svg,.b5k-legend svg{flex:none}
.b5k-fv.b5k-none{visibility:hidden}
.b5k-legend{display:flex;align-items:center;gap:6px;margin:-4px 0 0;font-size:12.5px;color:rgba(242,242,247,.6)}
.b5k-day{display:flex;flex-direction:column;gap:10px}
.b5k-day[hidden]{display:none}
.b5k-head{display:flex;flex-wrap:wrap;align-items:center;gap:0 8px;margin:0;font-size:17px;line-height:1.3}
.b5k-head svg{flex:none;color:rgba(242,242,247,.6)}
.b5k-head b{font-weight:600}
.b5k-head span{color:rgba(242,242,247,.6);font-size:15px}
.b5k .b5-chips{margin:0}
.b5k .b5-chip.b5k-warn{background:rgba(227,176,75,.16);color:#E3B04B}
.b5k-fish{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:10px;width:100%;margin:0;
  padding:9px 12px;border:1px solid rgba(15,168,116,.45);border-radius:8px;background:rgba(15,168,116,.08);
  color:#F2F2F7;font:inherit;font-size:15px;line-height:1.3;text-align:left;cursor:pointer;
  -webkit-tap-highlight-color:transparent}
.b5k-fish:active{background:rgba(15,168,116,.18)}
.b5k-fish:focus-visible{outline:2px solid var(--st-primary-color,#0fa874);outline-offset:2px}
@media (hover:hover){.b5k-fish:hover{border-color:var(--st-primary-color,#0fa874)}}
.b5k-fish>svg{color:var(--st-primary-color,#0fa874)}
.b5k-fish small{display:block;color:rgba(242,242,247,.6);font-size:13px}
.b5k-go{font-size:22px;line-height:1;color:rgba(242,242,247,.6)}
.b5k-note{margin:0;font-size:13.5px;color:rgba(242,242,247,.6)}
.b5k-scroll{overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;
  -webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 32px),transparent);
  mask-image:linear-gradient(90deg,#000 calc(100% - 32px),transparent)}
.b5k-scroll.b5k-end{-webkit-mask-image:none;mask-image:none}
.b5k-scroll::-webkit-scrollbar{display:none}
.b5k-scroll:focus-visible{outline:2px solid var(--st-primary-color,#0fa874);outline-offset:2px}
table.b5k-hours{table-layout:fixed;border-collapse:separate;border-spacing:0;margin:0;border:0;font-size:14px;
  font-variant-numeric:tabular-nums}
table.b5k-hours th,table.b5k-hours td{border:0;padding:3px 0;text-align:center;white-space:nowrap;background:transparent}
table.b5k-hours th{position:sticky;left:0;z-index:1;padding-right:6px;background:#000;color:rgba(242,242,247,.6);
  font-size:12px;font-weight:400;text-align:left}
table.b5k-hours td.b5k-new{box-shadow:inset 1px 0 rgba(242,242,247,.22)}
.b5k-r-ora td{color:rgba(242,242,247,.6);font-size:13px}
.b5k-r-ora td.b5k-now,.b5k-r-ora td.b5k-new{color:#F2F2F7;font-weight:600}
.b5k-r-ico svg{display:block;margin:0 auto}
.b5k-r-temp td{font-weight:600}
.b5k-wind{display:inline-flex;align-items:center;gap:2px}
.b5k-wind svg{color:rgba(242,242,247,.6)}
.b5k-rain{color:#2b9fe0}
.b5k-dim{color:rgba(242,242,247,.4)}
.b5k-hi{color:#E3B04B;font-weight:600}
table.b5k-hours tr.b5k-r-p td{padding:2px 0 0;text-align:left}
.b5k-r-p svg{display:block;overflow:visible}
.b5k-r-p text{fill:rgba(242,242,247,.6);font-size:11px;font-family:inherit}
.b5k-cap{margin:0;font-size:12.5px;line-height:1.4;color:rgba(242,242,247,.6)}
"""
_B5_WEEK_JS = r"""
export default function ({ data, parentElement, setTriggerValue }) {
  const d = data || {};
  const root = document.createElement("div");
  root.className = "b5k";
  root.innerHTML = d.html || "";                    // HTML costruito in Python, testi già protetti
  parentElement.appendChild(root);
  const tabs = [...root.querySelectorAll(".b5k-tab")], days = [...root.querySelectorAll(".b5k-day")];
  const head = root.querySelector(".b5k-head");
  const S = window.__b5meteo || (window.__b5meteo = {});
  const edge = (sc) => sc.classList.toggle("b5k-end", sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 2);
  const show = (i) => {
    tabs.forEach((t, k) => { t.setAttribute("aria-selected", String(k === i)); t.tabIndex = k === i ? 0 : -1; });
    days.forEach((p, k) => { p.hidden = k !== i; });
    if (head && days[i]) {                        // titolo del giorno scelto, sopra la striscia
      head.querySelector("b").textContent = days[i].dataset.title || "";
      head.querySelector("span").textContent = days[i].dataset.desc || "";
    }
    S[d.key] = i;
    const sc = days[i] && days[i].querySelector(".b5k-scroll");
    if (sc && !sc.dataset.done) {                  // alla prima apertura del giorno: tabella all'ora di partenza
      sc.dataset.done = "1";
      requestAnimationFrame(() => { sc.scrollLeft = Number(sc.dataset.start || 0) * d.colw; edge(sc); });
    }
  };
  root.querySelectorAll(".b5k-scroll").forEach((sc) => sc.addEventListener("scroll", () => edge(sc), { passive: true }));
  root.addEventListener("click", (e) => {
    const t = e.target.closest(".b5k-tab");
    if (t) { show(tabs.indexOf(t)); return; }
    const f = e.target.closest("button[data-off]");
    if (!f) return;
    f.disabled = true;
    const m = document.querySelector('[data-testid="stMain"]');
    if (m) m.scrollTo({ top: 0 });                  // la sezione Pesca si apre dall'inizio
    setTriggerValue("giorno", Number(f.dataset.off));
  });
  root.querySelector(".b5k-strip").addEventListener("keydown", (e) => {
    const i = tabs.indexOf(document.activeElement);
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (i < 0 || !step) return;
    const j = (i + step + tabs.length) % tabs.length;
    show(j);
    tabs[j].focus();
    e.preventDefault();
  });
  show(Math.min(Number(S[d.key]) || 0, days.length - 1));
  return () => root.remove();
}
"""


def _b5_wx_symbols():
    """Simboli del tempo come <symbol> SVG (giorno "g" e notte "n"), una volta per pagina."""
    kinds = sorted({kind for _, kind in _B5_WMO.values()})
    return '<svg width="0" height="0" style="position:absolute" aria-hidden="true">%s</svg>' % "".join(
        '<symbol id="b5wx-%s-%s" viewBox="0 0 32 32">%s</symbol>' % (kind, "g" if day else "n", _b5_wx_body(kind, day))
        for kind in kinds for day in (True, False))


def _b5_wx_use(code, day=True, size=28):
    desc, kind = _B5_WMO.get(int(_b5_f(code, 3)), ("", "coperto"))
    return ('<svg width="%d" height="%d" role="img" aria-label="%s"><use href="#b5wx-%s-%s"/></svg>'
            % (size, size, _b5_html.escape(desc), kind, "g" if day else "n"))


def _b5_press_svg(recs):
    """Linea della pressione alta 40 px, un punto per colonna; il valore ogni 3 ore sopra la linea."""
    pts = [(k, _b5_f(r["p"], None)) for k, r in enumerate(recs)]
    pts = [(k, v) for k, v in pts if v is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(v for _, v in pts), max(v for _, v in pts)
    span = max(hi - lo, 4.0)                        # almeno 4 hPa di scala: pochi decimi restano una linea piatta
    base = (hi + lo) / 2.0 - span / 2.0
    width = len(recs) * _B5_COL_W
    xy = [(k * _B5_COL_W + _B5_COL_W / 2.0, 37.0 - (v - base) / span * 17.0) for k, v in pts]
    line = ('<polyline points="%s" fill="none" stroke="#F2F2F7" stroke-opacity=".85" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round"/>' % " ".join("%.1f,%.1f" % p for p in xy))
    marks = "".join('<circle cx="%.1f" cy="%.1f" r="2.5" fill="#F2F2F7"/><text x="%.1f" y="11" text-anchor="middle">'
                    '%d</text>' % (x, y, x, round(v)) for (k, v), (x, y) in zip(pts, xy) if k % 3 == 0)
    return ('<svg width="%d" height="42" role="img" aria-label="Pressione da %d a %d hPa">%s%s</svg>'
            % (width, round(pts[0][1]), round(pts[-1][1]), line, marks))


def _b5_hours_table(recs, now_first):
    """Tabella delle ore (colonne da _B5_COL_W px): ora, simbolo, temperatura, pioggia, vento, raffiche, pressione."""
    esc = _b5_html.escape
    rows = {k: [] for k in ("ora", "ico", "temp", "pop", "vento", "raffiche")}
    for k, r in enumerate(recs):
        new_day = k > 0 and r["hour"] == 0
        now = k == 0 and now_first
        cls = ' class="b5k-new"' if new_day else (' class="b5k-now"' if now else "")
        label = "Ora" if now else (_B5_DOW[r["date"].weekday()] if new_day else "%02d" % r["hour"])
        pop, gust = r["pop"], _b5_f(r["gust"], 0.0)
        rows["ora"].append("<td%s>%s</td>" % (cls, esc(label)))
        rows["ico"].append("<td%s>%s</td>" % (cls, _b5_wx_use(r["code"], r["day"], 28)))
        rows["temp"].append("<td%s>%d°</td>" % (cls, round(_b5_f(r["temp"]))))
        rows["pop"].append('<td%s><span class="%s">%s</span></td>' % (
            cls, "b5k-rain" if _b5_f(pop, 0.0) >= 20 else "b5k-dim",
            "%d%%" % round(_b5_f(pop)) if pop is not None else "–"))
        rows["vento"].append('<td%s><span class="b5k-wind">%s%d</span></td>' % (
            cls, _b5_wind_arrow(r["dir"], 12), round(_b5_f(r["wind"]))))
        rows["raffiche"].append('<td%s><span class="%s">%d</span></td>' % (
            cls, "b5k-hi" if gust >= B5_GUST_WARN_KMH else "b5k-dim", round(gust)))
    labels = {"ora": "", "ico": "", "temp": "", "pop": "Pioggia", "vento": "Vento", "raffiche": "Raffiche"}
    body = "".join('<tr class="b5k-r-%s"><th scope="row">%s</th>%s</tr>' % (k, labels[k], "".join(v))
                   for k, v in rows.items())
    body += '<tr class="b5k-r-p"><th scope="row">Pressione</th><td colspan="%d">%s</td></tr>' % (
        len(recs), _b5_press_svg(recs))
    return ('<table class="b5k-hours" style="width:%dpx"><colgroup><col style="width:%dpx"><col span="%d" '
            'style="width:%dpx"></colgroup>%s</table>' % (_B5_LAB_W + len(recs) * _B5_COL_W, _B5_LAB_W, len(recs),
                                                          _B5_COL_W, body))


def _b5_day_title(d):
    date = d["date"]
    full = "%s %d %s" % (_B5_DOW_FULL[date.weekday()], date.day, _B5_MON_FULL[date.month - 1])
    when = {0: "Oggi", 1: "Domani", 2: "Dopodomani"}.get(d["off"])
    return ("%s · %s" % (when, full)) if when else full[0].upper() + full[1:]


def _b5_day_panel(d, view, fish, goal):
    """Il giorno scelto: titolo e tempo, riquadri (temperature, pioggia, vento, raffiche), Pesca e tabella delle ore."""
    esc = _b5_html.escape
    off = d["off"]
    desc = _B5_WMO.get(int(_b5_f(d["code"], 3)), ("", ""))[0]
    pop, mm = _b5_f(d["pop"], 0.0), _b5_f(d["rain"], 0.0)
    gust = _b5_f(d["gust"], 0.0)
    chips = [
        _b5_chip(_b5_icon("termometro"), "%d° – %d°" % (round(_b5_f(d["tmin"])), round(_b5_f(d["tmax"]))),
                 "Minima e massima"),
        _b5_chip(_b5_icon("goccia"), ("%d%% · %.1f mm" % (round(pop), mm)) if mm >= 0.1 else "%d%%" % round(pop),
                 "Pioggia: probabilità e quantità"),
        _b5_chip(_b5_wind_arrow(d["dir"], 14), "fino a %d km/h da %s" % (round(_b5_f(d["wind"])), _b5_compass(d["dir"])),
                 "Vento massimo e direzione prevalente"),
        _b5_chip(_b5_icon("raffica"), "raffiche %d km/h" % round(gust), "Raffiche massime").replace(
            'class="b5-chip"', 'class="b5-chip b5k-warn"' if gust >= B5_GUST_WARN_KMH else 'class="b5-chip"', 1),
    ]
    if 0 <= off <= B5_OFFSET_MAX:
        when = {0: "di oggi", 1: "di domani", 2: "di dopodomani"}[off]
        if off in fish:
            v, hh = fish[off]
            line = "%s <b>%s</b> · picco %s" % ("Trophy" if goal == "Trophy" else "Attività", _b5_idx(v), esc(hh))
        else:
            line = "Previsione di pesca"
        bridge = ('<button type="button" class="b5k-fish" data-off="%d">%s<span>%s<small>Apri la previsione di pesca %s'
                  '</small></span><span class="b5k-go" aria-hidden="true">›</span></button>'
                  % (off, _b5_nav_icon("pesca").replace('width="24" height="24"', 'width="22" height="22"'), line, when))
    else:
        bridge = '<p class="b5k-note">La previsione di pesca arriva fino a dopodomani.</p>'
    if off == 0:
        recs, start = view["next"][:24], 0
    else:
        recs = d["hours"]
        start = next((k for k, r in enumerate(recs) if r["hour"] >= B5_DAY_START_H), 0)
    # titolo e tempo non stanno nel pannello ma sopra la striscia (b5k-head): il browser li copia da data-title/desc
    return ('<section class="b5k-day" role="tabpanel" hidden data-title="%s" data-desc="%s">'
            '<div class="b5-chips">%s</div>%s<div class="b5k-scroll" data-start="%d" tabindex="0" role="region" '
            'aria-label="Ore di %s">%s</div></section>'
            % (esc(_b5_day_title(d)), esc(desc), "".join(chips), bridge, start, esc(_b5_day_title(d)),
               _b5_hours_table(recs, off == 0)))


def _b5_fish_mark(size):
    """Il pesce della pillola in piccolo, nel colore del testo intorno."""
    return _B5_SVG % (24, size, size, _B5_NAV_ICONS["pesca"])


def _b5_week_tab(d, fish, color):
    off, date = d["off"], d["date"]
    name = "Oggi" if off == 0 else _B5_DOW[date.weekday()].capitalize()
    pop = _b5_f(d["pop"], 0.0)
    tmin, tmax = round(_b5_f(d["tmin"])), round(_b5_f(d["tmax"]))
    if off in fish:             # indice di pesca col pesciolino: numero e non barretta (a 25/100 era un puntino)
        v = max(0.0, min(100.0, fish[off][0]))
        bar = '<span class="b5k-fv" style="color:%s">%s%s</span>' % (color, _b5_fish_mark(12), _b5_idx(v))
        extra = ", attività di pesca %s" % _b5_idx(v)
    else:
        bar, extra = '<span class="b5k-fv b5k-none">–</span>', ""
    label = "%s: %s, %d°–%d°, pioggia %d%%%s" % (_b5_day_title(d), _B5_WMO.get(int(_b5_f(d["code"], 3)), ("", ""))[0],
                                                  tmin, tmax, round(pop), extra)
    return ('<button type="button" class="b5k-tab" role="tab" aria-selected="false" aria-label="%s">'
            '<span class="b5k-d">%s</span><span class="b5k-n">%d %s</span>%s<span class="b5k-max">%d°</span>'
            '<span class="b5k-min">%d°</span><span class="b5k-pop">%s</span>%s</button>'
            % (_b5_html.escape(label), name, date.day, _B5_MON[date.month - 1], _b5_wx_use(d["code"], True, 28), tmax,
               tmin, "%d%%" % round(pop) if pop >= 20 else "", bar))


def _b5_meteo_week(view, fish, goal):
    """Striscia dei giorni e giorno scelto; un tocco su Pesca (primi tre giorni) apre quella sezione su quel giorno."""
    days = view["days"]
    if not days:
        return
    color = globals().get("B4_COL_TROPHY", "#9C72DE") if goal == "Trophy" else globals().get("B4_COL_BAI", "#0fa874")
    legend = ('<p class="b5k-legend"><span style="color:%s;display:inline-flex">%s</span>%s di pesca prevista · tocca '
              'un giorno per le sue ore</p>' % (color, _b5_fish_mark(13), "Trophy" if goal == "Trophy" else "Attività")
              if fish else '<p class="b5k-legend">Tocca un giorno per le sue ore.</p>')
    first = days[0]
    head = '<p class="b5k-head" aria-live="polite">%s<b>%s</b><span>%s</span></p>' % (
        _b5_icon("data", 18), _b5_html.escape(_b5_day_title(first)),
        _b5_html.escape(_B5_WMO.get(int(_b5_f(first["code"], 3)), ("", ""))[0]))
    html = (_b5_wx_symbols() + head + '<div class="b5k-strip" role="tablist" aria-label="Giorni">%s</div>%s%s'
            '<p class="b5k-cap">Pioggia: probabilità · vento e raffiche in km/h, la freccia indica dove soffia · '
            'pressione in hPa</p>' % ("".join(_b5_week_tab(d, fish, color) for d in days), legend,
                                      "".join(_b5_day_panel(d, view, fish, goal) for d in days)))
    key = "%s|%s" % (view["today"].isoformat(), view["tz"])
    try:
        from streamlit.components import v2 as components_v2
        comp = components_v2.component("b5_settimana", css=_B5_WEEK_CSS, js=_B5_WEEK_JS, isolate_styles=False)
        res = comp(key="b5_week", data={"html": html, "key": key, "colw": _B5_COL_W}, on_giorno_change=lambda: None)
    except Exception:                   # Streamlit senza componenti v2: solo oggi, senza tocchi
        st.markdown("<style>%s</style>%s" % (_B5_WEEK_CSS, html.replace(" hidden>", ">", 1)), unsafe_allow_html=True)
        return
    off = res.get("giorno") if hasattr(res, "get") else None
    if isinstance(off, (int, float)) and 0 <= int(off) <= B5_OFFSET_MAX:
        st.session_state["b5_when"] = B5_WHEN_OPTIONS[int(off)]
        st.session_state["b5_section"] = "pesca"
        st.rerun()


def _b5_meteo_pressure(view):
    """Pressione da ieri a dopodomani (72 h) con la linea di adesso: i fronti si vedono come cali e risalite."""
    pts = view["press"]
    if len(pts) < 6 or not view["next"]:
        return
    try:
        import plotly.graph_objects as go_
    except Exception:
        return
    x = [t for t, _ in pts]
    y = [_b5_f(p) for _, p in pts]
    now_t = view["next"][0]["t"]
    lo, hi = min(y), max(y)
    if hi - lo < 10.0:                 # almeno 10 hPa di scala: pochi decimi non devono sembrare un crollo
        mid = (hi + lo) / 2.0
        lo, hi = mid - 5.0, mid + 5.0
    ink = globals().get("B4_INK_1", "#F2F2F7")
    ink3 = globals().get("B4_INK_3", "#79797C")
    grid = globals().get("B4_GRID", "rgba(242,242,247,0.10)")
    font = globals().get("B4_FONT", "sans-serif")
    ui = globals().get("B4_UI") or {}
    labels = ["%s %s" % (_b5_fmt_date(_b5_dt.date.fromisoformat(t[:10])), t[11:16]) for t in x]
    past = [i for i, t in enumerate(x) if t <= now_t]
    if not past:
        return
    midnights = [t for t in x if t[11:13] == "00"]
    fig = go_.Figure()
    fig.add_trace(go_.Scatter(x=x[:len(past)], y=y[:len(past)], mode="lines", line=dict(color=ink3, width=2),
                              customdata=labels[:len(past)], hovertemplate="%{customdata}<br><b>%{y:.0f} hPa</b><extra></extra>"))
    fig.add_trace(go_.Scatter(x=x[len(past) - 1:], y=y[len(past) - 1:], mode="lines", line=dict(color=ink, width=2),
                              customdata=labels[len(past) - 1:],
                              hovertemplate="%{customdata}<br><b>%{y:.0f} hPa</b><extra></extra>"))
    fig.add_trace(go_.Scatter(x=[now_t], y=[_b5_f(view["p_now"], y[len(past) - 1])], mode="markers", hoverinfo="skip",
                              marker=dict(size=9, color=ink, line=dict(color=ui.get("surface", "#000000"), width=2))))
    fig.update_layout(
        template="plotly_dark", height=150, margin=dict(l=40, r=10, t=18, b=26), showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=ui.get("panel", "rgba(242,242,247,0.03)"), dragmode=False,
        font=dict(family=font, size=12, color=ink), hovermode="closest", hoverdistance=-1,
        hoverlabel=dict(bgcolor=ui.get("overlay_solid", "#2C2C2E"), bordercolor=ui.get("overlay_border", grid),
                        font=dict(size=12, color=ink, family=font)),
        xaxis=dict(type="date", range=[x[0], x[-1]], tickvals=midnights,
                   ticktext=[_b5_fmt_date(_b5_dt.date.fromisoformat(t[:10])) for t in midnights],
                   tickfont=dict(size=11, color=ink3), showgrid=True, gridcolor=grid, zeroline=False, fixedrange=True),
        yaxis=dict(range=[lo - 1.0, hi + 1.0], nticks=4, tickfont=dict(size=11, color=ink3), gridcolor=grid,
                   zeroline=False, fixedrange=True),
        shapes=[dict(type="line", xref="x", yref="paper", x0=now_t, x1=now_t, y0=0, y1=1,
                     line=dict(color=ink3, width=1, dash="dot"))],
        annotations=[dict(x=now_t, y=1, xref="x", yref="paper", yanchor="bottom", text="adesso", showarrow=False,
                          font=dict(size=11, color=ink3))])
    _b5_plotly(fig, "b5m_press")


def _b5_pressure_text(view):
    """Per il titolo del cassetto della pressione (una riga al telefono): "−5 hPa in 24 h", "+3 hPa in 24 h", "stabile"."""
    d = view["p_24"]
    if d is None:
        return ""
    if abs(d) < 1.0:
        return "stabile"
    return "%s%d hPa in 24 h" % ("−" if d < 0 else "+", round(abs(d)))


def _b5_fish_days(goal):
    """Indice di pesca dell'ora migliore per Oggi, Domani e Dopodomani con le impostazioni in uso -> {offset: (v, ora)}."""
    out = {}
    trophy = goal == "Trophy"
    for off in range(0, B5_OFFSET_MAX + 1):
        try:
            res = _b5_run(_b5_ctl(off), goal)
        except Exception:
            continue
        if res.get("error"):
            continue
        ana = res["ana"]
        rec = ana["troph"] if trophy and not ana["flat"] else ana["best"]
        out[off] = (_b5_f(rec.get("trophy_rate" if trophy else "catch_rate")), _b5_row_label(rec))
    return out


def _b5_meteo_footer(view, loc):
    url = "https://www.windy.com/?%.3f,%.3f,10" % (_b5_f(loc.get("lat"), 43.13), _b5_f(loc.get("lon"), 12.10))
    with st.container(horizontal=True, gap="small"):
        st.link_button(":material/open_in_new: Mappe su Windy", url, width="stretch")
        st.button(":material/refresh: Aggiorna", key="b5m_refresh", on_click=_b5_cb_meteo_refresh, width="stretch")
    parts = []
    try:
        utc = _b5_dt.datetime.fromisoformat(view.get("fetched"))
        zi = _b5_zone(view.get("tz") or loc.get("tz"))
        local = utc.astimezone(zi) if zi is not None else utc
        parts.append("Meteo scaricato alle %02d:%02d" % (local.hour, local.minute))
    except Exception:
        pass
    parts += ["previsioni Open-Meteo", "gli avvisi non sostituiscono quelli della Protezione Civile"]
    st.caption(" · ".join(parts), text_alignment="center")


def _b5_page_meteo():
    """Sezione Meteo: intestazione con il luogo, adesso, avvisi, giorno per giorno, pressione su 3 giorni."""
    ss = st.session_state
    loc = ss["b5_loc"]
    ctl = _b5_ctl(0)
    header = st.container()
    view, err, stale = None, None, None
    key = (round(ctl["lat"], 4), round(ctl["lon"], 4), ctl["tz"])
    try:
        with st.spinner("Scarico il meteo…"):
            data = _b5_meteo_fetch(*key)
        view = _b5_meteo_view(data, ctl["today"])
    except Exception as exc:
        err = exc
        old = _b5_stale_load("meteo", key)
        zi = _b5_zone(ctl["tz"])
        if old is not None and zi is not None:      # ultimi dati salvati: "adesso" = previsione per l'ora attuale
            try:
                view = _b5_meteo_view(old[0], ctl["today"], _b5_dt.datetime.now(zi).strftime("%Y-%m-%dT%H"))
                stale = old[1].astimezone(zi)
            except Exception:
                view = None
    try:
        astro = _b5_compute_astro(ctl["today"], ctl["lat"], ctl["lon"], ctl["tz"])
    except Exception:
        astro = None
    with header:
        _b5_render_header(ctl, ctl["today"], astro, meteo=True)
    _b5_open_drawer()
    if view is None:
        st.error("Open-Meteo non ha risposto. Riprova tra poco.", title="Meteo non disponibile",
                 icon=":material/warning:")
        st.button(":material/refresh: Riprova", key="b5m_retry", on_click=_b5_cb_meteo_refresh, width="stretch")
        with st.expander("Dettagli tecnici"):
            st.text(_b5_short_exc(err, 600))
        return

    if stale is not None:
        day = "" if stale.date() == ctl["today"] else " di %s" % _b5_fmt_date(stale.date())
        st.warning("Open-Meteo non risponde: mostro le previsioni scaricate alle %02d:%02d%s. Riprova più tardi con "
                   "«Aggiorna»." % (stale.hour, stale.minute, day), icon=":material/cloud_off:")
    _b5_meteo_now(view)
    alerts = _b5_meteo_alerts(view)
    if alerts:
        st.markdown(_b5_alerts_html(alerts), unsafe_allow_html=True)
    else:
        st.caption(":material/check_circle: Nessun temporale né raffiche forti nelle prossime 48 ore.")

    goal = ss.get("b5_goal", B5_GOALS[0])
    with st.spinner("Calcolo l'attività dei prossimi giorni…"):
        fish = _b5_fish_days(goal)
    _b5_meteo_week(view, fish, goal)
    trend = _b5_pressure_text(view)
    with st.expander(":material/compress: Pressione su 3 giorni" + (" · " + trend if trend else "")):
        st.caption("Da ieri a dopodomani. I cali e le risalite segnano il passaggio dei fronti.")
        _b5_meteo_pressure(view)
    _b5_meteo_footer(view, loc)


# ------------------------------------------------------------------------------
# SEZIONE DIARIO
# ------------------------------------------------------------------------------
# Diario delle uscite, non solo delle catture: ogni uscita (anche il cappotto) con luogo, orario, catture, acqua
# misurata e le condizioni e la previsione di quel giorno, salvate dall'app. "Come va la previsione" confronta, dentro
# ogni uscita conclusa, le catture all'ora nelle ore che il modello dava migliori (ore forti) e nelle altre: ogni
# uscita fa da confronto a sé stessa (stesso lago, stesso giorno, stesso pescatore). Senza accesso il diario sta nel
# browser di chi lo usa (localStorage), non sul server: Streamlit Cloud cancella i file a ogni riavvio. Con l'accesso
# (Google, st.login) sta nel database (Cloud Firestore), legato all'account. Copia di sicurezza in JSON.
#
# Un'uscita: {"id", "luogo": {name, admin, country, lat, lon, tz}, "data": "AAAA-MM-GG", "inizio": "HH:MM",
# "fine": "HH:MM" o None (in corso), "catture": [{"id", "ora", "kg", "cm", "esca", "nota"}], "acqua": °C misurati o
# None, "nota", "prev": previsione salvata (_b5_trip_forecast) o None, "creata", "mod"}.

# Ponte con il browser (componente invisibile): al primo giro della sessione il browser manda a Python il diario
# salvato ("caricato"); dopo ogni modifica Python manda il diario intero finché il browser non conferma di averlo
# scritto ("salvato"). "rev" cresce a ogni modifica: se nel browser c'è un numero uguale o più alto, il diario è stato
# cambiato in un'altra scheda e il browser lo rimanda indietro per unirlo (err "altrove") invece di sovrascriverlo.
# Prima di accedere o uscire dall'account il browser segna l'ora (d.after): dopo il giro da Google l'app riparte da
# capo e la pillola (_B5_NAV_JS) riapre il Diario invece della Pesca.
_B5_STORE_CSS = ".st-key-b5_store{position:absolute;width:0;height:0;overflow:hidden}"
_B5_STORE_JS = r"""
export default function ({ data, setTriggerValue }) {
  const d = data || {};
  let S = window.__b5store;
  if (!S || S.session !== d.session) S = window.__b5store = { session: d.session, sent: false, written: -1, go: 0 };
  const err = (e) => String((e && e.name) || e);
  if (d.goto && d.goto.n > S.go) {
    S.go = d.goto.n;
    try { window.localStorage.setItem(d.after, String(Date.now())); } catch (e) { /* si torna alla Pesca */ }
    setTriggerValue("via", d.goto.act);
    return;
  }
  if (!d.loaded) {
    if (S.sent) return;
    S.sent = true;
    let out;
    try {
      out = { ok: true, raw: window.localStorage.getItem(d.key) || "" };
      if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    } catch (e) {
      out = { ok: false, raw: "", err: err(e) };
    }
    setTriggerValue("caricato", out);
    return;
  }
  const save = d.save;
  if (!save || save.rev <= S.written) return;
  S.written = save.rev;
  let out;
  try {
    const old = window.localStorage.getItem(d.key);
    let rev = -1;
    try { rev = old ? Number(JSON.parse(old).rev) : -1; } catch (e) { rev = -1; }
    if (rev >= save.rev) {
      out = { rev: save.rev, ok: false, err: "altrove", raw: old };
    } else {
      window.localStorage.setItem(d.key, save.json);
      out = { rev: save.rev, ok: true };
    }
  } catch (e) {
    out = { rev: save.rev, ok: false, err: err(e) };
  }
  setTriggerValue("salvato", out);
}
"""
_B5_RE_HHMM = _b5_re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _b5_utc_iso():
    return _b5_dt.datetime.now(_b5_dt.timezone.utc).replace(microsecond=0).isoformat()


def _b5_new_id():
    return _b5_os.urandom(6).hex()


def _b5_now_at(loc):
    """Data e ora attuali nel fuso del luogo (datetime senza fuso)."""
    now = _b5_dt.datetime.now(_b5_dt.timezone.utc)
    zi = _b5_zone(loc.get("tz"))
    if zi is not None:
        try:
            return now.astimezone(zi).replace(tzinfo=None)
        except Exception:
            pass
    off = _b5_fallback_offset(loc.get("tz"), loc.get("lon"), now.date())
    return (now + _b5_dt.timedelta(hours=off)).replace(tzinfo=None)


def _b5_min(hhmm):
    """'07:30' -> 450 (minuti dalla mezzanotte)."""
    h, m = str(hhmm).split(":")
    return int(h) * 60 + int(m)


def _b5_it(value, nd=1):
    """Numero con la virgola: 1.25 -> '1,3' (nd=1)."""
    return ("%.*f" % (nd, _b5_f(value))).replace(".", ",")


def _b5_dur(minutes):
    """Durata: 45 -> 45′, 180 -> 3 h, 210 -> 3 h 30′."""
    h, m = divmod(max(0, int(round(minutes))), 60)
    if not h:
        return "%d′" % m
    return "%d h" % h + (" %02d′" % m if m else "")


def _b5_count(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


def _b5_catch_clean(c):
    if not isinstance(c, dict) or not _B5_RE_HHMM.match(str(c.get("ora") or "")):
        return None
    kg, cm = _b5_f(c.get("kg"), None), _b5_f(c.get("cm"), None)
    return {"id": str(c.get("id") or _b5_new_id())[:24], "ora": str(c["ora"]),
            "kg": round(kg, 2) if kg is not None and 0 < kg <= 15 else None,
            "cm": round(cm, 1) if cm is not None and 0 < cm <= 100 else None,
            "esca": " ".join(str(c.get("esca") or "").split())[:60], "nota": str(c.get("nota") or "")[:300]}


def _b5_trip_clean(t):
    """Uscita letta dal browser o da un file -> dict con i campi attesi, oppure None se manca l'essenziale."""
    if not isinstance(t, dict) or not t.get("id") or not _B5_RE_HHMM.match(str(t.get("inizio") or "")):
        return None
    try:
        day = _b5_dt.date.fromisoformat(str(t.get("data")))
    except ValueError:
        return None
    loc = t.get("luogo") if isinstance(t.get("luogo"), dict) else {}
    end = t.get("fine") if _B5_RE_HHMM.match(str(t.get("fine") or "")) else None
    prev = t.get("prev")
    ore = prev.get("ore") if isinstance(prev, dict) else None
    if not (isinstance(ore, dict) and isinstance(ore.get("att"), list) and len(ore["att"]) == 24):
        prev = None
    return {
        "id": str(t["id"])[:24],
        "luogo": {"name": str(loc.get("name") or "Lago")[:80], "admin": str(loc.get("admin") or "")[:80],
                  "country": str(loc.get("country") or "")[:40], "lat": _b5_f(loc.get("lat"), 43.13),
                  "lon": _b5_f(loc.get("lon"), 12.10), "tz": str(loc.get("tz") or "")[:40]},
        "data": day.isoformat(), "inizio": str(t["inizio"]), "fine": end,
        "catture": sorted((c for c in map(_b5_catch_clean, t.get("catture") or []) if c), key=lambda c: c["ora"]),
        "acqua": _b5_f(t.get("acqua"), None), "nota": str(t.get("nota") or "")[:1000], "prev": prev,
        "creata": str(t.get("creata") or ""), "mod": str(t.get("mod") or ""),
    }


def _b5_diary_parse(raw):
    """Testo JSON del diario -> (rev, uscite valide). Testo vuoto o rovinato: (0, [])."""
    try:
        obj = _b5_json.loads(raw) if raw else {}
    except ValueError:
        obj = {}
    if isinstance(obj, list):                       # elenco di uscite senza involucro
        obj = {"uscite": obj}
    if not isinstance(obj, dict):
        return 0, []
    trips, seen = [], set()
    for t in map(_b5_trip_clean, obj.get("uscite") or []):
        if t and t["id"] not in seen:
            seen.add(t["id"])
            trips.append(t)
    return max(0, int(_b5_f(obj.get("rev"), 0))), trips


def _b5_diary_json(diary):
    return _b5_json.dumps({"app": "Bassometro", "v": 1, "rev": diary["rev"], "uscite": diary["uscite"]},
                          ensure_ascii=False, separators=(",", ":"))


def _b5_diary_merge(mine, other):
    """Unione per uscita: a parità di id resta quella modificata per ultima."""
    out = {t["id"]: t for t in mine}
    for t in other:
        if t["id"] not in out or t["mod"] > out[t["id"]]["mod"]:
            out[t["id"]] = t
    return list(out.values())


def _b5_diary_pending():
    """True se il diario del browser ha una modifica non ancora scritta (il ponte va disegnato anche fuori dal Diario)."""
    ss = st.session_state
    return isinstance(ss.get("b5_local"), dict) and ss["b5_local"]["rev"] != ss.get("b5_local_acked")


def _b5_diary_store():
    """
    Ponte con il browser (componente qui sopra) e scelta del diario da mostrare: con l'accesso quello del database,
    altrimenti quello del browser (ss["b5_local"], lo stesso oggetto di ss["b5_diary"]). Va disegnato nella sezione
    Diario e finché c'è una modifica da scrivere; senza componenti v2 il diario del browser vale solo per la sessione.
    """
    ss = st.session_state
    ss.setdefault("b5_store_token", _b5_new_id())
    local = ss.get("b5_local")
    loaded = isinstance(local, dict)
    data = {"key": B5_DIARY_STORE_KEY, "session": ss["b5_store_token"], "loaded": loaded, "after": B5_AFTER_LOGIN_KEY}
    if loaded and local["rev"] != ss.get("b5_local_acked"):
        data["save"] = {"rev": local["rev"], "json": _b5_diary_json(local)}
    go = ss.get("b5_go")
    if go:
        data["goto"] = {"n": go[1], "act": go[0]}
    try:
        from streamlit.components import v2 as components_v2
        comp = components_v2.component("b5_archivio", css=_B5_STORE_CSS, js=_B5_STORE_JS, isolate_styles=False)
        res = comp(key="b5_store", data=data, on_caricato_change=lambda: None, on_salvato_change=lambda: None,
                   on_via_change=lambda: None)
    except Exception:
        res = {}
        if not loaded:
            ss["b5_local"], ss["b5_local_acked"], ss["b5_diary_warn"] = {"rev": 0, "uscite": []}, 0, "browser"
        if go:                                      # senza ponte si va da Google senza il segno per il ritorno
            res = {"via": go[0]}
    got = res.get("caricato") if hasattr(res, "get") else None
    if not loaded and isinstance(got, dict):
        rev, trips = _b5_diary_parse(got.get("raw"))
        ss["b5_local"], ss["b5_local_acked"] = {"rev": rev, "uscite": trips}, rev
        if not got.get("ok"):
            ss["b5_diary_warn"] = "browser"
    ack = res.get("salvato") if hasattr(res, "get") else None
    if loaded and isinstance(ack, dict) and ack.get("rev") == local["rev"]:
        if ack.get("ok"):
            ss["b5_local_acked"] = local["rev"]
        elif ack.get("err") == "altrove":           # cambiato in un'altra scheda: si uniscono le due versioni
            rev, trips = _b5_diary_parse(ack.get("raw"))
            local["uscite"] = _b5_diary_merge(local["uscite"], trips)
            local["rev"] = max(rev, local["rev"]) + 1
            st.rerun()
        else:
            ss["b5_local_acked"] = local["rev"]
            ss["b5_diary_warn"] = "spazio" if "Quota" in str(ack.get("err")) else "browser"
    via = res.get("via") if hasattr(res, "get") else None
    if go and via == go[0]:
        ss.pop("b5_go", None)
        if via == "login":
            st.login()
        else:
            st.logout()
        return
    user = _b5_user()
    if user:
        _b5_cloud_sync(user)
    elif isinstance(ss.get("b5_local"), dict):
        ss["b5_diary"], ss["b5_diary_src"] = ss["b5_local"], "browser"


def _b5_diary_trips():
    return st.session_state["b5_diary"]["uscite"]


def _b5_trip_get(tid):
    return next((t for t in _b5_diary_trips() if t["id"] == tid), None)


def _b5_diary_put(trip=None, delete_id=None, many=()):
    """
    Salva (o toglie) un'uscita, oppure ne salva molte (`many`, da una copia di sicurezza o dal browser). Nel browser il
    diario cambia numero di versione e il ponte lo scrive; con l'accesso le modifiche vanno subito al database (se non
    ci riesce restano in attesa e si riprova alla modifica successiva).
    """
    ss = st.session_state
    diary = ss["b5_diary"]
    now = _b5_utc_iso()
    saved = [trip] if trip else list(many)
    for t in saved:
        t["mod"] = t.get("mod") if many else now
    drop = {delete_id} | {t["id"] for t in saved}
    diary["uscite"] = [t for t in diary["uscite"] if t["id"] not in drop] + saved
    diary["rev"] += 1
    if ss.get("b5_diary_src") not in (None, "browser"):
        todo = ss.setdefault("b5_cloud_todo", {})
        for t in saved:
            todo[t["id"]] = t
        if delete_id:
            todo[delete_id] = None
        _b5_cloud_flush()


# ---- account e database ---------------------------------------------------------------------------------------------
# Facoltativi: accesso con Google (st.login, sezione [auth] dei secrets) e uscite in Cloud Firestore (sezione
# [firestore]: la chiave JSON del service account in "chiave"). Il database si usa solo da qui, con la chiave segreta
# del server: le regole di Firestore restano chiuse a tutti. Un documento per uscita, utenti/{uid}/uscite/{id}, con
# l'uscita in JSON ("dati"); in utenti/{uid} email, nome e ultimo accesso. uid = "g" + identificativo Google (sub).
def _b5_secret(section):
    """Sezione dei secrets come dict, oppure None se manca (o se i secrets non ci sono)."""
    try:
        sec = st.secrets.get(section)
    except Exception:
        return None
    return dict(sec) if sec else None


def _b5_cloud_ready():
    """True se accesso e database sono configurati e i pacchetti ci sono (Authlib per st.login, google-auth)."""
    if not (hasattr(st, "login") and _b5_secret("auth") and _b5_secret("firestore")):
        return False
    try:
        import authlib  # noqa: F401
        import google.auth  # noqa: F401
    except ImportError:
        return False
    return True


def _b5_user():
    """Chi ha fatto l'accesso: {"uid", "email", "nome"}; None senza accesso o senza account configurati."""
    if not _b5_cloud_ready():
        return None
    try:
        user = st.user
        if not user.get("is_logged_in"):
            return None
        sub = _b5_re.sub(r"[^0-9A-Za-z_-]", "", str(user.get("sub") or ""))[:60]
    except Exception:
        return None
    if not sub:
        return None
    return {"uid": "g" + sub, "email": str(user.get("email") or ""), "nome": str(user.get("name") or "")}


@st.cache_resource(show_spinner=False)
def _b5_db_session():
    """Sessione HTTP autorizzata con la chiave del service account (il gettone si rinnova da solo) e id del progetto."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account
    sec = _b5_secret("firestore") or {}
    info = _b5_json.loads(sec["chiave"]) if "chiave" in sec else sec
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/datastore"])
    return AuthorizedSession(creds), str(info["project_id"])


def _b5_db_name(project, *path):
    return "projects/%s/databases/(default)/documents/%s" % (project, "/".join(path))


def _b5_db_call(method, path, **kw):
    sess, _ = _b5_db_session()
    r = sess.request(method, B5_FIRESTORE_URL + path, timeout=15, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def _b5_db_load(uid):
    """Uscite dell'account (tutte le pagine dell'elenco)."""
    _, project = _b5_db_session()
    trips, token = [], None
    while True:
        params = {"pageSize": 300}
        if token:
            params["pageToken"] = token
        got = _b5_db_call("GET", _b5_db_name(project, "utenti", uid, "uscite"), params=params)
        for doc in got.get("documents") or []:
            raw = ((doc.get("fields") or {}).get("dati") or {}).get("stringValue")
            try:
                trip = _b5_trip_clean(_b5_json.loads(raw))
            except (TypeError, ValueError):
                trip = None
            if trip:
                trips.append(trip)
        token = got.get("nextPageToken")
        if not token:
            return trips


def _b5_db_commit(uid, save=(), delete=(), profile=None):
    """Scritture in blocchi da 500 (commit di Firestore: ogni blocco riesce o fallisce per intero)."""
    _, project = _b5_db_session()
    stamp = _b5_dt.datetime.now(_b5_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    writes = [{"update": {"name": _b5_db_name(project, "utenti", uid, "uscite", t["id"]), "fields": {
        "dati": {"stringValue": _b5_json.dumps(t, ensure_ascii=False, separators=(",", ":"))},
        "data": {"stringValue": t["data"]}, "modificata": {"timestampValue": stamp}}}} for t in save]
    writes += [{"delete": _b5_db_name(project, "utenti", uid, "uscite", tid)} for tid in delete]
    if profile is not None:
        writes.append({"update": {"name": _b5_db_name(project, "utenti", uid), "fields": {
            "email": {"stringValue": profile.get("email", "")}, "nome": {"stringValue": profile.get("nome", "")},
            "ultimo_accesso": {"timestampValue": stamp}}}} if profile else {"delete": _b5_db_name(project, "utenti", uid)})
    for k in range(0, len(writes), 500):
        _b5_db_call("POST", "projects/%s/databases/(default)/documents:commit" % project, json={"writes": writes[k:k + 500]})


def _b5_cloud_flush():
    """Manda al database le modifiche in attesa; False se non ci riesce (restano in attesa)."""
    ss = st.session_state
    todo, user = ss.get("b5_cloud_todo") or {}, _b5_user()
    if not todo or not user:
        return True
    try:
        _b5_db_commit(user["uid"], save=[t for t in todo.values() if t],
                      delete=[tid for tid, t in todo.items() if t is None])
    except Exception as exc:
        ss["b5_cloud_err"] = _b5_short_exc(exc)
        return False
    ss["b5_cloud_todo"] = {}
    ss.pop("b5_cloud_err", None)
    return True


def _b5_cloud_sync(user):
    """Diario dell'account in ss["b5_diary"]: riletto dal database entrando nel Diario dopo B5_DIARY_RELOAD_S secondi,
    non prima di aver mandato le modifiche in attesa. Al primo accesso della sessione aggiorna il profilo."""
    ss = st.session_state
    mine = ss.get("b5_diary_src") == user["uid"] and isinstance(ss.get("b5_diary"), dict)
    if mine and (_b5_time.time() - ss.get("b5_cloud_t", 0.0) < B5_DIARY_RELOAD_S or not _b5_cloud_flush()):
        return
    try:
        trips = _b5_db_load(user["uid"])
        if ss.get("b5_cloud_profile") != user["uid"]:
            _b5_db_commit(user["uid"], profile=user)
            ss["b5_cloud_profile"] = user["uid"]
    except Exception as exc:
        ss["b5_cloud_err"] = _b5_short_exc(exc)
        if not mine:
            ss["b5_diary"], ss["b5_diary_src"] = None, user["uid"]
        return
    ss["b5_diary"] = {"rev": 0, "uscite": trips}
    ss["b5_diary_src"], ss["b5_cloud_t"] = user["uid"], _b5_time.time()
    ss.pop("b5_cloud_err", None)


def _b5_cb_go(act):
    """Accedi / Esci: prima il browser segna di riaprire il Diario al ritorno (ponte), poi st.login / st.logout."""
    ss = st.session_state
    ss["b5_go"] = (act, int(ss.get("b5_go_n", 0)) + 1)
    ss["b5_go_n"] = ss["b5_go"][1]


def _b5_trip_place(loc):
    """Luogo dell'uscita: coordinate a 3 decimali (circa 100 m), abbastanza per il meteo e non per lo spot preciso."""
    return {"name": str(loc.get("name") or "Lago"), "admin": str(loc.get("admin") or ""),
            "country": str(loc.get("country") or ""), "lat": round(_b5_f(loc.get("lat"), 43.13), 3),
            "lon": round(_b5_f(loc.get("lon"), 12.10), 3), "tz": str(loc.get("tz") or "")}


# ---- previsione salvata con l'uscita --------------------------------------------------------------------------------
def _b5_trip_ctl(trip):
    """Controlli per la previsione del giorno dell'uscita nel suo luogo; impostazioni dello spot quelle già salvate con
    l'uscita, altrimenti quelle in uso. None se la data è fuori dai giorni che il modello calcola."""
    loc = trip["luogo"]
    today = _b5_today(loc.get("tz"), loc.get("lon"))
    day = _b5_dt.date.fromisoformat(trip["data"])
    off = (day - today).days
    if not B5_OFFSET_MIN <= off <= B5_OFFSET_MAX:
        return None
    ctl = _b5_ctl(0)
    ctl.update({"loc": loc, "lat": _b5_f(loc.get("lat")), "lon": _b5_f(loc.get("lon")), "tz": loc.get("tz") or "",
                "today": today, "day_offset": off, "target_date": day})
    imp = (trip.get("prev") or {}).get("imp") or {}
    for key, name, ok in (("spot", "spot", _b5_spot_keys()), ("water_level", "livello", B5_WATER_LEVELS),
                          ("forage_base", "prede", B5_FORAGE_BASES), ("fishing_pressure", "pressione", B5_PRESSURES),
                          ("turbidity", "torbidita", B5_TURBIDITIES)):
        if imp.get(name) in ok:
            ctl[key] = imp[name]
    if "sonda" in imp:
        ctl["probe"] = _b5_f(imp["sonda"], None)
    return ctl


def _b5_trip_forecast(ctl, before):
    """
    Previsione e condizioni del giorno, ora per ora, da salvare con l'uscita (Blocchi 1-2 con le impostazioni in uso).
    `before`: True se salvata all'inizio dell'uscita, prima delle catture. None se il calcolo non riesce.
    """
    try:
        res = _b5_run(ctl, B5_GOALS[0])
    except Exception:
        return None
    if res.get("error"):
        return None
    rows = {int(_b5_f(r.get("hour"), -1.0)): r for r in res["ana"]["timeline"]}

    def col(get, nd):
        out = []
        for h in range(24):
            v = _b5_f(get(rows[h]), None) if h in rows else None
            out.append(None if v is None else (int(round(v)) if nd == 0 else round(v, nd)))
        return out

    sim, astro = res["sim"], res.get("astro") or {}
    fetched = res.get("fetched_utc")
    return {
        "calc": _b5_utc_iso(), "prima": bool(before), "riserva": bool(res.get("stale")),
        "dati": fetched.replace(microsecond=0).isoformat() if isinstance(fetched, _b5_dt.datetime) else "",
        "imp": {"spot": ctl["spot"], "livello": ctl["water_level"], "prede": ctl["forage_base"],
                "pressione": ctl["fishing_pressure"], "torbidita": ctl["turbidity"], "sonda": ctl["probe"]},
        "stato": str(sim.get("biological_state") or "")[:300],
        "trend3d": round(_b5_f(sim.get("micro_trend_72h")), 1),
        "picco": int(_b5_f(res["ana"]["best"].get("hour"), 0.0)),
        "luna": int(round(_b5_f(astro.get("moon_illum"), 0.0))), "fase": str(astro.get("moon_phase") or ""),
        "alba": str(astro.get("sunrise_str") or ""), "tramonto": str(astro.get("sunset_str") or ""),
        "ore": {
            "att": col(lambda r: r.get("catch_rate"), 0),
            "tro": col(lambda r: r.get("trophy_rate"), 0),
            "acqua": col(lambda r: r.get("water_temp_used", r.get("water_temp")), 1),
            "o2": col(_b5_do_mg_l, 1),
            "aria": col(lambda r: r.get("air_temp"), 1),
            "press": col(lambda r: r.get("pressure"), 1),
            "vento": col(lambda r: r.get("wind"), 0),
            "nuvole": col(lambda r: r.get("clouds"), 0),
        },
    }


# ---- ore in acqua e confronto con la previsione ---------------------------------------------------------------------
def _b5_trip_hours(start, end):
    """[(ora, minuti in acqua in quell'ora)] tra start ed end (minuti dalla mezzanotte, end escluso)."""
    out = []
    for h in range(start // 60, min(24, (end + 59) // 60)):
        m = min(end, (h + 1) * 60) - max(start, h * 60)
        if m > 0:
            out.append((h, m))
    return out


def _b5_trip_end(trip, now):
    """Fine dell'uscita in minuti; per quella in corso l'ora attuale (se è ancora lo stesso giorno)."""
    if trip["fine"]:
        return _b5_min(trip["fine"])
    if now.date().isoformat() == trip["data"]:
        return max(_b5_min(trip["inizio"]), now.hour * 60 + now.minute)
    return _b5_min(trip["inizio"])


def _b5_trip_split(trip):
    """
    Ore forti e altre ore di un'uscita conclusa: forti sono le ore in acqua con l'Attività prevista sopra la mediana di
    quell'uscita. -> (ore forti, catture, altre ore, catture) in ore e numero; None senza previsione o con meno di due
    ore di valore diverso.
    """
    prev = trip.get("prev")
    if not prev or not trip["fine"]:
        return None
    att = prev["ore"]["att"]
    hours = [(h, m) for h, m in _b5_trip_hours(_b5_min(trip["inizio"]), _b5_min(trip["fine"])) if att[h] is not None]
    if len(hours) < 2:
        return None
    vals = sorted(att[h] for h, _ in hours)
    med = (vals[(len(vals) - 1) // 2] + vals[len(vals) // 2]) / 2.0
    strong = {h for h, _ in hours if att[h] > med}
    if not strong or len(strong) == len(hours):
        return None
    fished = dict(hours)
    cs = cw = 0
    for c in trip["catture"]:
        h = _b5_min(c["ora"]) // 60
        if h in fished:
            if h in strong:
                cs += 1
            else:
                cw += 1
    hs = sum(m for h, m in hours if h in strong) / 60.0
    return hs, cs, sum(fished.values()) / 60.0 - hs, cw


# ---- disegni --------------------------------------------------------------------------------------------------------
def _b5_trip_strip(trip, now, big=False):
    """
    Striscia delle ore dell'uscita (un'ora prima e una dopo): colonne alte quanto l'Attività prevista su un binario
    alto 100, verdi nelle ore in acqua e grigie fuori, un pallino bianco per ogni cattura sopra la sua ora. Il binario
    fa leggere la scala anche quando gli indici sono bassi (in inverno 15-25). "" senza previsione.
    """
    prev = trip.get("prev")
    if not prev:
        return ""
    att = prev["ore"]["att"]
    start = _b5_min(trip["inizio"])
    end = max(_b5_trip_end(trip, now), start + 1)
    fished = {h for h, _ in _b5_trip_hours(start, end)}
    h0, h1 = max(0, start // 60 - 1), min(23, (end - 1) // 60 + 1)
    counts = {}
    for c in trip["catture"]:
        h = _b5_min(c["ora"]) // 60
        counts[h] = counts.get(h, 0) + 1
    bw, gap, hmax, r = (22, 4, 64, 4.0) if big else (8, 2, 22, 2.4)
    step = 2 * r + 2
    pad = min(5, max(counts.values(), default=0)) * step + (2 if counts else 0)
    lab = 16 if big else 0
    n = h1 - h0 + 1
    w, hgt = n * (bw + gap) - gap, pad + hmax + lab
    green = globals().get("B4_COL_BAI", "#0fa874")
    parts = []
    for i, h in enumerate(range(h0, h1 + 1)):
        x = i * (bw + gap)
        v = max(0.0, min(100.0, _b5_f(att[h], 0.0)))
        bh = max(2.0, v / 100.0 * hmax)
        y = pad + hmax - bh
        rx = 3 if big else 2
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="rgba(242,242,247,.06)"/>'
                     % (x, pad, bw, hmax, rx))
        parts.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="%d" fill="%s"/>'
                     % (x, y, bw, bh, rx, green if h in fished else "rgba(242,242,247,.22)"))
        k = counts.get(h, 0)
        for j in range(min(k, 5)):
            parts.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#F2F2F7"/>' % (x + bw / 2.0, y - 2 - r - j * step, r))
        if big and (h - h0) % 2 == 0:
            parts.append('<text x="%.1f" y="%d" text-anchor="middle">%02d</text>' % (x + bw / 2.0, hgt - 3, h))
    times = ", ".join(c["ora"] for c in trip["catture"]) or "nessuna"
    label = "Attività prevista dalle %02d alle %02d; in acqua dalle %s; catture: %s" % (
        h0, h1, trip["inizio"] + (" alle " + trip["fine"] if trip["fine"] else ""), times)
    return ('<svg class="b5d-strip" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s" '
            'font-size="11" fill="rgba(242,242,247,.55)">%s</svg>'
            % (w, hgt, w, hgt, _b5_html.escape(label), "".join(parts)))


def _b5_trip_result(trip, small=True):
    n = len(trip["catture"])
    if not n:
        return '<span class="b5d-zero">%s</span>' % ("In acqua" if trip["fine"] is None else "Cappotto")
    kg = [c["kg"] for c in trip["catture"] if c["kg"]]
    extra = " <small>max %s kg</small>" % _b5_it(max(kg), 2 if max(kg) < 1 else 1) if kg and small else ""
    return "%d bass%s" % (n, extra)


def _b5_trip_times(trip, now):
    end = _b5_trip_end(trip, now)
    span = "%s–%s" % (trip["inizio"], trip["fine"]) if trip["fine"] else "dalle %s" % trip["inizio"]
    return "%s · %s" % (span, _b5_dur(end - _b5_min(trip["inizio"])))


def _b5_day_label(iso, full=False, year=None):
    """'dom 1 nov'; con full 'domenica 1 novembre', più l'anno se non è `year`."""
    d = _b5_dt.date.fromisoformat(iso)
    if full:
        return "%s %d %s" % (_B5_DOW_FULL[d.weekday()], d.day, _B5_MON_FULL[d.month - 1]) + (
            "" if d.year == year else " %d" % d.year)
    return _b5_fmt_date(d)


# ---- callback -------------------------------------------------------------------------------------------------------
def _b5_cb_dlg(kind, tid=None):
    """Apre un cassetto del Diario: "view" dettaglio, "edit" modifica, "new" uscita già fatta."""
    ss = st.session_state
    ss["b5_dlg"] = (kind, tid)
    ss.pop("b5_del_confirm", None)
    if kind == "view":
        return
    ss["b5_draft_n"] = int(ss.get("b5_draft_n", 0)) + 1
    trip = _b5_trip_get(tid) if kind == "edit" else None
    if trip:
        ss["b5_draft"] = _b5_json.loads(_b5_json.dumps(trip))
        ss["b5_draft"]["_data0"] = trip["data"]
        return
    loc = _b5_trip_place(ss["b5_loc"])
    now = _b5_now_at(loc)
    end = max(0, now.hour * 60 + now.minute) // 30 * 30
    ss["b5_draft"] = {"id": _b5_new_id(), "luogo": loc, "data": now.date().isoformat(),
                      "inizio": "%02d:%02d" % divmod(max(0, end - 180), 60),
                      "fine": "%02d:%02d" % divmod(max(30, end), 60), "catture": [], "acqua": None, "nota": "",
                      "prev": None, "creata": _b5_utc_iso(), "mod": "", "_data0": None}


def _b5_cb_start():
    st.session_state["b5_dstart"] = True             # il calcolo si fa nella pagina, con la rotellina


def _b5_cb_catch(tid):
    trip = _b5_trip_get(tid)
    if not trip:
        return
    hhmm = _b5_now_at(trip["luogo"]).strftime("%H:%M")
    trip = dict(trip, catture=trip["catture"] + [{"id": _b5_new_id(), "ora": hhmm, "kg": None, "cm": None,
                                                  "esca": "", "nota": ""}])
    _b5_diary_put(trip)
    st.session_state["b5_toast"] = ("Cattura segnata alle %s" % hhmm, ":material/check_circle:")


def _b5_cb_catch_undo(tid):
    trip = _b5_trip_get(tid)
    if trip and trip["catture"]:
        _b5_diary_put(dict(trip, catture=trip["catture"][:-1]))
        st.session_state["b5_toast"] = ("Ultima cattura tolta", ":material/undo:")


def _b5_cb_end(tid):
    ss = st.session_state
    trip = _b5_trip_get(tid)
    if not trip:
        return
    now = _b5_now_at(trip["luogo"])
    if now.date().isoformat() != trip["data"]:     # uscita di un altro giorno rimasta aperta: l'ora di fine la si scrive
        _b5_cb_dlg("edit", tid)
        return
    end = max(_b5_min(trip["inizio"]), now.hour * 60 + now.minute)
    trip = dict(trip, fine="%02d:%02d" % divmod(end, 60))
    _b5_diary_put(trip)
    if trip["prev"] is None:
        ss["b5_dprev"] = tid                            # previsione mancata all'inizio: si calcola adesso
    n = len(trip["catture"])
    ss["b5_toast"] = ("Uscita chiusa: %s in %s." % (_b5_count(n, "bass", "bass"), _b5_dur(end - _b5_min(trip["inizio"])))
                      if n else "Uscita chiusa: cappotto segnato. Conta anche lui.", ":material/flag:")


def _b5_cb_draft_add(default):
    st.session_state["b5_draft"]["catture"].append({"id": _b5_new_id(), "ora": default, "kg": None, "cm": None,
                                                    "esca": "", "nota": ""})


def _b5_cb_draft_del(cid):
    d = st.session_state["b5_draft"]
    d["catture"] = [c for c in d["catture"] if c["id"] != cid]


def _b5_cb_del_ask(tid):
    st.session_state["b5_del_confirm"] = tid


# ---- pezzi della pagina ---------------------------------------------------------------------------------------------
def _b5_diary_head(trips, live, user=None):
    """Riquadro in cima: titolo (con l'account, se collegato), totali e, senza uscite in corso, il luogo e i due modi
    di aggiungere un'uscita."""
    ss = st.session_state
    done = [t for t in trips if t["fine"]]
    with st.container(border=True, gap="xsmall", key="b5_card_diary"):
        st.markdown('<div class="b5d-title">Diario</div>', unsafe_allow_html=True)
        if user:
            st.caption(":material/account_circle: %s" % _b5_mdx(user["nome"] or user["email"]))
        if trips:
            catches = sum(len(t["catture"]) for t in trips)
            blanks = sum(1 for t in done if not t["catture"])
            minutes = sum(_b5_min(t["fine"]) - _b5_min(t["inizio"]) for t in done)
            chips = [_b5_chip(_b5_icon("data"), _b5_count(len(trips), "uscita", "uscite")),
                     _b5_chip(_b5_fish_mark(14), "%d bass" % catches)]
            if blanks:
                chips.append(_b5_chip(_b5_icon("zero"), _b5_count(blanks, "cappotto", "cappotti")))
            if minutes > 0:
                chips.append(_b5_chip(_b5_icon("orologio"), _b5_dur(minutes) + " in acqua"))
            st.markdown('<div class="b5-chips">%s</div>' % "".join(chips), unsafe_allow_html=True)
        if live:
            return
        loc = ss["b5_loc"]
        st.button(":material/location_on: %s :material/expand_more:" % _b5_mdx(loc.get("name") or "Località"),
                  key="b5_dloc", type="tertiary", on_click=_b5_cb_open, args=("loc",))
        with st.container(horizontal=True, gap="small"):
            st.button(":material/play_arrow: Inizia adesso", key="b5_dstart_btn", type="primary", width="stretch",
                      on_click=_b5_cb_start)
            st.button(":material/add: Già fatta", key="b5_dnew", width="stretch", on_click=_b5_cb_dlg, args=("new",))
        if not trips:
            st.caption("Inizia quando arrivi in acqua: meteo e previsione si salvano in quel momento, prima delle "
                       "catture.")


def _b5_diary_live(trip, now):
    """Uscita in corso: catture con un tocco, modifica, fine."""
    esc = _b5_html.escape
    same_day = now.date().isoformat() == trip["data"]
    n = len(trip["catture"])
    with st.container(border=True, gap="small", key="b5_dlive"):
        head = ("In acqua dalle %s · %s" % (trip["inizio"], _b5_dur(_b5_trip_end(trip, now) - _b5_min(trip["inizio"])))
                if same_day else "Uscita di %s ancora aperta" % _b5_day_label(trip["data"]))
        big = '<div class="b5d-big%s">%d<small>bass</small></div>' % ("" if n else " b5d-zero", n)
        times = "".join(_b5_chip(_b5_fish_mark(12), c["ora"]) for c in trip["catture"])
        prev = trip.get("prev")
        line = ""
        if prev and same_day:
            v = prev["ore"]["att"][now.hour]
            line = '<div class="b5d-sub">Attività adesso <b>%s</b> · picco del giorno alle %02d:00</div>' % (
                "–" if v is None else v, prev["picco"])
        elif not prev:
            line = '<div class="b5d-sub">Previsione non disponibile all\'inizio: la calcolo a fine uscita.</div>'
        st.markdown('<div class="b5d"><div class="b5d-live">%s</div><div class="b5d-place">%s</div>%s%s%s</div>'
                    % (esc(head), esc(trip["luogo"]["name"]), big,
                       '<div class="b5d-times">%s</div>' % times if times else "", line),
                    unsafe_allow_html=True)
        if same_day:
            st.button(":material/add: Cattura", key="b5_dcatch", type="primary", width="stretch",
                      on_click=_b5_cb_catch, args=(trip["id"],))
        with st.container(horizontal=True, gap="small"):
            st.button(":material/edit: Modifica", key="b5_dedit_live", width="stretch", on_click=_b5_cb_dlg,
                      args=("edit", trip["id"]))
            st.button(":material/flag: Fine uscita", key="b5_dend", width="stretch", on_click=_b5_cb_end,
                      args=(trip["id"],))
        if n and same_day:
            st.button("Togli l'ultima cattura (%s)" % trip["catture"][-1]["ora"], key="b5_dundo", type="tertiary",
                      on_click=_b5_cb_catch_undo, args=(trip["id"],))


def _b5_diary_intro(cloud):
    where = ("Il diario è salvato nel tuo account." if cloud else
             "Il diario resta su questo telefono e non va su internet.")
    st.markdown(
        '<div class="b5m-card b5d-intro"><div class="b5m-cap">Come funziona</div><ol>'
        "<li>Arrivato in acqua tocca <b>Inizia adesso</b>: l'app salva meteo, acqua stimata e previsione di quel "
        "momento.</li><li>A ogni bass tocca <b>Cattura</b>: basta un tocco, peso ed esca puoi aggiungerli dopo.</li>"
        "<li>A fine giornata <b>Fine uscita</b>, anche senza catture: i cappotti servono a capire se la previsione "
        "funziona.</li></ol><p>Per un'uscita già fatta tocca <b>Già fatta</b>. %s</p></div>" % where,
        unsafe_allow_html=True)


def _b5_account_offer():
    """Invito ad accedere (solo con gli account configurati e senza accesso)."""
    with st.container(border=True, gap="small", key="b5_card_account"):
        st.markdown('<div class="b5m-cap">Salva il diario nel tuo account</div><div class="b5d-sub">Lo ritrovi su '
                    "ogni telefono e computer e non lo perdi cambiando browser. Le uscite già segnate qui potrai "
                    "copiarle nell'account.</div>", unsafe_allow_html=True)
        st.button(":material/login: Accedi con Google", key="b5_login", width="stretch", on_click=_b5_cb_go,
                  args=("login",))
        st.caption("Con l'accesso salviamo nel database di Bassometro (Google Cloud, in Europa) le tue uscite, il tuo "
                   "nome e la tua email. Puoi cancellarli quando vuoi, dal fondo di questa pagina.")


def _b5_account_import(user):
    """Uscite rimaste nel browser e non ancora nell'account: si copiano con un tocco, poi il browser si svuota."""
    ss = st.session_state
    local = ss.get("b5_local")
    if not isinstance(local, dict) or not isinstance(ss.get("b5_diary"), dict):
        return
    known = {t["id"] for t in ss["b5_diary"]["uscite"]}
    extra = [t for t in local["uscite"] if t["id"] not in known]
    if not extra:
        return
    with st.container(border=True, gap="small", key="b5_card_import"):
        st.markdown('<div class="b5m-cap">Uscite su questo telefono</div><div class="b5d-sub">%s salvate qui prima '
                    "dell'accesso non sono ancora nel tuo account.</div>"
                    % _b5_count(len(extra), "uscita", "uscite").capitalize(), unsafe_allow_html=True)
        if not st.button(":material/cloud_upload: Copiale nel mio account", key="b5_import", type="primary",
                         width="stretch"):
            return
        _b5_diary_put(many=[_b5_json.loads(_b5_json.dumps(t)) for t in extra])
        if ss.get("b5_cloud_todo"):
            st.rerun()                              # non riuscito: l'avviso va in cima, il browser non si tocca
        local["uscite"], local["rev"] = [], local["rev"] + 1
        ss["b5_toast"] = ("%s nel tuo account" % _b5_count(len(extra), "uscita copiata", "uscite copiate"),
                          ":material/cloud_done:")
        st.rerun()


def _b5_diary_proof(trips):
    """Come va la previsione: catture all'ora nelle ore forti e nelle altre, sommando le uscite concluse."""
    splits = [s for s in map(_b5_trip_split, trips) if s]
    n = len(splits)
    green = globals().get("B4_COL_BAI", "#0fa874")
    if n < B5_DIARY_MIN_TRIPS:
        st.markdown('<div class="b5m-card"><div class="b5d-head"><span class="b5m-cap">Come va la previsione</span>'
                    '<span class="b5m-cap">%d su %d uscite</span></div><span class="b5d-bar"><i style="width:%.0f%%;'
                    'background:%s"></i></span><div class="b5m-sub">Dopo %d uscite concluse qui vedrai se prendi di '
                    "più nelle ore che il modello dava migliori. Contano le uscite di almeno due ore con la previsione "
                    "salvata.</div></div>" % (n, B5_DIARY_MIN_TRIPS, 100.0 * n / B5_DIARY_MIN_TRIPS, green,
                                              B5_DIARY_MIN_TRIPS), unsafe_allow_html=True)
        return
    hs, cs, hw, cw = (sum(x) for x in zip(*splits))
    rs, rw = (cs / hs if hs else 0.0), (cw / hw if hw else 0.0)
    total = cs + cw
    if not total:
        verdict = "Ancora nessuna cattura nelle uscite concluse: il confronto parte dalla prima."
    elif not rw:
        verdict = "Finora tutte le catture sono arrivate nelle ore forti."
    elif rs / rw >= 1.5:
        verdict = "Nelle ore forti prendi %s volte di più che nelle altre." % _b5_it(rs / rw, 1)
    elif rs / rw <= 1 / 1.5:
        verdict = "Finora prendi di più nelle altre ore: per te la previsione non sta funzionando."
    else:
        verdict = "Finora nessuna differenza chiara tra ore forti e altre ore."
    if total < B5_DIARY_FEW_CATCHES:
        verdict += " Con %s è presto per conclusioni." % _b5_count(total, "cattura", "catture")
    top = max(rs, rw) or 1.0

    def cell(label, rate, hours, color):
        return ('<div><span class="b5m-lab">%s</span><span class="b5m-val">%s<small>bass/ora</small></span>'
                '<span class="b5d-bar"><i style="width:%.0f%%;background:%s"></i></span>'
                '<span class="b5m-sub">%s in acqua</span></div>'
                % (label, _b5_it(rate, 1), 100.0 * rate / top, color, _b5_dur(hours * 60)))

    st.markdown('<div class="b5m-card"><div class="b5m-cap">Come va la previsione</div><div class="b5d-cmp">%s%s</div>'
                '<div class="b5d-verdict">%s</div><div class="b5m-sub">Ore forti: in ogni uscita, la metà delle ore in '
                "acqua con l'Attività prevista più alta. %s, %s.</div></div>"
                % (cell("Ore forti", rs, hs, green), cell("Altre ore", rw, hw, "rgba(242,242,247,.45)"),
                   _b5_html.escape(verdict), _b5_count(n, "uscita", "uscite"), _b5_count(total, "cattura", "catture")),
                unsafe_allow_html=True)


def _b5_diary_list(trips, now):
    """Uscite concluse dalla più recente, divise per mese (quella in corso sta nel suo riquadro); ogni riquadro si
    tocca per intero e apre il dettaglio."""
    esc = _b5_html.escape
    month = None
    for t in sorted((t for t in trips if t["fine"]), key=lambda t: (t["data"], t["inizio"]), reverse=True):
        d = _b5_dt.date.fromisoformat(t["data"])
        if (d.year, d.month) != month:
            month = (d.year, d.month)
            st.markdown('<p class="b5d-month">%s %d</p>' % (_B5_MON_FULL[d.month - 1].capitalize(), d.year),
                        unsafe_allow_html=True)
        sub = _b5_trip_times(t, now) + (" · acqua %s° misurata" % _b5_it(t["acqua"]) if t["acqua"] is not None else "")
        with st.container(border=True, key="b5_dcard_" + t["id"]):
            st.markdown('<div class="b5d-row"><div class="b5d-txt"><span class="b5d-when">%s · %s</span>'
                        '<span class="b5d-res">%s</span><span class="b5d-sub">%s</span></div>%s'
                        '<span class="b5d-go" aria-hidden="true">›</span></div>'
                        % (esc(_b5_day_label(t["data"])), esc(t["luogo"]["name"]), _b5_trip_result(t), esc(sub),
                           _b5_trip_strip(t, now)), unsafe_allow_html=True)
            st.button("Apri l'uscita di %s" % _b5_day_label(t["data"]), key="b5_dcbtn_" + t["id"],
                      on_click=_b5_cb_dlg, args=("view", t["id"]))


def _b5_account_box(user):
    """Account nel pannello in fondo: chi è collegato, Esci, cancellazione dal database (con conferma)."""
    ss = st.session_state
    st.markdown("**%s**" % _b5_mdx(user["nome"] or user["email"]) + ("  \n" + _b5_mdx(user["email"])
                                                                      if user["nome"] and user["email"] else ""))
    st.button(":material/logout: Esci", key="b5_logout", width="stretch", on_click=_b5_cb_go, args=("logout",))
    if ss.get("b5_wipe") != user["uid"]:
        st.button(":material/delete_forever: Cancella il mio diario dal database", key="b5_wipe_ask", type="tertiary",
                  on_click=lambda: ss.__setitem__("b5_wipe", user["uid"]))
        return
    st.warning("Cancello dal database tutte le tue uscite, il tuo nome e la tua email. Non si può annullare: se vuoi, "
               "scarica prima una copia.", icon=":material/delete_forever:")
    with st.container(horizontal=True, gap="small"):
        if st.button("Sì, cancella", key="b5_wipe_ok", width="stretch"):
            try:
                with st.spinner("Cancello…"):
                    _b5_db_commit(user["uid"], delete=[t["id"] for t in _b5_db_load(user["uid"])], profile={})
            except Exception as exc:
                st.error("Cancellazione non riuscita: %s" % _b5_mdx(_b5_short_exc(exc)), icon=":material/error:")
                return
            ss.pop("b5_wipe", None)
            ss["b5_diary"], ss["b5_cloud_todo"], ss["b5_cloud_t"] = {"rev": 0, "uscite": []}, {}, _b5_time.time()
            ss["b5_cloud_profile"] = None
            ss["b5_toast"] = ("Diario cancellato dal database", ":material/delete_forever:")
            st.rerun()
        st.button("Annulla", key="b5_wipe_no", width="stretch", on_click=lambda: ss.pop("b5_wipe", None))


def _b5_diary_backup(diary, user):
    """Account (se collegato) e copia di sicurezza: il diario in un file JSON da scaricare e ricaricare (unione per
    uscita)."""
    ss = st.session_state
    title = ":material/account_circle: Account e copia di sicurezza" if user else ":material/save: Copia di sicurezza"
    with st.expander(title):
        if user:
            _b5_account_box(user)
            st.divider()
            st.caption("Il diario è salvato nel tuo account: una copia in un file resta utile per tenerlo anche "
                       "fuori da Bassometro.")
        else:
            st.caption("Il diario è salvato solo in questo browser, su questo telefono: non va su nessun server. Se "
                       "cancelli i dati del browser o cambi telefono lo perdi, quindi scarica una copia ogni tanto. Su "
                       "iPhone Safari può cancellare i dati di un sito che non apri da più di una settimana.")
        today = _b5_today(ss["b5_loc"].get("tz"), ss["b5_loc"].get("lon"))
        st.download_button(":material/download: Scarica una copia", data=_b5_diary_json(diary),
                           file_name="bassometro-diario-%s.json" % today.isoformat(), mime="application/json",
                           width="stretch", on_click="ignore", disabled=not diary["uscite"])
        up = st.file_uploader("Ripristina da una copia", type=["json"], key="b5_dup")
        if up is None or ss.get("b5_dup_done") == up.file_id:
            return
        ss["b5_dup_done"] = up.file_id
        _, trips = _b5_diary_parse(up.getvalue().decode("utf-8", "replace"))
        if not trips:
            st.error("Il file non contiene uscite del diario di Bassometro.", icon=":material/error:")
            return
        mine = {t["id"]: t for t in diary["uscite"]}
        newer = [t for t in trips if t["id"] not in mine or t["mod"] > mine[t["id"]]["mod"]]
        new = sum(1 for t in newer if t["id"] not in mine)
        if newer:
            _b5_diary_put(many=newer)
        ss["b5_toast"] = ("Copia caricata: %d uscite nuove, %d già nel diario." % (new, len(trips) - new),
                          ":material/restore:")
        st.rerun()


# ---- cassetti -------------------------------------------------------------------------------------------------------
def _b5_stats_html(cells):
    return '<div class="b5m-stats b5d-stats">%s</div>' % "".join(
        '<div><span class="b5m-lab">%s</span><span class="b5m-val">%s</span><span class="b5m-sub">%s</span></div>'
        % c for c in cells)


def _b5_trip_conditions(trip, now):
    """Riquadri delle condizioni nelle ore in acqua (dalla previsione salvata)."""
    prev = trip["prev"]
    ore = prev["ore"]
    start = _b5_min(trip["inizio"])
    hours = [h for h, _ in _b5_trip_hours(start, max(_b5_trip_end(trip, now), start + 1))]

    def vals(key):
        return [ore[key][h] for h in hours if ore[key][h] is not None]

    def span(v, nd=0, unit=""):
        if not v:
            return "–"
        a, b = min(v), max(v)
        txt = _b5_it(a, nd) if round(a, nd) == round(b, nd) else "%s–%s" % (_b5_it(a, nd), _b5_it(b, nd))
        return txt + unit

    water = vals("acqua")
    est = "%s°" % _b5_it(sum(water) / len(water)) if water else "–"
    if trip["acqua"] is not None:
        water_cell = ("ACQUA", "%s°" % _b5_it(trip["acqua"]), "misurata · stimata %s" % est)
    else:
        water_cell = ("ACQUA", est, "stimata")
    press = vals("press")
    if len(press) >= 2:
        d = press[-1] - press[0]
        trend = "stabile" if abs(d) < 0.5 else "%s%s in uscita" % ("−" if d < 0 else "+", _b5_it(abs(d)))
    else:
        trend = ""
    att = vals("att")
    cells = [
        water_cell,
        ("ARIA", span(vals("aria"), 0, "°"), ""),
        ("VENTO", span(vals("vento")) + "<small>km/h</small>", ""),
        ("PRESSIONE", (str(int(round(sum(press) / len(press)))) + "<small>hPa</small>") if press else "–", trend),
        ("ATTIVITÀ", span(att), "picco del giorno %02d:00" % prev["picco"]),
        ("LUNA", "%d %%" % prev["luna"], _b5_html.escape(prev["fase"].lower()) if prev["fase"] not in ("", "n/d") else ""),
    ]
    return _b5_stats_html(cells)


def _b5_trip_viewer(tid, now):
    trip = _b5_trip_get(tid)
    if not trip:
        return
    esc = _b5_html.escape
    title = _b5_day_label(trip["data"], full=True, year=now.year)

    @st.dialog(title[0].upper() + title[1:], position=B5_DRAWER_POSITION, icon=":material/menu_book:",
               on_dismiss="ignore")
    def drawer():
        ss = st.session_state
        prev = trip.get("prev")
        n = len(trip["catture"])
        big = ('<div class="b5d-big">%d<small>bass</small></div>' % n if n else
               '<div class="b5d-big b5d-zero">%s</div>' % ("0<small>bass</small>" if trip["fine"] is None
                                                            else "Cappotto"))
        html = '<div class="b5d-sub">%s · %s</div>%s' % (esc(trip["luogo"]["name"]), esc(_b5_trip_times(trip, now)),
                                                         big)
        if prev:
            html += ('<div class="b5d-chart">%s</div><div class="b5d-legend"><i class="b5d-key"></i>Attività '
                     'prevista, in acqua <i class="b5d-key b5d-off"></i>fuori <i class="b5d-dot"></i>cattura</div>'
                     % _b5_trip_strip(trip, now, big=True))
            caught = [prev["ore"]["att"][_b5_min(c["ora"]) // 60] for c in trip["catture"]]
            caught = [v for v in caught if v is not None]
            start = _b5_min(trip["inizio"])
            fished = [(prev["ore"]["att"][h], m) for h, m in _b5_trip_hours(start, max(_b5_trip_end(trip, now),
                                                                                          start + 1))
                      if prev["ore"]["att"][h] is not None]
            if caught and fished:
                mean = sum(v * m for v, m in fished) / float(sum(m for _, m in fished))
                html += ('<div class="b5d-sub">Catture con Attività media <b>%d</b>, contro %d delle ore in '
                         'acqua.</div>' % (round(sum(caught) / len(caught)), round(mean)))
        st.markdown('<div class="b5d">%s</div>' % html, unsafe_allow_html=True)
        if trip["catture"]:
            lines = []
            for c in trip["catture"]:
                bits = [b for b in ("%s kg" % _b5_it(c["kg"], 2) if c["kg"] else "",
                                    "%s cm" % _b5_it(c["cm"], 0) if c["cm"] else "", c["esca"], c["nota"]) if b]
                lines.append("- **%s**%s" % (c["ora"], " · " + _b5_mdx(" · ".join(bits)) if bits else ""))
            st.markdown("\n".join(lines))
        if prev:
            st.markdown(_b5_trip_conditions(trip, now), unsafe_allow_html=True)
        if trip["nota"]:
            st.markdown(_b5_mdx(trip["nota"]))
        if prev:
            imp = prev["imp"]
            if prev["prima"]:
                when = "salvata alle %s, all'inizio dell'uscita" % _b5_hhmm_of(prev["calc"], trip["luogo"])
            else:
                when = "calcolata dopo l'uscita, con il meteo del giorno"
            st.caption("Previsione %s%s · %s, livello %s, torbidità %s%s" % (
                when, " (dati salvati, Open-Meteo non rispondeva)" if prev.get("riserva") else "",
                _b5_mdx(_b5_spot_label(imp.get("spot"))),
                _b5_mdx(B5_WATER_LABELS.get(imp.get("livello"), imp.get("livello") or "").lower()),
                "stimata" if imp.get("torbidita") in (None, "Non specificato") else _b5_mdx(imp["torbidita"].lower()),
                " · sonda %s °C" % _b5_it(imp["sonda"]) if imp.get("sonda") is not None else ""))
        else:
            st.caption("Previsione non disponibile: si calcola solo per gli ultimi %d giorni." % -B5_OFFSET_MIN)
        with st.container(horizontal=True, gap="small"):
            if st.button(":material/edit: Modifica", key="b5_dv_edit", width="stretch", on_click=_b5_cb_dlg,
                         args=("edit", tid)):
                st.rerun()
            st.button(":material/delete: Elimina", key="b5_dv_del", width="stretch", on_click=_b5_cb_del_ask,
                      args=(tid,))
        if ss.get("b5_del_confirm") == tid:
            st.warning("Eliminare questa uscita? Non si può annullare.", icon=":material/delete:")
            with st.container(horizontal=True, gap="small"):
                if st.button("Sì, elimina", key="b5_dv_del_ok", width="stretch"):
                    _b5_diary_put(delete_id=tid)
                    ss.pop("b5_del_confirm", None)
                    ss["b5_toast"] = ("Uscita eliminata", ":material/delete:")
                    st.rerun()
                if st.button("Annulla", key="b5_dv_del_no", width="stretch"):
                    ss.pop("b5_del_confirm", None)
                    st.rerun(scope="fragment")

    drawer()


def _b5_hhmm_of(iso_utc, loc):
    """Ora del luogo (HH:MM) di un istante UTC salvato in ISO."""
    try:
        t = _b5_dt.datetime.fromisoformat(iso_utc)
        zi = _b5_zone(loc.get("tz"))
        t = t.astimezone(zi) if zi is not None else t + _b5_dt.timedelta(
            hours=_b5_fallback_offset(loc.get("tz"), loc.get("lon"), t.date()))
        return t.strftime("%H:%M")
    except Exception:
        return "--:--"


def _b5_time_of(hhmm):
    h, m = divmod(_b5_min(hhmm), 60)
    return _b5_dt.time(h, m)


def _b5_trip_editor(now_of):
    ss = st.session_state
    draft = ss.get("b5_draft")
    if not isinstance(draft, dict):
        return
    new = _b5_trip_get(draft["id"]) is None

    @st.dialog("Uscita già fatta" if new else "Modifica l'uscita", position=B5_DRAWER_POSITION,
               icon=":material/edit_note:", on_dismiss="ignore")
    def drawer():
        k = "b5e%d_" % int(ss.get("b5_draft_n", 0))
        loc = draft["luogo"]
        now = now_of(loc)
        today = now.date()
        st.caption(":material/location_on: %s%s" % (_b5_mdx(loc["name"]), " · per un altro lago cambialo prima nella "
                                                    "pagina del Diario" if new else ""))
        day = st.date_input("Giorno", value=_b5_dt.date.fromisoformat(draft["data"]),
                            min_value=today - _b5_dt.timedelta(days=B5_DIARY_MAX_DAYS), max_value=today,
                            format="DD/MM/YYYY", key=k + "data")
        with st.container(horizontal=True, gap="small"):
            t0 = st.time_input("Inizio", value=_b5_time_of(draft["inizio"]), step=300, key=k + "inizio")
            t1 = st.time_input("Fine", value=_b5_time_of(draft["fine"]) if draft["fine"] else None, step=300,
                               key=k + "fine", help=None)
        if draft["fine"] is None and not new:
            st.caption("Lascia vuota la fine se sei ancora in acqua.")
        st.markdown("**Catture**" if draft["catture"] else "**Catture** · nessuna (cappotto)")
        for i, c in enumerate(draft["catture"]):
            ck = "%sc%s_" % (k, c["id"])
            with st.container(border=True, gap="xsmall"):
                with st.container(horizontal=True, vertical_alignment="center"):
                    st.markdown(":small[**Cattura %d**]" % (i + 1), width="stretch")
                    st.button(":material/close:", key=ck + "del", type="tertiary", on_click=_b5_cb_draft_del,
                              args=(c["id"],), help="Togli questa cattura")
                with st.container(horizontal=True, gap="small"):
                    st.time_input("Ora", value=_b5_time_of(c["ora"]), step=300, key=ck + "ora")
                    st.number_input("Peso (kg)", min_value=0.0, max_value=15.0, value=c["kg"], step=0.1,
                                    format="%.2f", placeholder="–", key=ck + "kg")
                with st.container(horizontal=True, gap="small"):
                    st.number_input("Lunghezza (cm)", min_value=0.0, max_value=100.0, value=c["cm"], step=1.0,
                                    format="%.0f", placeholder="–", key=ck + "cm")
                    st.text_input("Esca", value=c["esca"], max_chars=60, placeholder="es. spinnerbait", key=ck + "esca")
        last = draft["catture"][-1]["ora"] if draft["catture"] else draft["inizio"]
        if draft["fine"] is None and now.date().isoformat() == draft["data"]:
            last = now.strftime("%H:%M")
        st.button(":material/add: Aggiungi una cattura", key=k + "add", width="stretch", on_click=_b5_cb_draft_add,
                  args=(last,))
        water = st.number_input("Acqua misurata (°C)", min_value=0.0, max_value=38.0, value=draft["acqua"], step=0.1,
                                format="%.1f", placeholder="Non misurata", key=k + "acqua")
        note = st.text_area("Note", value=draft["nota"], max_chars=1000, height=90, key=k + "nota",
                            placeholder="Spot, esche, cosa ha funzionato…")
        if not st.button(":material/check: Salva", key=k + "save", type="primary", width="stretch"):
            return
        start = t0.strftime("%H:%M") if t0 else None
        end = t1.strftime("%H:%M") if t1 else None
        errors = []
        if start is None:
            errors.append("Manca l'ora di inizio.")
        if end is None and (new or day != today):
            errors.append("Manca l'ora di fine.")
        if start and end and end <= start:
            errors.append("La fine deve venire dopo l'inizio (le uscite oltre la mezzanotte non sono previste).")
        if start and day == today and start > now.strftime("%H:%M"):
            errors.append("L'inizio è più tardi di adesso.")
        if end is None and any(t["fine"] is None and t["id"] != draft["id"] for t in _b5_diary_trips()):
            errors.append("C'è già un'uscita in corso.")
        catches = []
        for i, c in enumerate(draft["catture"]):
            ck = "%sc%s_" % (k, c["id"])
            ora = ss.get(ck + "ora")
            hhmm = ora.strftime("%H:%M") if ora else None
            if hhmm is None:
                errors.append("Manca l'ora della cattura %d." % (i + 1))
            elif start and (hhmm < start or (end and hhmm > end)):
                errors.append("La cattura %d (%s) è fuori dall'orario dell'uscita." % (i + 1, hhmm))
            catches.append(_b5_catch_clean({"id": c["id"], "ora": hhmm or "00:00", "kg": ss.get(ck + "kg"),
                                            "cm": ss.get(ck + "cm"), "esca": ss.get(ck + "esca"), "nota": c["nota"]}))
        if errors:
            for e in errors:
                st.error(e, icon=":material/error:")
            return
        trip = {key: v for key, v in draft.items() if not key.startswith("_")}
        trip.update(data=day.isoformat(), inizio=start, fine=end, acqua=water, nota=(note or "").strip(),
                    catture=sorted(catches, key=lambda c: c["ora"]))
        if trip["prev"] is None or trip["data"] != draft.get("_data0"):
            ctl = _b5_trip_ctl(trip)
            prev = None
            if ctl is not None:
                with st.spinner("Calcolo meteo e previsione di quel giorno…"):
                    prev = _b5_trip_forecast(ctl, False)
            trip["prev"] = prev
        _b5_diary_put(trip)
        ss.pop("b5_draft", None)
        ss["b5_toast"] = ("Uscita salvata", ":material/check_circle:")
        st.rerun()

    drawer()


# ---- pagina ---------------------------------------------------------------------------------------------------------
def _b5_page_diario():
    """Sezione Diario: intestazione con i totali, uscita in corso, confronto con la previsione, uscite, copia."""
    ss = st.session_state
    diary = ss.get("b5_diary")
    user = _b5_user()
    if not isinstance(diary, dict):                 # il browser non ha ancora mandato il diario, o il database non va
        with st.container(border=True, gap="xsmall", key="b5_card_diary"):
            st.markdown('<div class="b5d-title">Diario</div>', unsafe_allow_html=True)
            if user and ss.get("b5_cloud_err"):
                st.error("Non riesco a leggere il tuo diario dal database. Riprova tra poco.",
                         icon=":material/cloud_off:")
                st.button(":material/refresh: Riprova", key="b5_cloud_retry", width="stretch",
                          on_click=lambda: ss.pop("b5_diary_src", None))
                st.caption(_b5_mdx(ss["b5_cloud_err"]))
            else:
                st.caption("Apro il diario…")
        return
    toast = ss.pop("b5_toast", None)
    if toast:
        st.toast(toast[0], icon=toast[1])
    if user and (ss.get("b5_cloud_todo") or ss.get("b5_cloud_err")):
        n = len(ss.get("b5_cloud_todo") or {})
        st.warning("Non riesco a salvare nel tuo account%s: le modifiche restano qui finché non si riesce." % (
            " (%s)" % _b5_count(n, "modifica in attesa", "modifiche in attesa") if n else ""),
            icon=":material/cloud_off:")
        st.button(":material/refresh: Riprova adesso", key="b5_cloud_flush", on_click=_b5_cloud_flush)
    warn = ss.get("b5_diary_warn") if not user else None
    if warn:
        st.warning("Lo spazio del browser per il diario è finito: scarica una copia di sicurezza (in fondo alla pagina)."
                   if warn == "spazio" else
                   "Questo browser non permette di salvare il diario (navigazione privata o dati dei siti bloccati): "
                   "le uscite restano solo finché la pagina è aperta. Scarica una copia prima di chiuderla.",
                   icon=":material/warning:")

    if ss.pop("b5_dstart", False) and not any(t["fine"] is None for t in diary["uscite"]):
        loc = _b5_trip_place(ss["b5_loc"])
        now = _b5_now_at(loc)
        with st.spinner("Salvo meteo e previsione di adesso…"):
            prev = _b5_trip_forecast(_b5_ctl(0), True)
        _b5_diary_put({"id": _b5_new_id(), "luogo": loc, "data": now.date().isoformat(),
                       "inizio": now.strftime("%H:%M"), "fine": None, "catture": [], "acqua": None, "nota": "",
                       "prev": prev, "creata": _b5_utc_iso(), "mod": ""})
        ss["b5_toast"] = (("Uscita iniziata alle %s. Buona pesca!" % now.strftime("%H:%M")) if prev else
                          "Uscita iniziata. Previsione non disponibile adesso: la calcolo a fine uscita.",
                          ":material/play_arrow:")
        st.rerun()
    tid = ss.pop("b5_dprev", None)
    trip = _b5_trip_get(tid) if tid else None
    if trip and trip["prev"] is None:
        ctl = _b5_trip_ctl(trip)
        if ctl is not None:
            with st.spinner("Calcolo la previsione dell'uscita…"):
                prev = _b5_trip_forecast(ctl, False)
            if prev:
                _b5_diary_put(dict(trip, prev=prev))
                st.rerun()

    trips = diary["uscite"]
    now_cache = {}

    def now_of(loc):
        key = loc.get("tz") or ""
        if key not in now_cache:
            now_cache[key] = _b5_now_at(loc)
        return now_cache[key]

    live = next((t for t in trips if t["fine"] is None), None)
    _b5_diary_head(trips, live, user)
    if live:
        _b5_diary_live(live, now_of(live["luogo"]))
    if user:
        _b5_account_import(user)
    elif _b5_cloud_ready():
        _b5_account_offer()
    if not trips:
        _b5_diary_intro(bool(user))
    else:
        _b5_diary_proof(trips)
        here = now_of(ss["b5_loc"])
        _b5_diary_list(trips, here)
    _b5_diary_backup(diary, user)
    st.caption("Indici del modello relativi (0-100) · " + ("Diario salvato nel tuo account" if user else
                                                            "Il diario resta su questo telefono"),
               text_alignment="center")

    dlg = ss.pop("b5_dlg", None)
    if dlg and dlg[0] == "view":
        t = _b5_trip_get(dlg[1])
        if t:
            _b5_trip_viewer(dlg[1], now_of(t["luogo"]))
    elif dlg and dlg[0] in ("edit", "new"):
        _b5_trip_editor(now_of)
    _b5_open_drawer()


# ------------------------------------------------------------------------------
# CONTROLLER
# ------------------------------------------------------------------------------
def _b5_guarded(fn, res, label):
    """Un tab che fallisce non deve portare giù gli altri."""
    try:
        fn(res)
    except Exception as exc:
        st.error(_b5_mdx(_b5_short_exc(exc)), title="%s non disponibile" % label, icon=":material/warning:")


def _b5_fetched_text(res):
    """"Dati meteo scaricati alle 14:32" nell'ora del luogo, con il giorno se non è oggi; "" se l'ora non è nota."""
    when, ctl = res.get("fetched_utc"), res.get("ctl") or {}
    if not isinstance(when, _b5_dt.datetime):
        return ""
    local = None
    zi = _b5_zone(ctl.get("tz"))
    if zi is not None:
        try:
            local = when.astimezone(zi)
        except Exception:
            local = None
    if local is None:
        local = when + _b5_dt.timedelta(hours=_b5_fallback_offset(ctl.get("tz"), ctl.get("lon"), when.date()))
    day = "" if local.date() == ctl.get("today") else " %s" % _b5_fmt_date(local.date())
    return "Dati meteo scaricati%s alle %02d:%02d" % (day, local.hour, local.minute)


def _b5_footer(res):
    fetched = _b5_fetched_text(res)
    if fetched:
        st.caption(":material/update: " + _b5_mdx(fetched), text_alignment="center")
    st.button(":material/refresh: Aggiorna i dati meteo", key="b5_refresh", on_click=_b5_cb_refresh, width="stretch")
    st.caption(_b5_mdx(B5_FOOTER_TEXT), text_alignment="center")


def _b5_logo_path(name):
    """File del logo nella cartella Logo accanto all'app, oppure accanto all'app (pubblicazione senza cartelle); None
    se manca."""
    try:
        base = _b5_os.path.dirname(_b5_os.path.abspath(__file__))
    except NameError:                               # eseguito senza file (prove): la cartella di lavoro
        base = _b5_os.getcwd()
    for path in (_b5_os.path.join(base, "Logo", name), _b5_os.path.join(base, name)):
        if _b5_os.path.isfile(path):
            return path
    return None


def main():
    """
    Controller dell'app: barra delle sezioni; Pesca: controlli -> Blocchi 1-4 -> tre tab; Meteo: _b5_page_meteo;
    Diario: _b5_page_diario.
    """
    st.set_page_config(page_title=B5_PAGE_TITLE, page_icon=_b5_logo_path(B5_PAGE_ICON_FILE) or ":material/phishing:",
                       layout="centered", initial_sidebar_state="collapsed")
    st.html("<style>%s</style>" % _b5_css())       # solo <style>: Streamlit lo inietta senza occupare spazio
    logo = next((p for p in map(_b5_logo_path, B5_LOGO_FILES) if p), None)
    if logo:
        st.logo(logo, size="large")                 # al centro della fascia sopra il primo riquadro (B5_CSS)
    _b5_config_warnings()
    missing = _b5_missing_blocks()
    if missing:
        _b5_render_missing(missing)
        return

    _b5_init_state()
    ss = st.session_state
    for key in _B5_KEEP_KEYS:         # restano anche nei giri in cui i loro widget non sono disegnati (Meteo)
        ss[key] = ss[key]
    section = _b5_nav()
    if section == "diario" or _b5_diary_pending():  # ponte con il browser: diario da leggere o da scrivere
        _b5_diary_store()
    if section == "meteo":
        _b5_page_meteo()
        return
    if section == "diario":
        _b5_page_diario()
        return

    header = st.container()           # riempita dopo il calcolo: mostra la data effettiva della serie
    ctl = _b5_controls()
    goal = st.session_state["b5_goal"]

    with st.spinner("Scarico i dati meteo e calcolo la simulazione…"):
        res = _b5_run(ctl, goal)
    astro = res.get("astro")
    if astro is None:
        try:
            astro = _b5_compute_astro(res["date"], ctl["lat"], ctl["lon"], ctl["tz"])
        except Exception:
            astro = None
    with header:
        _b5_render_header(ctl, res["date"], astro)
    _b5_open_drawer()                 # anche con errore meteo: la località si deve poter cambiare

    if res["error"]:
        _b5_render_error(res)
        _b5_footer(res)
        return

    _b5_render_notices(res)
    tab_charts, tab_report, tab_hours = st.tabs(list(B5_TAB_LABELS))
    with tab_charts:
        _b5_guarded(_b5_tab_charts, res, "Grafici")
    with tab_report:
        _b5_guarded(_b5_tab_report, res, "Strategia")
    with tab_hours:
        _b5_guarded(_b5_tab_hours, res, "Tabella oraria")
    _b5_render_data_notes(res)
    _b5_footer(res)


if __name__ == "__main__":
    main()
